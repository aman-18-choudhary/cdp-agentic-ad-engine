#!/usr/bin/env python3
"""Intent Profiler Agent.

Triggered by MongoDB Change Stream events from the Profile Merger,
this agent uses LangChain + Ollama to analyse a
unified cross-platform user profile and produce a concise semantic
intent summary covering:

- Product category / product the user is actively researching
- Apparent price sensitivity or budget range
- Behavioral signals (repeat views, cart abandons, comparison shopping,
  cross-platform behaviour)

The summary is written back to ``unified_profiles.last_intent_profile``
in MongoDB.

Can also be invoked directly via :func:`profile_user` for on-demand
profiling.

Usage:
    python agents/intent_profiler.py  # self-test with mock data
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

try:
    from langchain_ollama import ChatOllama
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
except ImportError:
    ChatOllama = None

from common.logging import setup_logging, get_logger
from common.settings import settings

logger = get_logger("agents.intent_profiler")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", settings.ollama_chat_model)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "cdp")
MONGODB_PROFILE_COLLECTION = os.getenv("MONGODB_PROFILE_COLLECTION", "unified_profiles")

MAX_RETRIES = 3
RETRY_DELAY_S = 2.0

SYSTEM_PROMPT = """You are a behavioural analyst for an e-commerce platform.
You will receive a unified cross-platform user profile as JSON.
Your job is to write a concise semantic intent summary (2-3 sentences max)
that captures:
- What category/product the user is actively researching
- Their apparent price sensitivity or budget range
- Any behavioural signals (repeat views, cart abandons, comparison behaviour,
  cross-platform activity)

Output ONLY the intent summary as plain text. No JSON. No preamble."""


# ──────────────────────────────────────────────
# Product Catalog Helper
# ──────────────────────────────────────────────

def _load_product_catalog(path: str = "data/product_catalog.json") -> Dict[str, Dict[str, Any]]:
    """Load the product catalog and return a dict keyed by ``product_id``."""
    if not os.path.exists(path):
        logger.warning("product_catalog_not_found", path=path)
        return {}
    with open(path) as f:
        products = json.load(f)
    return {p["product_id"]: p for p in products}


# ──────────────────────────────────────────────
# Context Builder
# ──────────────────────────────────────────────

def build_context_from_profile(
    profile: Dict[str, Any],
    product_map: Dict[str, Dict[str, Any]],
) -> str:
    """Convert a unified profile document into a contextual prompt for the LLM.

    Extracts session summary, event statistics, product categories viewed,
    price ranges, and behavioural signals.
    """
    sections: List[str] = []

    # ── Profile overview
    uid = profile.get("_id", "unknown")
    sessions = profile.get("sessions", [])
    devices = profile.get("devices", [])
    locations = profile.get("locations", [])
    event_history = profile.get("event_history", [])
    previous_intent = profile.get("last_intent_profile")

    sections.append(f"Global UID: {uid}")
    sections.append(f"Platforms: {', '.join(s['platform'] for s in sessions) if sessions else 'N/A'}")
    sections.append(f"Total sessions: {len(sessions)}")
    sections.append(f"Devices: {', '.join(devices) if devices else 'N/A'}")
    sections.append(f"Locations: {', '.join(loc.get('city', '') for loc in locations) if locations else 'N/A'}")
    if previous_intent:
        sections.append(f"Previous intent: {previous_intent}")

    # ── Event statistics
    event_types: Dict[str, int] = {"view": 0, "cart": 0, "purchase": 0}
    product_ids_seen: set = set()
    session_events: Dict[str, List[str]] = {}

    for ev in event_history:
        etype = ev.get("event_type", "view")
        event_types[etype] = event_types.get(etype, 0) + 1
        pid = ev.get("product_id", "")
        if pid:
            product_ids_seen.add(pid)
        sid = ev.get("session_id", "")
        if sid not in session_events:
            session_events[sid] = []
        session_events[sid].append(etype)

    sections.append(f"Total events: {len(event_history)}")
    sections.append(f"  Views: {event_types.get('view', 0)}")
    sections.append(f"  Cart adds: {event_types.get('cart', 0)}")
    sections.append(f"  Purchases: {event_types.get('purchase', 0)}")
    sections.append(f"Unique products interacted with: {len(product_ids_seen)}")

    # ── Product categories & price ranges
    categories_seen: Dict[str, int] = {}
    prices_seen: List[float] = []

    for pid in product_ids_seen:
        product = product_map.get(pid)
        if product:
            cat = product.get("category", "unknown")
            categories_seen[cat] = categories_seen.get(cat, 0) + 1
            prices_seen.append(product.get("price", 0.0))

    if categories_seen:
        sorted_cats = sorted(categories_seen.items(), key=lambda x: -x[1])
        sections.append(f"Product categories browsed: {', '.join(f'{c}({n})' for c, n in sorted_cats)}")
    if prices_seen:
        sections.append(f"Price range seen: ${min(prices_seen):.2f} – ${max(prices_seen):.2f}")
        sections.append(f"Average price: ${sum(prices_seen) / len(prices_seen):.2f}")

    # ── Behavioural signals
    for sid, types in session_events.items():
        if "cart" in types and "purchase" not in types:
            sections.append(f"[Signal] Cart abandon in session {sid[:16]}")

    # Sessions with many views
    for sid, types in session_events.items():
        view_count = types.count("view")
        if view_count >= 3:
            sections.append(f"[Signal] High-intent browsing ({view_count} views) in session {sid[:16]}")

    # Cross-platform signal
    platforms_involved = {s.get("platform") for s in sessions}
    if len(platforms_involved) > 1:
        sections.append(
            f"[Signal] Cross-platform activity: {', '.join(platforms_involved)}"
        )

    # Repeat product views (same product in multiple sessions)
    product_sessions: Dict[str, set] = {}
    for ev in event_history:
        pid = ev.get("product_id", "")
        sid = ev.get("session_id", "")
        if pid and sid:
            if pid not in product_sessions:
                product_sessions[pid] = set()
            product_sessions[pid].add(sid)
    repeat_products = {pid: sessions for pid, sessions in product_sessions.items() if len(sessions) >= 2}
    if repeat_products:
        top_repeats = sorted(repeat_products.items(), key=lambda x: -len(x[1]))[:3]
        repeat_names = []
        for pid, _ in top_repeats:
            p = product_map.get(pid)
            repeat_names.append(p["name"] if p else pid[:12])
        sections.append(f"[Signal] Repeat product interest: {', '.join(repeat_names)}")

    return "\n".join(sections)


# ──────────────────────────────────────────────
# Profiler
# ──────────────────────────────────────────────

class IntentProfiler:
    """Analyse unified profiles and produce semantic intent summaries."""

    def __init__(
        self,
        mongo_uri: str = MONGODB_URI,
        ollama_base_url: str = OLLAMA_BASE_URL,
        ollama_model: str = OLLAMA_CHAT_MODEL,
        catalog_path: str = "data/product_catalog.json",
    ) -> None:
        self._mongo_uri = mongo_uri
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._product_map = _load_product_catalog(catalog_path)
        self._mongo_client: Optional[AsyncIOMotorClient] = None
        self._llm: Optional[ChatOllama] = None

    # ── Connection lifecycle ─────────────────────

    async def connect(self) -> None:
        """Connect to MongoDB and initialise the LLM."""
        if AsyncIOMotorClient is not None:
            self._mongo_client = AsyncIOMotorClient(self._mongo_uri)
            logger.info("mongodb_connected", uri=self._mongo_uri)

        if ChatOllama is not None:
            self._llm = ChatOllama(
                base_url=self._ollama_base_url,
                model=self._ollama_model,
                temperature=0.3,
                num_predict=512,
            )
            logger.info(
                "llm_initialised",
                model=self._ollama_model,
                base_url=self._ollama_base_url,
            )

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._mongo_client:
            self._mongo_client.close()
            logger.info("mongodb_disconnected")

    # ── Core profiling ───────────────────────────

    async def profile_user(self, global_uid: str) -> Optional[str]:
        """Produce a semantic intent summary for a single user.

        Fetches the unified profile from MongoDB, builds an LLM context,
        calls the model (with retry), and persists the result back to
        the profile document.

        Returns the intent summary string, or ``None`` on failure.
        """
        profile = await self._fetch_profile(global_uid)
        if profile is None:
            logger.error("profile_not_found", global_uid=global_uid)
            return None

        context = build_context_from_profile(profile, self._product_map)
        logger.debug("llm_context_built", global_uid=global_uid, context_length=len(context))

        intent = await self._call_llm_with_retry(context)
        if intent is None:
            logger.error("llm_failed_all_retries", global_uid=global_uid)
            return None

        await self._write_intent(global_uid, intent)
        logger.info(
            "profile_completed",
            global_uid=global_uid,
            intent_length=len(intent),
            intent_snippet=intent[:80],
        )
        return intent

    # ── Internal helpers ─────────────────────────

    async def _fetch_profile(self, global_uid: str) -> Optional[Dict[str, Any]]:
        """Fetch a unified profile by its ``_id`` from MongoDB."""
        if self._mongo_client is None:
            logger.warning("no_mongo_connection, using mock")
            return None

        db = self._mongo_client[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        doc = await coll.find_one({"_id": global_uid})
        if doc:
            logger.debug("profile_fetched", global_uid=global_uid, events=len(doc.get("event_history", [])))
        else:
            logger.warning("profile_not_in_mongo", global_uid=global_uid)
        return doc

    async def _call_llm_with_retry(self, context: str) -> Optional[str]:
        """Call the LLM with the built context, retrying on failure."""
        if self._llm is None:
            logger.warning("llm_not_available, returning mock intent")
            return await self._mock_intent(context)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "User Profile:\n\n{context}"),
        ])
        chain = prompt | self._llm | StrOutputParser()

        last_error: Optional[str] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug("llm_call", attempt=attempt)
                result = await chain.ainvoke({"context": context})
                cleaned = result.strip()
                if cleaned:
                    return cleaned
                last_error = "empty_response"
            except Exception as exc:
                last_error = str(exc)
                logger.warning("llm_retry", attempt=attempt, error=last_error)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_S * attempt)
        logger.error("llm_all_retries_exhausted", last_error=last_error)
        return None

    async def _mock_intent(self, context: str) -> str:
        """Fallback when no LLM is connected.  Extracts a simple heuristic summary."""
        lines = context.lower().split("\n")
        categories = [line for line in lines if "categories" in line]
        prices = [line for line in lines if "price" in line]
        signals = [line for line in lines if "[signal]" in line]
        cat_str = categories[0] if categories else "various products"
        price_str = prices[0] if prices else ""
        signal_summary = "; ".join(s.strip() for s in signals[:2]) if signals else ""
        intent = f"User is researching {cat_str.split(':')[-1].strip() if ':' in cat_str else cat_str}"
        if price_str:
            intent += f" with {price_str}"
        if signal_summary:
            intent += f". Signals: {signal_summary}"
        return intent + "."

    async def _write_intent(self, global_uid: str, intent: str) -> None:
        """Write the intent summary back to MongoDB."""
        if self._mongo_client is None:
            logger.info("mock_write_intent", global_uid=global_uid, intent=intent)
            return

        db = self._mongo_client[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        await coll.update_one(
            {"_id": global_uid},
            {
                "$set": {
                    "last_intent_profile": intent,
                    "last_updated": datetime.utcnow(),
                },
            },
        )
        logger.debug("intent_written", global_uid=global_uid)

    # ── Change Stream callback ───────────────────

    async def change_stream_callback(self, profile: Dict[str, Any]) -> None:
        """Callback intended for use by the Profile Merger Change Stream.

        Extracts the ``_id`` from the full document and runs profiling.
        """
        global_uid = profile.get("_id")
        if not global_uid:
            logger.warning("change_stream_missing_uid")
            return
        logger.info("change_stream_trigger", global_uid=global_uid)
        await self.profile_user(str(global_uid))


# ──────────────────────────────────────────────
# Standalone callable
# ──────────────────────────────────────────────

async def profile_user(
    global_uid: str,
    mongo_uri: str = MONGODB_URI,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_model: str = OLLAMA_CHAT_MODEL,
) -> Optional[str]:
    """Convenience wrapper — connect, profile, disconnect."""
    profiler = IntentProfiler(
        mongo_uri=mongo_uri,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )
    try:
        await profiler.connect()
        return await profiler.profile_user(global_uid)
    finally:
        await profiler.disconnect()


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

async def _is_ollama_available(model: str = OLLAMA_CHAT_MODEL) -> bool:
    """Quick check whether Ollama is running with the required model."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(m.get("name", "").startswith(model) for m in models)
    except Exception:
        pass
    return False


async def _self_test() -> None:
    setup_logging(service_name="intent-profiler-self-test")

    product_map = _load_product_catalog()

    mock_profile: Dict[str, Any] = {
        "_id": "test_global_001",
        "sessions": [
            {"platform": "A", "session_id": "sess_a_001", "linked_at": "2024-03-15T14:30:00Z", "method": "probabilistic", "confidence": 0.82},
            {"platform": "B", "session_id": "sess_b_001", "linked_at": "2024-03-15T15:00:00Z", "method": "probabilistic", "confidence": 0.85},
        ],
        "event_history": [
            {"session_id": "sess_a_001", "event_type": "view", "product_id": "prod_0001", "platform": "A"},
            {"session_id": "sess_a_001", "event_type": "view", "product_id": "prod_0002", "platform": "A"},
            {"session_id": "sess_a_001", "event_type": "view", "product_id": "prod_0003", "platform": "A"},
            {"session_id": "sess_a_001", "event_type": "cart", "product_id": "prod_0002", "platform": "A"},
            {"session_id": "sess_b_001", "event_type": "view", "product_id": "prod_0004", "platform": "B"},
            {"session_id": "sess_b_001", "event_type": "view", "product_id": "prod_0001", "platform": "B"},
            {"session_id": "sess_b_001", "event_type": "cart", "product_id": "prod_0001", "platform": "B"},
        ],
        "devices": ["mobile", "desktop"],
        "locations": [{"city": "New York", "country": "US"}],
        "last_intent_profile": None,
    }

    context = build_context_from_profile(mock_profile, product_map)
    logger.info("context_built", context=context)

    profiler = IntentProfiler()
    await profiler.connect()

    ollama_ok = await _is_ollama_available()
    if ollama_ok:
        intent = await profiler._call_llm_with_retry(context)
    else:
        logger.info("ollama_not_available_using_mock")
        intent = await profiler._mock_intent(context)

    print()
    print("=" * 72)
    print("  INTENT PROFILER SELF-TEST")
    print("=" * 72)
    print(f"\n  Context:\n{context}\n")
    print(f"  Generated intent:\n  {intent}\n")
    print("=" * 72)

    if intent and len(intent) > 20:
        print("  ✅ Self-test passed.\n")
    else:
        print("  ⚠️  Self-test completed (mock mode if no LLM available).\n")


def main() -> None:
    asyncio.run(_self_test())


if __name__ == "__main__":
    main()
