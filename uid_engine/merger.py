#!/usr/bin/env python3
"""Profile Merger & Change Stream Watcher.

Upserts unified profiles into the MongoDB ``unified_profiles`` collection
and watches for significant user events (cart abandon, 3+ page views,
new purchase) via MongoDB Change Streams to trigger the AI intent
profiler pipeline.

Usage:
    python uid_engine/merger.py  # runs a self-test with in-memory store
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
except ImportError:
    AsyncIOMotorClient = None

from common.logging import setup_logging, get_logger
from common.schemas import (
    ClickstreamEvent,
    DeviceType,
    Location,
    MatchMethod,
    Platform,
    SessionLink,
    UnifiedProfile,
)

logger = get_logger("uid_engine.merger")


# ──────────────────────────────────────────────
# Defaults (override via env)
# ──────────────────────────────────────────────

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "cdp")
MONGODB_PROFILE_COLLECTION = os.getenv("MONGODB_PROFILE_COLLECTION", "unified_profiles")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _to_raw_event_dict(event: Any) -> Dict[str, Any]:
    """Convert a ClickstreamEvent (or raw dict) to a JSON-safe dict for MongoDB.

    Uses ``mode=\"json\"`` to ensure enums → strings, datetimes → ISO strings,
    eliminating Pydantic enum-object fragility in BSON serialization.
    """
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json")
    if isinstance(event, dict):
        return event
    return dict(event)


# ──────────────────────────────────────────────
# Profile Merger
# ──────────────────────────────────────────────

class ProfileMerger:
    """Manages upsert of unified profiles into MongoDB and Change Streams.

    Usage::

        merger = ProfileMerger()
        await merger.connect()
        uid = await merger.get_or_create_global_uid(session_a, session_b, method)
        await merger.start_change_stream(callback)
    """

    def __init__(
        self,
        mongo_uri: str = MONGODB_URI,
        db_name: str = MONGODB_DATABASE,
        coll_name: str = MONGODB_PROFILE_COLLECTION,
    ) -> None:
        self._mongo_uri = mongo_uri
        self._db_name = db_name
        self._coll_name = coll_name
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._coll: Optional[AsyncIOMotorCollection] = None
        self._change_stream_task: Optional[asyncio.Task] = None

    # ── Connection ────────────────────────────────

    async def connect(self) -> None:
        """Establish connection to MongoDB and ensure indexes exist."""
        if AsyncIOMotorClient is None:
            logger.warning("motor not installed — using in-memory fallback")
            return

        self._client = AsyncIOMotorClient(self._mongo_uri)
        self._db = self._client[self._db_name]
        self._coll = self._db[self._coll_name]

        # Ensure indexes
        await self._coll.create_index("sessions.session_id")
        await self._coll.create_index("last_updated")
        logger.info("mongodb_connected", db=self._db_name, coll=self._coll_name)

    async def disconnect(self) -> None:
        """Stop change stream and close MongoDB connection."""
        await self.stop_change_stream()
        if self._client:
            self._client.close()
            logger.info("mongodb_disconnected")

    # ── Profile Operations ────────────────────────

    async def get_or_create_global_uid(
        self,
        session: Dict[str, Any],
        matched_session: Optional[Dict[str, Any]] = None,
        method: MatchMethod = MatchMethod.none,
        confidence: float = 0.0,
    ) -> str:
        """Resolve a session to a ``global_uid``, creating or merging profiles.

        Strategy:
            1. Look for an existing profile linked to this session_id.
            2. If a matched_session is provided (from deterministic/probabilistic
               match), use its ``global_uid`` and merge this session in.
            3. Otherwise create a new profile.

        Returns the ``global_uid`` string.
        """
        session_id = session.get("session_id", "")
        platform_str = session.get("platform", "A")
        platform = Platform(platform_str) if isinstance(platform_str, str) else platform_str

        existing_uid = await self._find_by_session(session_id)
        if existing_uid:
            # Re-entry: still persist events even though session link already exists
            events = session.get("events", [])
            if events:
                event_dicts = [_to_raw_event_dict(ev) for ev in events]
                await self._merge_events_only(existing_uid, event_dicts)
            return existing_uid

        # If a match was found, merge into or create the matched profile
        if matched_session and method != MatchMethod.none:
            matched_uid = matched_session.get("_global_uid")
            if matched_uid:
                exists = await self._find_profile_exists(matched_uid)
                if exists:
                    await self._merge_session(matched_uid, session, platform, method, confidence)
                else:
                    await self._insert_new_profile(matched_uid, session, platform, method, confidence)
                return matched_uid
            # Fall through: generate fresh UID

        # New profile
        profile = UnifiedProfile(
            _id=str(uuid.uuid4()),
            last_updated=datetime.now(timezone.utc),
        )
        uid = await self._insert_new_profile(
            profile.id, session, platform, method, confidence
        )
        return uid

    async def _merge_events_only(
        self,
        global_uid: str,
        event_dicts: List[Dict[str, Any]],
    ) -> None:
        """Append raw event dicts to an existing profile (no session link)."""
        if not event_dicts:
            return
        if self._coll is not None:
            await self._coll.update_one(
                {"_id": global_uid},
                {
                    "$push": {"event_history": {"$each": event_dicts}},
                    "$set": {"last_updated": datetime.now(timezone.utc)},
                },
            )
        else:
            profile = self._in_memory_store.get(global_uid)
            if profile:
                history = profile.setdefault("event_history", [])
                for ed in event_dicts:
                    history.append(ed)
                profile["last_updated"] = datetime.now(timezone.utc).isoformat()

    # ── Internal Helpers ──────────────────────────

    _in_memory_store: Dict[str, Any] = {}

    async def _find_by_session(self, session_id: str) -> Optional[str]:
        """Find an existing profile that already contains this session_id."""
        if self._coll is not None:
            doc = await self._coll.find_one(
                {"sessions.session_id": session_id},
                projection={"_id": 1},
            )
            return doc["_id"] if doc else None
        # In-memory fallback
        for uid, profile in self._in_memory_store.items():
            for s in profile.get("sessions", []):
                if s.get("session_id") == session_id:
                    return uid
        return None

    async def _find_profile_exists(self, uid: str) -> bool:
        """Check if a profile with the given ``_id`` exists in MongoDB."""
        if self._coll is not None:
            doc = await self._coll.find_one({"_id": uid}, projection={"_id": 1})
            return doc is not None
        return uid in self._in_memory_store

    async def _insert_new_profile(
        self,
        uid: str,
        session: Dict[str, Any],
        platform: Platform,
        method: MatchMethod,
        confidence: float,
    ) -> str:
        """Create and persist a new profile with the given uid and session."""
        session_id = session.get("session_id", "")
        profile = UnifiedProfile(
            _id=uid,
            last_updated=datetime.now(timezone.utc),
        )
        profile.add_session(
            session_id=session_id,
            platform=platform,
            method=method,
            confidence=confidence,
        )
        events = session.get("events", [])
        event_dicts = [_to_raw_event_dict(ev) for ev in events]
        for ed in event_dicts:
            profile.event_history.append(dict(ed))

        if self._coll is not None:
            await self._coll.insert_one(profile.model_dump(by_alias=True))
        else:
            self._in_memory_store[profile.id] = profile.model_dump(by_alias=True)

        logger.info(
            "profile_created",
            global_uid=profile.id,
            session_id=session_id,
            platform=platform.value,
            events_added=len(event_dicts),
            event_history_size=len(profile.event_history),
        )
        return profile.id

    async def _merge_session(
        self,
        global_uid: str,
        session: Dict[str, Any],
        platform: Platform,
        method: MatchMethod,
        confidence: float,
    ) -> None:
        """Append a session link and events to an existing profile."""
        session_id = session.get("session_id", "")
        link = SessionLink(
            platform=platform,
            session_id=session_id,
            linked_at=datetime.now(timezone.utc),
            method=method,
            confidence=confidence,
        )
        update: Dict[str, Any] = {
            "$push": {"sessions": link.model_dump(mode="json")},
            "$set": {"last_updated": datetime.now(timezone.utc)},
            "$addToSet": {"devices": session.get("device_type", "desktop")},
        }
        loc = Location(
            city=session.get("city") or session.get("location_city", ""),
            country=session.get("country") or session.get("location_country", ""),
        )
        update["$addToSet"]["locations"] = loc.model_dump(mode="json")

        events = session.get("events", [])
        event_dicts = [_to_raw_event_dict(ev) for ev in events]
        if event_dicts:
            update["$push"]["event_history"] = {"$each": event_dicts}

        if self._coll is not None:
            await self._coll.update_one(
                {"_id": global_uid},
                update,
            )
        else:
            profile = self._in_memory_store.get(global_uid)
            if profile:
                existing_sessions = {s["session_id"] for s in profile.get("sessions", [])}
                if session_id not in existing_sessions:
                    profile["sessions"].append(link.model_dump())
                profile["last_updated"] = datetime.utcnow().isoformat()
                devices = profile.setdefault("devices", [])
                dev = session.get("device_type", "desktop")
                if dev not in devices:
                    devices.append(dev)
                locs = profile.setdefault("locations", [])
                if loc.model_dump() not in locs:
                    locs.append(loc.model_dump())
                history = profile.setdefault("event_history", [])
                for ed in event_dicts:
                    history.append(ed)

        logger.info(
            "session_merged",
            global_uid=global_uid,
            session_id=session_id,
            platform=platform.value,
            method=method.value,
            confidence=confidence,
            events_added=len(event_dicts),
        )

    # ── Change Stream ─────────────────────────────

    async def start_change_stream(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Start an async Change Stream watcher on the unified profiles collection.

        The *callback* is called with the full profile document whenever a
        significant user activity signal is detected:

        - **Cart abandon**: an event of type ``cart`` appears without
          a matching ``purchase`` within the same session.
        - **3+ views**: a session accumulates three or more ``view`` events.
        - **New purchase**: a ``purchase`` event is recorded.

        The callback should be the entry point to the AI intent profiler
        (Module 3).
        """
        if self._coll is None:
            logger.warning("change_stream_unavailable", reason="no_mongo_connection")
            return

        self._change_stream_task = asyncio.create_task(
            self._change_stream_loop(callback),
        )
        logger.info("change_stream_started")

    async def stop_change_stream(self) -> None:
        if self._change_stream_task is not None:
            self._change_stream_task.cancel()
            try:
                await self._change_stream_task
            except asyncio.CancelledError:
                pass
            self._change_stream_task = None
            logger.info("change_stream_stopped")

    async def _change_stream_loop(
        self,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Continuously watch the collection and invoke callback on triggers."""
        if self._coll is None:
            return

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"operationType": "insert"},
                        {"operationType": "update"},
                    ],
                }
            }
        ]

        try:
            async with self._coll.watch(pipeline, full_document="updateLookup") as stream:
                async for change in stream:
                    profile = change.get("fullDocument") or {}
                    if not profile:
                        continue

                    if self._is_significant_event(profile):
                        logger.info(
                            "intent_trigger_detected",
                            global_uid=profile.get("_id"),
                            event_history_size=len(profile.get("event_history", []))
                        )
                        try:
                            await callback(profile)
                        except Exception as exc:
                            logger.error("change_stream_callback_error", error=str(exc))
        except asyncio.CancelledError:
            logger.info("change_stream_loop_cancelled")
        except Exception as exc:
            logger.error("change_stream_loop_error", error=str(exc))

    @staticmethod
    def _is_significant_event(profile: Dict[str, Any]) -> bool:
        """Return True if the profile contains a signal that warrants intent re-profiling."""
        events = profile.get("event_history", [])
        if not events:
            return False

        # Collect signals per session
        session_signals: Dict[str, Dict[str, Any]] = {}
        for ev in events:
            sid = ev.get("session_id", "")
            if sid not in session_signals:
                session_signals[sid] = {"views": 0, "has_cart": False, "has_purchase": False}
            etype = ev.get("event_type", "")
            if etype == "view":
                session_signals[sid]["views"] += 1
            elif etype == "cart":
                session_signals[sid]["has_cart"] = True
            elif etype == "purchase":
                session_signals[sid]["has_purchase"] = True

        for sid, sig in session_signals.items():
            if sig["has_cart"] and not sig["has_purchase"]:
                return True
            if sig["views"] >= 3:
                return True
            if sig["has_purchase"]:
                return True

        return False

    # ── Utility ───────────────────────────────────

    async def get_profile(self, global_uid: str) -> Optional[UnifiedProfile]:
        """Fetch a unified profile by its global_uid."""
        if self._coll is not None:
            doc = await self._coll.find_one({"_id": global_uid})
            if doc:
                return UnifiedProfile(**doc)
        profile_data = self._in_memory_store.get(global_uid)
        return UnifiedProfile(**profile_data) if profile_data else None


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

async def _self_test() -> None:
    setup_logging(service_name="merger-self-test")
    merger = ProfileMerger()

    session_a = {
        "session_id": "test_sess_a",
        "platform": "A",
        "device_type": "mobile",
        "city": "New York",
        "country": "US",
    }
    session_b = {
        "session_id": "test_sess_b",
        "platform": "B",
        "device_type": "mobile",
        "city": "New York",
        "country": "US",
    }

    # Create first profile
    uid_a = await merger.get_or_create_global_uid(session_a)
    logger.info("created_uid_a", uid=uid_a)
    assert uid_a is not None

    # Merge second session into same profile (simulating a match)
    uid_b = await merger.get_or_create_global_uid(
        session_b,
        matched_session={"_global_uid": uid_a},
        method=MatchMethod.probabilistic,
        confidence=0.85,
    )
    logger.info("merged_uid_b", uid=uid_b)
    assert uid_b == uid_a

    # Verify profile
    profile = await merger.get_profile(uid_a)
    assert profile is not None
    assert len(profile.sessions) == 2
    logger.info("profile_has_two_sessions", count=len(profile.sessions))

    # Test Change Stream signal detection
    significant = {
        "event_history": [
            {"session_id": "s1", "event_type": "view"},
            {"session_id": "s1", "event_type": "view"},
            {"session_id": "s1", "event_type": "view"},
            {"session_id": "s1", "event_type": "cart"},
        ]
    }
    assert ProfileMerger._is_significant_event(significant) is True
    logger.info("significance_detected", test="3_views_plus_cart")

    not_significant = {
        "event_history": [
            {"session_id": "s2", "event_type": "view"},
            {"session_id": "s2", "event_type": "view"},
        ]
    }
    assert ProfileMerger._is_significant_event(not_significant) is False
    logger.info("significance_not_detected", test="only_2_views")

    print("All merger self-tests passed.")


def main() -> None:
    asyncio.run(_self_test())


if __name__ == "__main__":
    main()
