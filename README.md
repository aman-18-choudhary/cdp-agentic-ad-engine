# CDP — Agentic Ad Engine

Cross-platform identity resolution and personalised ad serving engine with real-time clickstream ingestion, probabilistic/deterministic UID stitching, LLM-driven intent profiling, and low-latency API delivery.

## Architecture

```
Platform A ──┐                    ┌── MinIO (Data Lake)
             ├── Redpanda ──► Consumer ──┤
Platform B ──┘                    └── UID Queue ──► Matcher ──► Merger ──► MongoDB
                                                                    │
                                                                    ▼
                                                              FastAPI (Redis cache)
                                                                    │
                                                                    ▼
                                                               Ad Creative (Ollama)
```

## Tech Stack

| Component       | Technology                                       |
|----------------|--------------------------------------------------|
| Event Bus      | Redpanda (Kafka-compatible, no Zookeeper)        |
| Vector DB      | Qdrant                                           |
| Document DB    | MongoDB (replica set for Change Streams)         |
| Cache          | Redis                                            |
| Object Store   | MinIO (S3-compatible)                            |
| LLM            | Ollama (llama3.1:8b + nomic-embed-text)          |
| API            | FastAPI                                          |
| Orchestration  | Docker Compose (local) / K3s + Terraform (prod)  |

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Embed product catalog
python vector_store/embed_catalog.py --reset

# 3. Run tests
pytest tests/ -v

# 4. Start API
MONGODB_URI="mongodb://localhost:27017/?directConnection=true" uvicorn api.main:app --port 8000

# 5. Produce events & run consumer
python simulators/platform_a_producer.py --throttle 20 &
python simulators/platform_b_producer.py --throttle 20 &
MONGODB_URI="mongodb://localhost:27017/?directConnection=true" python consumers/event_consumer.py

# 6. Check profiles
python -c "from pymongo import MongoClient; c=MongoClient('mongodb://localhost:27017/?directConnection=true'); print(f'Profiles: {c.cdp.unified_profiles.count_documents({})}')"
```

## API Endpoints

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| GET    | `/health`         | Service health check                 |
| GET    | `/profile/{uid}`  | Fetch unified profile                |
| GET    | `/ad/{uid}`       | Generate personalised ad creative    |
| POST   | `/events`         | Ingest raw clickstream event         |
| DELETE | `/cache/{uid}`    | Evict cached ad for a UID            |

## Results

### Identity Resolution (F1 Score)

Evaluated against 400 ground-truth cross-platform session pairs:

| Method               | Precision | Recall | F1     | TP  | FP  | FN |
|----------------------|-----------|--------|--------|-----|-----|----|
| Deterministic        | 1.0000    | 1.0000 | 1.0000 | 200 | 0   | 0  |
| Probabilistic        | 1.0000    | 1.0000 | 1.0000 | 200 | 0   | 0  |
| **Combined**         | 0.9302    | 1.0000 | **0.9639** | 400 | 30  | 0  |

Threshold: 0.85 — **PASS**

### Load Test (500 users, 60s)

Test: 500 concurrent users hitting `/ad/{uid}` with 50 UIDs, spawn rate 50/s, 60s runtime.

| Metric    | Value   |
|-----------|---------|
| Requests  | 2,896   |
| Failures  | 0       |
| p50       | 8,900ms |
| p95       | 15,000ms |
| p99       | 19,000ms |
| RPS       | ~48/s   |

Latency is dominated by Ollama LLM inference (llama3.1:8b on CPU). With GPU acceleration or a cloud LLM, p95 is expected to drop below 100ms. The API framework (FastAPI) handles 48 req/s with 0 failures.

### Pipeline Throughput

| Stage          | Count    |
|----------------|----------|
| Events produced| ~18,000  |
| Events consumed| 5,811+   |
| Profiles created| 499     |
| Products embedded| 507    |

### End-to-End Flow

All 7 validation steps completed:
1. Docker Compose — 6/6 services healthy
2. MongoDB replica set — PRIMARY, health 1
3. Product catalog — 507 products embedded in Qdrant
4. Tests — 42/42 passing (UID: 19, Agents: 17, API: 6)
5. API health — all 4 dependencies green
6. Producers + consumer — events consumed, MinIO written
7. Profile creation — profiles persisted in MongoDB
8. UID evaluator — F1 0.9639 **PASS**

## Project Structure

```
├── api/              # FastAPI app (5 endpoints, Redis cache)
├── agents/           # Intent profiler, product matcher, ad creative
├── consumers/        # Event consumer (Redpanda → MinIO → UID engine)
├── uid_engine/       # Deterministic + probabilistic matching, merger
├── simulators/       # Platform A & B event producers
├── vector_store/     # Qdrant embedding and search
├── scripts/          # Dataset generation, ground truth
├── common/           # Schemas (Pydantic v2), logging (structlog)
├── k8s/              # K8s manifests (10 files)
├── infra/            # Terraform (Helm provider for K3s)
└── tests/            # 42 pytest tests
```
# cdp-agentic-ad-engine
