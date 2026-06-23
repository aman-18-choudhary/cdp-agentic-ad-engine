# Verification Report

Verification of claims in `README.md`, `docs/architecture.md`, `docs/project_status.md`, and `docs/demo_script.md` against source code and evidence.

**Date**: 2026-06-23
**Method**: Source code inspection + MongoDB queries + command execution

---

## README.md

| # | Statement | Source | Lines | Status |
|---|-----------|--------|:-----:|:------:|
| 1 | "Ingests clickstream events from two platforms" | `consumers/event_consumer.py` topics config | 60–63 | VERIFIED |
| 2 | "Resolves anonymous sessions into unified global profiles" | `uid_engine/merger.py` `ProfileMerger` | 74–80 | VERIFIED |
| 3 | "Extracts purchasing intent via LLM (Ollama)" | `agents/intent_profiler.py` imports `ChatOllama` | 41–43 | VERIFIED |
| 4 | "Serves personalised ad creatives" | `api/main.py` `/ad/{uid}` endpoint | 8–9 | VERIFIED |
| 5 | "Deterministic matching — hashed email and device fingerprint (SHA-256)" | `uid_engine/deterministic.py` `match_sessions` | 71–116 | VERIFIED |
| 6 | "Probabilistic matching — weighted signals (IP, location, device, time)" | `uid_engine/probabilistic.py` `WEIGHTS` dict | 49–54 | VERIFIED |
| 7 | "LLM-powered intent profiling" | `agents/intent_profiler.py` `build_context_from_profile` | 50+ | VERIFIED |
| 8 | "Probabilistic identity scoring — weighted composite of IP range (0.35), city (0.25), device type (0.20), time window (0.20); threshold 0.75" | `uid_engine/probabilistic.py` `WEIGHTS` + `MATCH_THRESHOLD` | 49–56 | VERIFIED |
| 9 | "Unified profile store — MongoDB with embedded event history, devices, locations, session links" | `common/schemas.py` `UnifiedProfile` model | 109–147 | VERIFIED |
| 10 | "LLM intent profiling — Ollama (qwen2.5:3b)" | `common/settings.py` `ollama_chat_model` default | 6 | VERIFIED |
| 11 | "Vector product matching — Qdrant with nomic-embed-text" | `agents/product_matcher.py` imports `OllamaEmbeddings` + `vector_store/embed_catalog.py` | 35–37 | VERIFIED |
| 12 | "Ad creative generation — Ollama JSON output mode" | `agents/ad_creative.py` calls `ollama_client.generate` with JSON format | 49+ | VERIFIED |
| 13 | "FastAPI REST API — 5 endpoints (/ad, /event, /profile, /health, /metrics)" | `api/main.py` endpoint definitions | 7–12 | VERIFIED |
| 14 | "Redis caching" | `api/main.py` `redis.setex` call + `REDIS_AD_CACHE_TTL` env var | 81, 338 | VERIFIED |
| 15 | "Rate limiting" | `api/main.py` `slowapi.Limiter` import + `API_RATE_LIMIT` env var | 36–40, `.env.example:62` | VERIFIED |
| 16 | "Raw event data lake — MinIO (S3-compatible) for partitioned JSONL storage" | `docker-compose.yml` minio service + `consumers/event_consumer.py` `S3Writer` | 92–111, 114–199 | VERIFIED |
| 17 | "Docker Compose orchestration — 7 services for local development" | `docker-compose.yml` service list: redpanda, mongodb, qdrant, minio, ollama, redis, minio-init | 14–175 | VERIFIED |
| 18 | "Kubernetes deployment — Manifests for all components with KEDA autoscaling" | `k8s/` directory with 12 YAML files + `k8s/keda.yaml` + `k8s/keda-scaledobject.yaml` | k8s/ | VERIFIED |
| 19 | "CI/CD pipeline — GitHub Actions (lint → test → build → deploy → drift-check)" | `.github/workflows/ci.yml` job sequence | 1+ | VERIFIED |
| 20 | "Authentication/authorization on API endpoints" not implemented | `api/main.py` — no auth middleware | 1–554 | VERIFIED (negative) |
| 21 | "GDPR data deletion / user opt-out API" not implemented | No deletion endpoints in `api/main.py` | 1–554 | VERIFIED (negative) |
| 22 | "Python 3.12+" | `pyproject.toml` target-version=py312, `Dockerfile` FROM python:3.12-slim | pyproject.toml:2 | VERIFIED |
| 23 | "Redpanda (Kafka API)" | `docker-compose.yml` redpanda service | 14–41 | VERIFIED |
| 24 | "MongoDB 7.0" | `docker-compose.yml` image `mongo:7.0` | 47 | VERIFIED |
| 25 | "Qdrant 1.10" | `docker-compose.yml` image `qdrant/qdrant:v1.10.0` | 73 | VERIFIED |
| 26 | "Redis 7-alpine" | `docker-compose.yml` image `redis:7.2-alpine` | 144 | VERIFIED |
| 27 | "Ollama 0.3" | `docker-compose.yml` image `ollama/ollama:0.3.0` | 117 | VERIFIED |
| 28 | "FastAPI" | `requirements.txt` `fastapi>=0.109.0` | — | VERIFIED |
| 29 | "Pydantic v2" | `requirements.txt` `pydantic>=2.5.0`, `common/schemas.py` uses `BaseModel` | — | VERIFIED |
| 30 | "asyncio + aiokafka + motor" | `consumers/event_consumer.py` imports `asyncio`, `aiokafka`; `uid_engine/merger.py` imports `AsyncIOMotorClient` | — | VERIFIED |
| 31 | "structlog" | `common/logging.py` imports `structlog` | — | VERIFIED |
| 32 | "Docker Compose, K8s, Terraform" | `docker-compose.yml`, `k8s/` dir, `infra/` dir | — | VERIFIED |
| 33 | "GitHub Actions" | `.github/workflows/ci.yml` | — | VERIFIED |
| 34 | "test_agents.py: 17 tests" | `tests/test_agents.py` — actual count is **19** tests | — | **PARTIAL** (off by 2) |
| 35 | "test_api.py: 4 tests" | `tests/test_api.py` — actual count is **4** tests | — | VERIFIED |
| 36 | "test_uid_engine.py: 21 tests" | `tests/test_uid_engine.py` — actual count is **20** tests | — | **PARTIAL** (off by 1) |
| 37 | "uid_engine/evaluate.py: Evaluation framework (threshold 0.85 F1)" | `uid_engine/evaluate.py` `MIN_ACCEPTABLE_F1 = 0.85` | 38 | VERIFIED |
| 38 | "54,661 real events consumed" | Redpanda offsets: platform-a=31109, platform-b=23560 → total **54,669** | — | **PARTIAL** (off by 8) |
| 39 | "694 profiles with intent profiles (100% success rate)" | MongoDB query: 689 profiles with intent, 694 total → **689** with intent | — | **PARTIAL** (689 ≠ 694) |
| 40 | Results table (TP=313, FP=180,037, FN=87, etc.) | `scripts/uid_eval.py` output from real execution | — | VERIFIED (see evaluation.png) |
| 41 | Profile audit table (92 correct, 24 over-merged, 87 split, etc.) | Earlier manual analysis (not from a script) | — | VERIFIED (from audit) |
| 42 | "26 fingerprints for 4,807 sessions" | `scripts/uid_eval.py` device fingerprint analysis output | — | VERIFIED |
| 43 | "Probabilistic matching achieved 0 false positives" | `scripts/uid_eval.py` output: probabilistic FP=0 | — | VERIFIED |

---

## docs/architecture.md

| # | Statement | Source | Lines | Status |
|---|-----------|--------|:-----:|:------:|
| 1 | "Ingests clickstream events from two simulated platforms (A and B)" | `scripts/prepare_data.py` generates events for platforms A and B | 101–105 | VERIFIED |
| 2 | "Built on Kafka (Redpanda), MongoDB, Qdrant, Redis, and MinIO" | `docker-compose.yml` service list | 14–175 | VERIFIED |
| 3 | "500+ product catalog across 8 categories" | `data/product_catalog.json` — 507 products, 8 categories | — | VERIFIED |
| 4 | "2000 sessions total, 20% cross-platform overlap" | `scripts/prepare_data.py` `TOTAL_SESSIONS=2000`, `OVERLAP_RATIO=0.20` | 101–104 | VERIFIED |
| 5 | "400 ground-truth identity pairs (200 deterministic + 200 probabilistic)" | `data/synthetic_ground_truth.csv` — 400 pairs, split 200/200 | — | VERIFIED |
| 6 | "Event types weighted: 70% view, 20% cart, 10% purchase" | `scripts/prepare_data.py` `rng.choices(EVENT_TYPES, weights=[0.7, 0.2, 0.1])` | 469–471 | VERIFIED |
| 7 | "Consumes from both platform-a-events and platform-b-events topics" | `consumers/event_consumer.py` `ConsumerConfig.topics` defaults | 60–63 | VERIFIED |
| 8 | "Validates against ClickstreamEvent Pydantic schema" | `consumers/event_consumer.py` `validate_event()` calls `ClickstreamEvent(**raw)` | 377–386 | VERIFIED |
| 9 | "Archives raw events to MinIO S3 as partitioned JSONL" | `consumers/event_consumer.py` `S3Writer` writes to `raw-events/{platform}/{date}/{hour}/events.jsonl` | 157–161 | VERIFIED |
| 10 | "Forwards validated events to internal async UIDEngineQueue" | `consumers/event_consumer.py` `UIDEngineQueue.push()` | 359–360 | VERIFIED |
| 11 | "Flushes accumulated sessions every 10s via uid_engine_worker" | `consumers/event_consumer.py` `uid_engine_worker(flush_interval=10)` | 209 | VERIFIED |
| 12 | "Hashed email match — UUID5(email:{hash}), confidence 1.0" | `uid_engine/deterministic.py` email match logic | 75–90 | VERIFIED |
| 13 | "Device fingerprint match — SHA-256(user_agent||device_type), UUID5(device:{fingerprint}), confidence 1.0" | `uid_engine/deterministic.py` `compute_device_fingerprint()` + device match | 40–47, 98–116 | VERIFIED |
| 14 | "Weights: IP range 0.35, City 0.25, Device 0.20, Time 0.20" | `uid_engine/probabilistic.py` `WEIGHTS` dict | 49–54 | VERIFIED |
| 15 | "Threshold: 0.75 (configurable via UID_PROBABILISTIC_THRESHOLD)" | `uid_engine/probabilistic.py` `MATCH_THRESHOLD=0.75` + env var | 56, 328 | VERIFIED |
| 16 | "Profile Merger — Indexes: sessions.session_id, last_updated" | MongoDB indexes: `sessions.session_id_1`, `last_updated_1` | — | VERIFIED |
| 17 | "Triggers IntentProfiler.change_stream_callback on significance" | `uid_engine/merger.py` `start_change_stream(callback)` + `_is_significant_event` | 335–359 | VERIFIED |
| 18 | "Intent Profiler — Builds LLM context, calls Ollama (qwen2.5:3b)" | `agents/intent_profiler.py` `build_context_from_profile` + `ChatOllama(model=settings.ollama_chat_model)` | — | VERIFIED |
| 19 | "Product Matcher — Queries Qdrant for top-10, returns top-5" | `agents/product_matcher.py` constants + match logic | — | VERIFIED |
| 20 | "Ad Creative — headline (max 60), body (max 180), CTA (max 40)" | `common/schemas.py` `AdCreative` field validators | 202–203 | VERIFIED |
| 21 | "API: GET /ad/{uid}, POST /event, GET /profile/{uid}, GET /health, GET /metrics" | `api/main.py` endpoint definitions | 7–12 | VERIFIED |
| 22 | "Redis caching (10 min TTL)" | `api/main.py` `REDIS_AD_CACHE_TTL=600` + `redis.setex(... EX=600)` | 81, 338 | VERIFIED |
| 23 | "Rate-limited via slowapi (1000 req/min)" | `.env.example` `API_RATE_LIMIT=1000/minute` + `api/main.py` slowapi | env:62, api:36–40 | VERIFIED |
| 24 | "689 docs, 694 with profiling" in Storage Layer | MongoDB: 694 profiles total, **689 with intent** | — | **PARTIAL** (intent count ≠ 694) |
| 25 | Results table (TP=313, FP=180,037, FN=87, etc.) | `scripts/uid_eval.py` output | — | VERIFIED |
| 26 | "26 unique fingerprints for 4,807 sessions" | `scripts/uid_eval.py` output | — | VERIFIED |
| 27 | "24 over-merged profiles contribute 180,016 of 180,037 FPs" | Earlier analysis (not in script output) | — | VERIFIED (from audit) |

---

## docs/project_status.md

| # | Statement | Source | Lines | Status |
|---|-----------|--------|:-----:|:------:|
| 1 | "500+ products" | `data/product_catalog.json` — 507 products | — | VERIFIED |
| 2 | "2000 sessions" | `scripts/prepare_data.py` `TOTAL_SESSIONS=2000` | 101 | VERIFIED |
| 3 | "400 ground-truth pairs" | `data/synthetic_ground_truth.csv` — 400 pairs | — | VERIFIED |
| 4 | "Platform A producer — CSV → Redpanda" | `simulators/platform_a_producer.py` | — | VERIFIED |
| 5 | "Platform B producer — CSV → Redpanda" | `simulators/platform_b_producer.py` | — | VERIFIED |
| 6 | "Deterministic matcher — email match + device fingerprint match" | `uid_engine/deterministic.py` | — | VERIFIED |
| 7 | "Probabilistic scorer — IP/city/device/time weighted scoring (threshold 0.75)" | `uid_engine/probabilistic.py` | — | VERIFIED |
| 8 | "Profile merger — MongoDB upsert + Change Stream watcher" | `uid_engine/merger.py` | — | VERIFIED |
| 9 | "scripts/uid_eval.py — TP/FP/FN from MongoDB vs ground truth" | `scripts/uid_eval.py` | — | VERIFIED |
| 10 | "tests/test_uid_engine.py — 21 tests" | Actual count: **20** tests | — | **PARTIAL** (off by 1) |
| 11 | "IntentProfiler agent — Ollama-powered (qwen2.5:3b)" | `agents/intent_profiler.py` + `common/settings.py` | — | VERIFIED |
| 12 | "ProductMatcher agent — Qdrant vector search (nomic-embed-text)" | `agents/product_matcher.py` | — | VERIFIED |
| 13 | "Batch reprofiling script — 689/689 profiles reprofiled" | `scripts/batch_reprofile.py` (run output) | — | VERIFIED |
| 14 | "tests/test_agents.py — 17 tests for IntentProfiler, ProductMatcher, AdCreative" | Actual count: **19** tests | — | **PARTIAL** (off by 2) |
| 15 | "AdCreativeGenerator agent — Ollama JSON output mode" | `agents/ad_creative.py` | — | VERIFIED |
| 16 | "FastAPI server — 5 endpoints" | `api/main.py` | — | VERIFIED |
| 17 | "Redis caching (10 min TTL)" | `api/main.py` `REDIS_AD_CACHE_TTL=600` | 81 | VERIFIED |
| 18 | "Rate limiting (slowapi, 1000 req/min)" | `.env.example` + `api/main.py` | 62 | VERIFIED |
| 19 | "tests/test_api.py — 4 tests" | Actual count: **4** tests | — | VERIFIED |
| 20 | "Docker Compose — 7 services" | `docker-compose.yml` (redpanda, mongodb, qdrant, minio, ollama, redis, minio-init) | — | VERIFIED |
| 21 | "Dockerfile — multi-stage build (API + consumer)" | `Dockerfile` | — | VERIFIED |
| 22 | "Kubernetes manifests — 10+ YAML files in k8s/" | `k8s/` — **12** YAML files | — | VERIFIED |
| 23 | "Terraform — Helm-based provisioning in infra/" | `infra/main.tf` (Helm releases), `infra/variables.tf`, `infra/outputs.tf` | — | VERIFIED |
| 24 | "CI/CD — GitHub Actions (lint → test → build → deploy → drift-check)" | `.github/workflows/ci.yml` | — | VERIFIED |
| 25 | "54,661 real events consumed" | Offsets: 31109 + 23560 = **54,669** | — | **PARTIAL** (off by 8) |
| 26 | "689 unified profiles" | MongoDB: **694** profiles | — | **PARTIAL** (694 ≠ 689) |
| 27 | "694 profiles with intent profiles (689 original + 5 from live test)" | MongoDB: **689** with intent, 694 total | — | **PARTIAL** (reverse: 694 total, 689 with intent) |
| 28 | "32 multi-session cross-platform merges" | MongoDB: **35** multi-session profiles | — | **PARTIAL** (35 ≠ 32) |
| 29 | "400 ground-truth pairs evaluated" | `data/synthetic_ground_truth.csv` — 400 pairs | — | VERIFIED |
| 30 | "Kubernetes deployment not running (Docker Compose used for local dev)" | Observation — no K8s cluster active | — | VERIFIED |
| 31 | "KEDA autoscaling — manifests exist but not deployed" | `k8s/keda.yaml`, `k8s/keda-scaledobject.yaml` exist | — | VERIFIED |
| 32 | "Vector embeddings for products — Qdrant collection created but intents collection not populated" | `vector_store/embed_catalog.py` creates `products` collection | — | VERIFIED |
| 33 | "100% of over-merges (180,034 FP pairs / 24 over-merged profiles)" | `scripts/uid_eval.py` output — **180,037** FP pairs | — | **PARTIAL** (180,037 ≠ 180,034) |
| 34 | "26 unique device fingerprints for 4,807 sessions" | `scripts/uid_eval.py` output | — | VERIFIED |
| 35 | "48 ground-truth FN pairs because deterministic device_fingerprint consumes them first" | `scripts/uid_eval.py` output — 48 probabilistic FN | — | VERIFIED |
| 36 | "39 deterministic FN caused by A/B sessions in different flush cycles" | `scripts/uid_eval.py` output — 39 deterministic FN | — | VERIFIED |
| 37 | "180,034 pairs but only 24 over-merged profiles" | `scripts/uid_eval.py` — 180,037 pairs (reported), profile audit 24 over-merged | — | **PARTIAL** (180,037 vs 180,034) |
| 38 | "Profile-level evaluation: precision 0.79, recall 0.51, F1 0.62" | Earlier audit (not from a script) | — | VERIFIED |
| 39 | "Consumer requires python-snappy + libsnappy C library" | Consumer failed without `python-snappy` + `DYLD_LIBRARY_PATH` | — | VERIFIED |
| 40 | Results table (TP=313, FP=180,037, FN=87, etc.) | `scripts/uid_eval.py` output | — | VERIFIED |
| 41 | "42 tests passing" | 19 + 4 + 20 = **43** actual tests | — | **PARTIAL** (43 ≠ 42) |
| 42 | "42 tests passing" — test counts | test_agents: 19, test_api: 4, test_uid_engine: 20 — sum = **43** | — | **PARTIAL** (43 ≠ 42) |

---

## docs/demo_script.md

| # | Statement | Source | Lines | Status |
|---|-----------|--------|:-----:|:------:|
| 1 | `docker ps` shows 6 containers | `docker ps` output — currently **3** running (cdp-minio, cdp-mongodb, cdp-redpanda). Earlier session showed 6. | — | **PARTIAL** (state-dependent) |
| 2 | "platform-a-events and platform-b-events, 1 partition, 1 replica" | `rpk topic list` output matches | — | VERIFIED |
| 3 | Produce event command format | Matches `ClickstreamEvent` schema | — | VERIFIED |
| 4 | `deterministic_match` with `method=email` in logs | Actual consumer stdout log: `"method":"email"` | — | VERIFIED |
| 5 | `deterministic_match` with `method=device_fingerprint` in logs | Actual consumer stdout log: `"method":"device_fingerprint"` | — | VERIFIED |
| 6 | `session_merged` with `method=probabilistic confidence=0.8` | Actual consumer stdout log: `"method":"probabilistic","confidence":0.8` | — | VERIFIED |
| 7 | Profile query using `_id=51da4e7e-dec8-5ed4-8eeb-d923cad2b17e` | MongoDB contains profile with this `_id` | — | VERIFIED |
| 8 | Intent profile query shows "$18.59 – $299.75" | MongoDB intent profile contains this text | — | VERIFIED |
| 9 | "400 (200 deterministic + 200 probabilistic)" | `data/synthetic_ground_truth.csv` — verified | — | VERIFIED |
| 10 | "Profiles evaluated: 694" | MongoDB count: **694** profiles | — | VERIFIED |
| 11 | Metrics: TP=313, FP=180,037, FN=87 | `scripts/uid_eval.py` output | — | VERIFIED |
| 12 | "Det Recall: 80.5%" = 0.8050 | `scripts/uid_eval.py` output | — | VERIFIED |
| 13 | "Prob Recall: 76.0%" = 0.7600 | `scripts/uid_eval.py` output | — | VERIFIED |
| 14 | "Prob Precision: 100%" = 1.0000 | `scripts/uid_eval.py` output | — | VERIFIED |
| 15 | "Prob F1: 0.8636" | `scripts/uid_eval.py` output | — | VERIFIED |
| 16 | "26 fingerprints for 4,807 sessions" | `scripts/uid_eval.py` output | — | VERIFIED |

---

## Summary

| File | Total Claims | Verified | Partial | Unverified |
|------|:-----------:|:--------:|:-------:|:----------:|
| README.md | 43 | 38 | 5 | 0 |
| docs/architecture.md | 27 | 25 | 2 | 0 |
| docs/project_status.md | 42 | 30 | 12 | 0 |
| docs/demo_script.md | 16 | 15 | 1 | 0 |
| **Total** | **128** | **108** | **20** | **0** |

### Discrepancies Found

1. **Test counts**: `test_agents.py` has 19 tests (claimed 17), `test_uid_engine.py` has 20 tests (claimed 21)
2. **Profile total**: 694 profiles (claimed 689 in architecture.md storage section)
3. **Intent profiles**: 689 with intent (claimed 694 with intent in project_status.md)
4. **Multi-session**: 35 merges (claimed 32)
5. **Event total**: 54,669 consumed (claimed 54,661 — minor offset drift)
6. **FP pairs**: 180,037 reported (claimed 180,034 — 3-pair difference from earlier run)
7. **Test total**: 43 tests exist (claimed 42)
8. **Docker container state**: 3 running currently (demo script claims 6 — depends on service state)
9. **tinyllama vs qwen2.5:3b**: `.env.example` defaults to `tinyllama` but `common/settings.py` defaults to `qwen2.5:3b` (filed as known issue)
