# Demo Script — CDP Agentic Ad Engine

## Quick Start (5 min setup)

```bash
# 1. Start all infrastructure
cd /Users/aman/Projects/CDP
docker compose up -d
docker ps --format "table {{.Names}}\t{{.Status}}"
# Wait until all services show "healthy"

# 2. Pull LLM models (host Ollama)
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 3. Set up Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# On macOS (for python-snappy):
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 4. Generate & embed data
python backend/scripts/prepare_data.py --seed 42
python backend/vector_store/embed_catalog.py

# 5. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173

# 6. Run the pipeline (full demo)
python backend/scripts/reset.py
nohup python backend/consumers/event_consumer.py > /tmp/cdp_consumer.log 2>&1 &
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/cdp_api.log 2>&1 &
python backend/simulators/platform_a_producer.py --max-events 5000 &
python backend/simulators/platform_b_producer.py --max-events 5000 &
python backend/scripts/batch_reprofile.py --limit 10 --concurrency 4

# Or use the all-in-one script:
./backend/scripts/demo.sh
```

---

## Dashboard Walkthrough

Navigate to **http://localhost:5173** and show these pages:

| Route | Page | What to Show |
|-------|------|-------------|
| `/` | **Live Feed** | Real-time event stream with platform/type filters, event simulator |
| `/profiles` | **User Profiles** | Paginated profile table — click a row for detail drawer (intent + ad preview) |
| `/identity` | **Identity Explorer** | Search a Global UID — session graph, devices, locations, LLM intent profile |
| `/ads` | **Ad Studio** | Enter UID — AI-generated ad creative; toggle desktop/mobile; batch fetch |
| `/analytics` | **Analytics** | F1 gauges, precision/recall bar chart, platform split donut, health status |

---

## Evaluation Results

```bash
python backend/scripts/uid_eval.py
```

| Metric | Deterministic | Probabilistic |
|--------|:------------:|:-------------:|
| Precision | 0.0009 | 1.0000 |
| Recall | 0.8050 | 0.7600 |
| F1 Score | 0.0018 | **0.8636** |

Key takeaway: Probabilistic matching achieved 100% precision — zero over-merges. Intent profiling completed for 689 of 694 profiles (99.3% success rate).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| MongoDB connection refused | Wait for `docker compose` health checks to complete |
| Ollama not responding | Run `ollama list` on host machine |
| Frontend shows no data | Check `curl localhost:8000/health` |
| `python-snappy` import error | `export DYLD_LIBRARY_PATH=/opt/homebrew/lib` |

---

## Clean Up

```bash
kill <consumer_pid> <api_pid>
python backend/scripts/reset.py
docker compose down
```
