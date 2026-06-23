#!/usr/bin/env python3
"""Batch re-profile all existing unified_profiles via IntentProfiler + Ollama.

Usage:
    python scripts/batch_reprofile.py [--model qwen2.5:3b] [--concurrency 2]
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.logging import setup_logging, get_logger
from agents.intent_profiler import IntentProfiler

logger = get_logger("batch_reprofile")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
CONCURRENCY = int(os.getenv("REPROFILE_CONCURRENCY", "2"))


async def get_all_profile_uids() -> List[str]:
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client["cdp"]
    coll = db["unified_profiles"]
    # Process small profiles first for fast early completion
    pipeline = [
        {"$addFields": {"event_count": {"$size": {"$ifNull": ["$event_history", []]}}}},
        {"$sort": {"event_count": 1}},
        {"$project": {"_id": 1}},
    ]
    uids = []
    async for doc in coll.aggregate(pipeline):
        uids.append(str(doc["_id"]))
    client.close()
    return uids


async def run() -> None:
    setup_logging(service_name="batch-reprofile")

    profiler = IntentProfiler(mongo_uri=MONGODB_URI)
    await profiler.connect()
    logger.info("profiler_connected")

    uids = await get_all_profile_uids()
    total = len(uids)
    logger.info("profiles_to_reprofile", total=total)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def profile_one(uid: str, idx: int) -> dict:
        async with sem:
            t0 = time.monotonic()
            try:
                result = await profiler.profile_user(uid)
                elapsed = time.monotonic() - t0
                if result:
                    logger.info(
                        "profile_success",
                        idx=idx,
                        total=total,
                        uid=uid[:16],
                        elapsed_s=round(elapsed, 1),
                    )
                    return {"uid": uid, "status": "ok", "elapsed": elapsed}
                else:
                    logger.warning(
                        "profile_failed",
                        idx=idx,
                        total=total,
                        uid=uid[:16],
                        elapsed_s=round(elapsed, 1),
                    )
                    return {"uid": uid, "status": "failed", "elapsed": elapsed}
            except Exception as exc:
                elapsed = time.monotonic() - t0
                logger.error(
                    "profile_error",
                    idx=idx,
                    total=total,
                    uid=uid[:16],
                    error=str(exc),
                    elapsed_s=round(elapsed, 1),
                )
                return {"uid": uid, "status": "error", "elapsed": elapsed}

    t_start = time.monotonic()
    tasks = [profile_one(uid, i) for i, uid in enumerate(uids)]
    results = await asyncio.gather(*tasks)

    elapsed_total = time.monotonic() - t_start
    ok = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "error")

    await profiler.disconnect()

    print()
    print("=" * 60)
    print("  BATCH REPROFILE COMPLETE")
    print("=" * 60)
    print(f"  Total profiles:  {total}")
    print(f"  Success:         {ok}")
    print(f"  Failed (null):   {failed}")
    print(f"  Errors:          {errors}")
    print(f"  Total time:      {elapsed_total:.1f}s ({elapsed_total/60:.1f}min)")
    if ok:
        avg = sum(r["elapsed"] for r in results if r["status"] == "ok") / ok
        print(f"  Avg per profile: {avg:.1f}s")
    print("=" * 60)

    sys.exit(0 if errors == 0 else 1)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
