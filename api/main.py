#!/usr/bin/env python3
"""CDP Agentic Ad Engine — Serving API.

FastAPI application that exposes endpoints for serving personalised
ad creatives, ingesting clickstream events, and retrieving user profiles.

Endpoints:
    GET  /ad/{global_uid}     → cached ad creative with background refresh
    POST /event               → ingest a clickstream event
    GET  /profile/{global_uid} → full unified profile
    GET  /health              → dependency status
    GET  /metrics             → request stats

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
except ImportError:
    Limiter = None

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

from common.logging import setup_logging, get_logger
from common.schemas import (
    AdCreative,
    AdResponse,
    ClickstreamEvent,
    EventIngestResponse,
    HealthStatus,
    ProfileResponse,
    UnifiedProfile,
)
from uid_engine.merger import ProfileMerger
from agents.intent_profiler import IntentProfiler

logger = get_logger("api")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "cdp")
MONGODB_PROFILE_COLLECTION = os.getenv("MONGODB_PROFILE_COLLECTION", "unified_profiles")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_AD_CACHE_TTL = int(os.getenv("REDIS_AD_CACHE_TTL", "600"))
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

AD_REFRESH_MINUTES = int(os.getenv("AD_CREATIVE_REGENERATE_MINUTES", "10"))
AD_REFRESH_TD = timedelta(minutes=AD_REFRESH_MINUTES)


# ──────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────

limiter = None
if Limiter is not None:
    limiter = Limiter(key_func=get_remote_address)


# ──────────────────────────────────────────────
# Global State
# ──────────────────────────────────────────────

class AppState:
    """Shared application state for the FastAPI app."""

    def __init__(self) -> None:
        self.mongo: Optional[AsyncIOMotorClient] = None
        self.redis: Optional[aioredis.Redis] = None
        self.qdrant: Optional[QdrantClient] = None
        self.event_queue: asyncio.Queue[ClickstreamEvent] = asyncio.Queue(maxsize=10000)
        self._refresh_in_progress: Set[str] = set()

        # Metrics
        self.total_requests: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.total_latency_ms: float = 0.0

        # Health state (set during startup)
        self.services: Dict[str, str] = {
            "mongodb": "unknown",
            "redis": "unknown",
            "qdrant": "unknown",
            "ollama": "unknown",
        }

    def record_request(self, latency_ms: float, cache_hit: bool = False) -> None:
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0


state = AppState()


# ──────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify dependencies, start event consumer background task."""
    setup_logging(service_name="api-server")
    logger.info("api_starting")

    # ── MongoDB ──
    if AsyncIOMotorClient is not None:
        try:
            state.mongo = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
            await state.mongo.admin.command("ping")
            state.services["mongodb"] = "ok"
            logger.info("mongodb_ok")
        except Exception as exc:
            state.services["mongodb"] = f"error: {exc}"
            logger.warning("mongodb_unavailable", error=str(exc))
    else:
        state.services["mongodb"] = "unavailable (package not installed)"

    # ── Redis ──
    if aioredis is not None:
        try:
            state.redis = aioredis.from_url(REDIS_URL, decode_responses=True, socket_timeout=3)
            await state.redis.ping()
            state.services["redis"] = "ok"
            logger.info("redis_ok")
        except Exception as exc:
            state.services["redis"] = f"error: {exc}"
            logger.warning("redis_unavailable", error=str(exc))
    else:
        state.services["redis"] = "unavailable (package not installed)"

    # ── Qdrant ──
    if QdrantClient is not None:
        try:
            state.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=3)
            state.qdrant.get_collections()
            state.services["qdrant"] = "ok"
            logger.info("qdrant_ok")
        except Exception as exc:
            state.services["qdrant"] = f"error: {exc}"
            logger.warning("qdrant_unavailable", error=str(exc))
    else:
        state.services["qdrant"] = "unavailable (package not installed)"

    # ── Ollama ──
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                state.services["ollama"] = "ok"
                logger.info("ollama_ok")
            else:
                state.services["ollama"] = f"error: status {resp.status_code}"
    except Exception as exc:
        state.services["ollama"] = f"error: {exc}"
        logger.warning("ollama_unavailable", error=str(exc))

    # ── Background event consumer ──
    consumer_task = asyncio.create_task(_event_consumer_loop())

    # ── Profile Merger + Change Stream ──
    merger = ProfileMerger(mongo_uri=MONGODB_URI)
    profiler = IntentProfiler(mongo_uri=MONGODB_URI)
    change_stream_task: Optional[asyncio.Task] = None
    if AsyncIOMotorClient is not None and state.services.get("mongodb") == "ok":
        try:
            await merger.connect()
            await profiler.connect()
            change_stream_task = asyncio.create_task(
                merger.start_change_stream(profiler.change_stream_callback)
            )
            logger.info("change_stream_started")
        except Exception as exc:
            logger.warning("change_stream_start_failed", error=str(exc))

    logger.info("api_started", services=state.services)
    yield
    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    if change_stream_task is not None:
        change_stream_task.cancel()
        try:
            await change_stream_task
        except asyncio.CancelledError:
            pass
    await profiler.disconnect()
    await merger.disconnect()
    if state.mongo:
        state.mongo.close()
    if state.redis:
        await state.redis.close()
    logger.info("api_stopped")


app = FastAPI(
    title="CDP Agentic Ad Engine API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if limiter is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ──────────────────────────────────────────────
# Background Event Consumer
# ──────────────────────────────────────────────

async def _event_consumer_loop() -> None:
    """Background task that processes events from the in-memory queue.

    Validates, logs, and (if MongoDB is available) persists events.
    This is a simplified inline version of ``event_consumer.py`` for
    the API context.  For full throughput the standalone consumer
    should be deployed alongside.
    """
    logger.info("event_consumer_loop_started")
    while True:
        try:
            event = await state.event_queue.get()
            try:
                validated = ClickstreamEvent(**event.model_dump())
            except Exception as exc:
                logger.warning("event_validation_failed", error=str(exc))
                state.event_queue.task_done()
                continue

            logger.debug("event_consumed", session_id=validated.session_id, event_type=validated.event_type)

            if state.mongo:
                try:
                    db = state.mongo[MONGODB_DATABASE]
                    coll = db["raw_events"]
                    await coll.insert_one(validated.model_dump(mode="json"))
                except Exception as exc:
                    logger.error("event_persist_failed", error=str(exc))

            state.event_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("event_consumer_error", error=str(exc))


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _get_cached_ad(global_uid: str) -> Optional[AdCreative]:
    """Read a cached ad creative from Redis."""
    if state.redis is None:
        return None
    try:
        raw = await state.redis.get(f"ad:{global_uid}")
        if raw:
            data = json.loads(raw)
            return AdCreative(**data)
    except Exception as exc:
        logger.debug("cache_read_error", error=str(exc))
    return None


async def _set_cached_ad(global_uid: str, creative: AdCreative) -> None:
    """Write an ad creative to Redis cache with TTL."""
    if state.redis is None:
        return
    try:
        data = creative.model_dump(mode="json")
        await state.redis.setex(f"ad:{global_uid}", REDIS_AD_CACHE_TTL, json.dumps(data))
    except Exception as exc:
        logger.debug("cache_write_error", error=str(exc))


async def _get_mongo_ad(global_uid: str) -> Optional[AdCreative]:
    """Read the last generated ad creative from MongoDB."""
    if state.mongo is None:
        return None
    try:
        db = state.mongo[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        doc = await coll.find_one(
            {"_id": global_uid},
            projection={"last_ad_creative": 1, "last_ad_generated_at": 1},
        )
        if doc and doc.get("last_ad_creative"):
            return AdCreative(**doc["last_ad_creative"])
    except Exception as exc:
        logger.warning("mongo_ad_read_error", error=str(exc))
    return None


async def _ad_needs_refresh(global_uid: str) -> bool:
    """Return True if the profile's last ad is older than the refresh window."""
    if state.mongo is None:
        return True
    try:
        db = state.mongo[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        doc = await coll.find_one(
            {"_id": global_uid},
            projection={"last_ad_generated_at": 1},
        )
        if doc is None:
            return True
        last_gen = doc.get("last_ad_generated_at")
        if last_gen is None:
            return True
        if isinstance(last_gen, str):
            last_gen = datetime.fromisoformat(last_gen.replace("Z", "+00:00").replace(" ", "T"))
        age = datetime.now(timezone.utc) - last_gen.replace(tzinfo=timezone.utc) if last_gen.tzinfo is None else datetime.now(timezone.utc) - last_gen
        return age > AD_REFRESH_TD
    except Exception:
        return True


async def _generate_ad_background(global_uid: str) -> None:
    """Background task: generate and cache a new ad creative."""
    if global_uid in state._refresh_in_progress:
        logger.debug("refresh_already_in_progress", global_uid=global_uid)
        return

    state._refresh_in_progress.add(global_uid)
    try:
        from agents.ad_creative import generate_ad
        creative = await generate_ad(global_uid)
        await _set_cached_ad(global_uid, creative)
        logger.info("ad_refreshed", global_uid=global_uid)
    except Exception as exc:
        logger.error("ad_refresh_failed", global_uid=global_uid, error=str(exc))
    finally:
        state._refresh_in_progress.discard(global_uid)


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/ad/{global_uid}", response_model=AdResponse)
@limiter.limit("1000/minute") if limiter else (lambda f: f)
async def get_ad(global_uid: str, request: Request, background_tasks: BackgroundTasks):
    """Return the latest ad creative for a user.

    Priority:
        1. Redis cache (fastest, sub-ms)
        2. MongoDB stored creative (serves stale + refreshes in background)
        3. Synchronous generation (first time) — slow path
    """
    start = time.monotonic()

    # 1. Try Redis cache
    cached = await _get_cached_ad(global_uid)
    if cached:
        latency = (time.monotonic() - start) * 1000
        state.record_request(latency, cache_hit=True)
        return AdResponse(
            global_uid=global_uid,
            creative=cached,
            cached=True,
            generated_at=cached.generated_at,
        )

    # 2. Try MongoDB stored creative
    mongo_ad = await _get_mongo_ad(global_uid)
    if mongo_ad:
        latency = (time.monotonic() - start) * 1000
        state.record_request(latency, cache_hit=False)
        # Check if refresh is needed
        needs_refresh = await _ad_needs_refresh(global_uid)
        if needs_refresh:
            background_tasks.add_task(_generate_ad_background, global_uid)
        # Prime the cache
        await _set_cached_ad(global_uid, mongo_ad)
        return AdResponse(
            global_uid=global_uid,
            creative=mongo_ad,
            cached=True,
            generated_at=mongo_ad.generated_at,
        )

    # 3. No cached ad — generate synchronously (first time, slow)
    logger.info("first_time_ad_generation", global_uid=global_uid)
    try:
        from agents.ad_creative import generate_ad
        creative = await generate_ad(global_uid)
        await _set_cached_ad(global_uid, creative)
        latency = (time.monotonic() - start) * 1000
        state.record_request(latency, cache_hit=False)
        return AdResponse(
            global_uid=global_uid,
            creative=creative,
            cached=False,
            generated_at=creative.generated_at,
        )
    except Exception as exc:
        logger.error("ad_generation_failed", global_uid=global_uid, error=str(exc))
        fallback = AdCreative(
            headline="Discover Top Products",
            body="Check out products curated just for you.",
            cta="Browse Now",
            product_links=[],
        )
        return AdResponse(
            global_uid=global_uid,
            creative=fallback,
            cached=False,
            generated_at=fallback.generated_at,
        )


@app.post("/event", response_model=EventIngestResponse)
@limiter.limit("1000/minute") if limiter else (lambda f: f)
async def post_event(request: Request, event: ClickstreamEvent):
    """Ingest a clickstream event for processing."""
    event_id = str(uuid.uuid4())
    try:
        await state.event_queue.put(event)
        logger.debug("event_queued", event_id=event_id, session_id=event.session_id)
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="Event queue full, try again later")

    return EventIngestResponse(
        accepted=True,
        event_id=event_id,
        message="Event queued for processing",
    )


@app.get("/profile/{global_uid}", response_model=ProfileResponse)
@limiter.limit("1000/minute") if limiter else (lambda f: f)
async def get_profile(global_uid: str, request: Request):
    """Return the full unified profile for a user."""
    if state.mongo is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")

    db = state.mongo[MONGODB_DATABASE]
    coll = db[MONGODB_PROFILE_COLLECTION]
    doc = await coll.find_one({"_id": global_uid})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Profile {global_uid} not found")

    profile = UnifiedProfile(**doc)
    return ProfileResponse(profile=profile)


@app.get("/health", response_model=HealthStatus)
async def health():
    """Return the health status of all dependencies."""
    return HealthStatus(
        status="ok" if all(v == "ok" for v in state.services.values()) else "degraded",
        services=dict(state.services),
    )


@app.get("/metrics")
async def metrics():
    """Return API request metrics."""
    return {
        "total_requests": state.total_requests,
        "cache_hits": state.cache_hits,
        "cache_misses": state.cache_misses,
        "cache_hit_rate": round(state.cache_hit_rate, 4),
        "avg_latency_ms": round(state.avg_latency_ms, 2),
        "queue_size": state.event_queue.qsize(),
        "refresh_in_progress": len(state._refresh_in_progress),
    }


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    """Run the API server with uvicorn."""
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
