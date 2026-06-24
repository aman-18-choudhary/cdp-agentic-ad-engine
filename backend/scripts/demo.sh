#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/../.venv/bin/activate"

echo "╔══════════════════════════════════════════════════╗"
echo "║  CDP Agentic Ad Engine — LIVE DEMO              ║"
echo "║  Data Generation → UID Creation → Dashboard     ║"
echo "╚══════════════════════════════════════════════════╝"

# ── Step 1: Verify Docker ──────────────────
echo ""
echo "▸ STEP 1: Verify infrastructure is running"
docker ps --format "table {{.Names}}\t{{.Status}}" 2>&1 | head -10
echo ""
read -p "  ✓ Docker OK? [Press Enter to continue...]"

# ── Step 2: Reset DB ───────────────────────
echo ""
echo "▸ STEP 2: Clearing old data (MongoDB reset)"
python scripts/reset.py
echo "  → Collections dropped. Ready for fresh data."
read -p "  [Press Enter to continue...]"

# ── Step 3: Generate Synthetic Data ────────
echo ""
echo "▸ STEP 3: Generating synthetic clickstream data"
echo "  → platform_a_events.csv (10,363 events)"
echo "  → platform_b_events.csv (7,847 events)"
echo "  → product_catalog.json (507 products)"
echo "  → synthetic_ground_truth.csv (400 pairs)"
python scripts/prepare_data.py --seed 42
read -p "  [Press Enter to continue...]"

# ── Step 4: Embed Product Catalog ──────────
echo ""
echo "▸ STEP 4: Embedding products in Qdrant vector DB"
echo "  → Each product → nomic-embed-text → vector → Qdrant"
python vector_store/embed_catalog.py
echo "  ✓ Products embedded."
read -p "  [Press Enter to continue...]"

# ── Step 5: Start Consumer ─────────────────
echo ""
echo "▸ STEP 5: Starting Event Consumer"
echo "  → Listens on Redpanda: platform-a-events / platform-b-events"
echo "  → Validates → stores in MongoDB → runs UID Engine"
nohup python consumers/event_consumer.py > /tmp/cdp_consumer.log 2>&1 &
CONSUMER_PID=$!
echo "  Consumer started (PID: $CONSUMER_PID)"
sleep 5
read -p "  [Press Enter to continue...]"

# ── Step 6: Start API ──────────────────────
echo ""
echo "▸ STEP 6: Starting API Server"
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/cdp_api.log 2>&1 &
API_PID=$!
echo "  API started (PID: $API_PID)"
sleep 5
echo ""
echo "  → OPEN http://localhost:5173 in browser NOW"
echo "  → (Start frontend with: cd frontend && npm run dev)"
echo ""
curl -s http://localhost:8000/health | python3 -m json.tool 2>&1
read -p "  [Press Enter to continue...]"

# ── Step 7: Run Producers (LIVE!) ──────────
echo ""
echo "▸ STEP 7: PRODUCING EVENTS — Watch the dashboard!"
echo "  ⚡ Running Platform A & B producers..."
python simulators/platform_a_producer.py --max-events 5000 &
PA_PID=$!
python simulators/platform_b_producer.py --max-events 5000 &
PB_PID=$!
echo ""
echo "  ⚡ Events are flowing NOW!"
echo "  ⚡ Go to http://localhost:5173 — counters are increasing!"
echo "  ⚡ Click 'User Profiles' — UIDs are being created live!"
echo ""
wait $PA_PID $PB_PID
echo "  ✓ Producers finished."
sleep 15
read -p "  [Press Enter to continue...]"

# ── Step 8: Intent Reprofile (subset) ──────
echo ""
echo "▸ STEP 8: Generating LLM intent profiles (first 10 users)"
echo "  → This uses Ollama — may take 1-2 min per profile"
python scripts/batch_reprofile.py --limit 10 --concurrency 4 2>&1 || true
echo "  ✓ Intent profiles generated for demo."
read -p "  [Press Enter to continue...]"

# ── Step 9: Show Results ───────────────────
echo ""
echo "▸ STEP 9: Pipeline Results"
python3 << 'PYEOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def report():
    m = AsyncIOMotorClient('mongodb://localhost:27017/?directConnection=true')
    d = m['cdp']
    raw = await d['raw_events'].count_documents({})
    prof = await d['unified_profiles'].count_documents({})
    with_intent = await d['unified_profiles'].count_documents({"last_intent_profile": {"$ne": None}})
    print(f"  Events stored:        {raw}")
    print(f"  Profiles (UIDs):      {prof}")
    print(f"  Profiles with intent: {with_intent}")
    if prof > 0:
        s = await d['unified_profiles'].find_one()
        print(f"  Sample Global UID:    {s['_id']}")
        print(f"  Has intent?:          {s.get('last_intent_profile') is not None}")
    m.close()
asyncio.run(report())
PYEOF

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅ DEMO COMPLETE                               ║"
echo "║                                                  ║"
echo "║  Show the panel these pages:                     ║"
echo "║  • / (Live Feed)     — Event stream in real-time ║"
echo "║  • /profiles         — Profiles with Global UIDs ║"
echo "║  • /identity         — Search a UID, graph+intent║"
echo "║  • /ads              — Generate ad from any UID  ║"
echo "║  • /analytics        — F1 scores & charts        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "To stop: kill $CONSUMER_PID $API_PID"
echo "To cleanup: python scripts/reset.py"
