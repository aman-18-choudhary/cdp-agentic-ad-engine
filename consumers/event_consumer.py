#!/usr/bin/env python3
"""Event consumer for the CDP Agentic Ad Engine.

Consumes clickstream events from both Redpanda topics (platform-a-events
and platform-b-events), validates them against the
:class:`~common.schemas.ClickstreamEvent` schema, writes raw JSONL to
MinIO (S3-compatible data lake), and forwards validated events to the
Identity Resolution Engine via an internal async queue.

Usage:
    python consumers/event_consumer.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple

import structlog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except ImportError:
    AIOKafkaConsumer = None
    AIOKafkaProducer = None

try:
    import boto3
    from botocore.config import Config as BotoConfig
except ImportError:
    boto3 = None

from common.logging import setup_logging, get_logger
from common.schemas import ClickstreamEvent
from uid_engine.merger import ProfileMerger

logger = get_logger("event_consumer")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

class ConsumerConfig:
    """Runtime configuration for the event consumer, read from env / CLI."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.bootstrap_servers: str = args.bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:19093"
        )
        self.topics: List[str] = args.topics or [
            os.getenv("KAFKA_TOPIC_PLATFORM_A", "platform-a-events"),
            os.getenv("KAFKA_TOPIC_PLATFORM_B", "platform-b-events"),
        ]
        self.group_id: str = args.group_id or os.getenv(
            "KAFKA_CONSUMER_GROUP", "cdp-event-consumer"
        )

        # MinIO / S3
        self.s3_endpoint: str = args.s3_endpoint or os.getenv(
            "S3_ENDPOINT_URL", "http://localhost:9000"
        )
        self.s3_access_key: str = args.s3_access_key or os.getenv(
            "S3_ACCESS_KEY_ID", "cdpadmin"
        )
        self.s3_secret_key: str = args.s3_secret_key or os.getenv(
            "S3_SECRET_ACCESS_KEY", "cdpadmin123"
        )
        self.s3_bucket: str = args.s3_bucket or os.getenv(
            "S3_BUCKET_RAW_EVENTS", "raw-events"
        )
        self.s3_region: str = args.s3_region or os.getenv("S3_REGION", "us-east-1")

        self.max_batch_size: int = args.max_batch_size or 100
        self.flush_interval: float = args.flush_interval or 5.0

        # MongoDB (for profile persistence via UID engine)
        self.mongo_uri: str = args.mongo_uri or os.getenv(
            "MONGODB_URI", "mongodb://localhost:27017/?directConnection=true"
        )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Event consumer — reads from Redpanda, writes to MinIO, forwards to UID engine.",
    )
    parser.add_argument("--bootstrap-servers", type=str, default=None)
    parser.add_argument("--topics", type=str, nargs="+", default=None)
    parser.add_argument("--group-id", type=str, default=None)
    parser.add_argument("--s3-endpoint", type=str, default=None)
    parser.add_argument("--s3-access-key", type=str, default=None)
    parser.add_argument("--s3-secret-key", type=str, default=None)
    parser.add_argument("--s3-bucket", type=str, default=None)
    parser.add_argument("--s3-region", type=str, default=None)
    parser.add_argument("--max-batch-size", type=int, default=100)
    parser.add_argument("--flush-interval", type=float, default=5.0)
    parser.add_argument("--mongo-uri", type=str, default=None)
    return parser.parse_args(argv)


# ──────────────────────────────────────────────
# S3 / MinIO Writer
# ──────────────────────────────────────────────

class S3Writer:
    """Writes validated events as JSONL to MinIO partitioned by platform/date/hour."""

    def __init__(self, cfg: ConsumerConfig) -> None:
        self.cfg = cfg
        self._client = None
        self._buffer: Dict[str, List[str]] = {}

    async def start(self) -> None:
        """Create S3 client and ensure the bucket exists."""
        if boto3 is None:
            logger.error("boto3 not installed — S3 writes disabled")
            return

        loop = asyncio.get_running_loop()
        self._client = await loop.run_in_executor(
            None,
            lambda: boto3.client(
                "s3",
                endpoint_url=self.cfg.s3_endpoint,
                aws_access_key_id=self.cfg.s3_access_key,
                aws_secret_access_key=self.cfg.s3_secret_key,
                region_name=self.cfg.s3_region,
                config=BotoConfig(signature_version="s3v4", connect_timeout=5, read_timeout=10),
            ),
        )

        # Ensure bucket exists
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.head_bucket(Bucket=self.cfg.s3_bucket),
            )
            logger.info("bucket_exists", bucket=self.cfg.s3_bucket)
        except Exception:
            await loop.run_in_executor(
                None,
                lambda: self._client.create_bucket(Bucket=self.cfg.s3_bucket),
            )
            logger.info("bucket_created", bucket=self.cfg.s3_bucket)

    async def write_event(self, event: ClickstreamEvent) -> None:
        """Buffer an event and flush if batch size reached."""
        platform = event.platform.value
        dt = event.event_time
        hour = dt.strftime("%H")
        date_prefix = dt.strftime("%Y-%m-%d")
        key = f"raw-events/{platform}/{date_prefix}/{hour}/events.jsonl"
        line = event.model_dump_json() + "\n"

        if key not in self._buffer:
            self._buffer[key] = []
        self._buffer[key].append(line)

        if len(self._buffer[key]) >= self.cfg.max_batch_size:
            await self._flush_key(key)

    async def flush_all(self) -> None:
        """Flush all buffered keys."""
        for key in list(self._buffer.keys()):
            await self._flush_key(key)

    async def _flush_key(self, key: str) -> None:
        """Write buffered lines for a single S3 key."""
        lines = self._buffer.pop(key, [])
        if not lines or self._client is None:
            return

        data = "".join(lines).encode("utf-8")
        loop = asyncio.get_running_loop()

        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    Bucket=self.cfg.s3_bucket,
                    Key=key,
                    Body=data,
                    ContentType="application/x-ndjson",
                ),
            )
            logger.debug("s3_write_ok", key=key, bytes=len(data), lines=len(lines))
        except Exception as exc:
            logger.error("s3_write_failed", key=key, error=str(exc))
            # Re-buffer for retry
            self._buffer[key] = lines + self._buffer.get(key, [])


# ──────────────────────────────────────────────
# UID Engine Worker — drains queue → resolve → persist
# ──────────────────────────────────────────────

async def uid_engine_worker(
    uid_queue: UIDEngineQueue,
    merger: ProfileMerger,
    flush_interval: int = 10,
) -> None:
    """Background worker that drains the UID queue and runs identity resolution.

    Collects events into session dicts, runs deterministic matching
    on cross-platform pairs, and persists profiles via ProfileMerger.

    Uses ``asyncio.wait_for`` with a ``flush_interval`` timeout so that
    accumulated sessions are persisted even when no new events arrive
    (the original blocking ``async for`` loop would sleep forever once
    the queue drained, causing the flush timer never to fire).
    """
    from uid_engine.deterministic import match_sessions
    from uid_engine.probabilistic import score_sessions as prob_match_sessions

    sessions: Dict[str, Dict[str, Any]] = {}
    last_flush = datetime.now(timezone.utc)

    try:
        while True:
            now = datetime.now(timezone.utc)
            elapsed = (now - last_flush).total_seconds()
            remaining = max(0.0, flush_interval - elapsed)

            try:
                event = await asyncio.wait_for(
                    uid_queue._queue.get(), timeout=remaining
                )
                uid_queue._queue.task_done()
            except asyncio.TimeoutError:
                # Periodic flush: no events arrived within the window
                if sessions:
                    logger.info("worker_flush_started", sessions=len(sessions))
                    await _flush_matches(
                        sessions, merger, match_sessions, prob_match_sessions
                    )
                    logger.info("worker_flush_completed")
                last_flush = datetime.now(timezone.utc)
                continue

            sid = event.session_id

            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "platform": event.platform.value,
                    "device_type": event.device_type.value,
                    "hashed_email": event.hashed_email,
                    "user_agent": event.user_agent,
                    "ip_range": event.ip_range,
                    "city": event.location.city if event.location else "",
                    "country": event.location.country if event.location else "",
                    "events": [],
                }
            sessions[sid]["events"].append(event)
            sessions[sid]["event_times"] = [e.event_time for e in sessions[sid]["events"]]

    except asyncio.CancelledError:
        # Shutdown safety: persist any remaining sessions
        if sessions:
            logger.info("final_shutdown_flush", sessions=len(sessions))
            await _flush_matches(
                sessions, merger, match_sessions, prob_match_sessions
            )
            logger.info("final_shutdown_flush_completed")
        raise


async def _flush_matches(
    sessions: Dict[str, Dict[str, Any]],
    merger: ProfileMerger,
    det_match_fn,
    prob_match_fn,
) -> None:
    """Run matching on collected sessions and persist profiles."""
    seen: Set[str] = set()
    session_list = list(sessions.values())

    for i, sa in enumerate(session_list):
        if sa["session_id"] in seen:
            continue
        seen.add(sa["session_id"])

        # Try deterministic match against all other sessions
        matched = False
        for j, sb in enumerate(session_list):
            if sb["session_id"] in seen:
                continue
            if sa["platform"] == sb["platform"]:
                continue

            result = det_match_fn(sa, sb)
            if result.match:
                score = result.score if result.score is not None else 1.0
                uid = await merger.get_or_create_global_uid(
                    sa, matched_session={"_global_uid": result.global_uid},
                    method=result.method, confidence=score,
                )
                await merger.get_or_create_global_uid(
                    sb, matched_session={"_global_uid": uid},
                    method=result.method, confidence=score,
                )
                seen.add(sb["session_id"])
                matched = True
                break

        if not matched:
            # Probabilistic match
            for j, sb in enumerate(session_list):
                if sb["session_id"] in seen:
                    continue
                if sa["platform"] == sb["platform"]:
                    continue
                result = prob_match_fn(sa, sb)
                if result.match:
                    score = result.score if result.score is not None else 0.0
                    uid = await merger.get_or_create_global_uid(
                        sa, matched_session={"_global_uid": result.global_uid},
                        method=result.method, confidence=score,
                    )
                    await merger.get_or_create_global_uid(
                        sb, matched_session={"_global_uid": uid},
                        method=result.method, confidence=score,
                    )
                    seen.add(sb["session_id"])
                    matched = True
                    break

        if not matched:
            await merger.get_or_create_global_uid(sa)

    # Remove matched sessions from the buffer
    for sid in list(seen):
        sessions.pop(sid, None)


# ──────────────────────────────────────────────
# UID Engine Forwarder (internal async queue)
# ──────────────────────────────────────────────

class UIDEngineQueue:
    """Async queue that forwards validated events to the Identity Resolution Engine.

    The UID Engine processor (Module 2) will consume from this queue
    via :meth:`consume` in a background task.
    """

    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[ClickstreamEvent] = asyncio.Queue(maxsize=maxsize)

    async def push(self, event: ClickstreamEvent) -> None:
        await self._queue.put(event)

    async def consume(self) -> AsyncIterator[ClickstreamEvent]:
        while True:
            event = await self._queue.get()
            yield event
            self._queue.task_done()

    @property
    def qsize(self) -> int:
        return self._queue.qsize()


# ──────────────────────────────────────────────
# Event Validator
# ──────────────────────────────────────────────

def validate_event(raw: Dict[str, Any]) -> Optional[ClickstreamEvent]:
    """Validate a raw JSON event against the ClickstreamEvent schema.

    Returns None if validation fails (and logs the error).
    """
    try:
        return ClickstreamEvent(**raw)
    except Exception as exc:
        logger.warning("event_validation_failed", error=str(exc), raw=raw)
        return None


# ──────────────────────────────────────────────
# Consumer Loop
# ──────────────────────────────────────────────

async def consume_loop(
    cfg: ConsumerConfig,
    uid_queue: UIDEngineQueue,
    s3_writer: S3Writer,
) -> None:
    """Main consumer loop that reads from both Kafka topics."""
    consumer = AIOKafkaConsumer(
        *cfg.topics,
        bootstrap_servers=cfg.bootstrap_servers,
        group_id=cfg.group_id,
        enable_auto_commit=True,
        auto_commit_interval_ms=5000,
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        key_deserializer=lambda m: m.decode("utf-8") if m else None,
        max_poll_records=cfg.max_batch_size,
    )

    await consumer.start()
    logger.info(
        "consumer_started",
        topics=cfg.topics,
        group=cfg.group_id,
        bootstrap=cfg.bootstrap_servers,
    )

    stats = {"consumed": 0, "valid": 0, "invalid": 0, "s3_written": 0, "queued": 0}
    last_log = datetime.now(timezone.utc)

    try:
        async for msg in consumer:
            stats["consumed"] += 1

            if msg.value is None:
                stats["invalid"] += 1
                continue

            validated = validate_event(msg.value)
            if validated is None:
                stats["invalid"] += 1
                continue

            stats["valid"] += 1

            # Write to S3 data lake
            try:
                await s3_writer.write_event(validated)
                stats["s3_written"] += 1
            except Exception as exc:
                logger.error("s3_write_error", error=str(exc), event=validated.session_id)

            # Forward to UID engine
            try:
                await uid_queue.push(validated)
                stats["queued"] += 1
            except asyncio.QueueFull:
                logger.warning("uid_queue_full", qsize=uid_queue.qsize)
                # Drop event — UID engine will catch up from S3 replay
                stats["queued"] -= 1

            # Periodic stats log
            now = datetime.now(timezone.utc)
            if (now - last_log).total_seconds() >= 30:
                logger.info("consumer_stats", **stats)
                last_log = now

    except asyncio.CancelledError:
        logger.info("consumer_cancelled")
    except Exception as exc:
        logger.error("consumer_error", error=str(exc))
        raise
    finally:
        # Flush remaining S3 writes
        await s3_writer.flush_all()
        await consumer.stop()
        logger.info("consumer_stopped", final=stats)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def main_async() -> None:
    args = parse_args()
    cfg = ConsumerConfig(args)

    setup_logging(service_name="event-consumer")
    logger.info("initializing", config=vars(cfg))

    uid_queue = UIDEngineQueue()
    s3_writer = S3Writer(cfg)
    merger = ProfileMerger(mongo_uri=cfg.mongo_uri)

    await s3_writer.start()
    await merger.connect()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("signal_received", signal="SIGINT/SIGTERM")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    consumer_task = asyncio.create_task(
        consume_loop(cfg=cfg, uid_queue=uid_queue, s3_writer=s3_writer)
    )
    uid_worker_task = asyncio.create_task(
        uid_engine_worker(uid_queue=uid_queue, merger=merger)
    )

    done, _ = await asyncio.wait(
        [consumer_task, uid_worker_task, asyncio.create_task(stop_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_event.is_set():
        consumer_task.cancel()
        uid_worker_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        try:
            await uid_worker_task
        except asyncio.CancelledError:
            pass

    await merger.disconnect()
    logger.info("shutdown_complete")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
