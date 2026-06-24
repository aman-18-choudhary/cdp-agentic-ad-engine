#!/usr/bin/env python3
"""Drop MongoDB collections for a fresh demo start."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def reset():
    c = AsyncIOMotorClient("mongodb://localhost:27017/?directConnection=true")
    db = c["cdp"]
    raw = await db["raw_events"].count_documents({})
    prof = await db["unified_profiles"].count_documents({})
    print(f"Before reset: {raw} raw_events, {prof} unified_profiles")
    await db["raw_events"].drop()
    await db["unified_profiles"].drop()
    print("Collections dropped. Ready for fresh data.")
    c.close()

asyncio.run(reset())
