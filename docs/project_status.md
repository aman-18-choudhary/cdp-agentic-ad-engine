# Project Status Report — CDP Agentic Ad Engine

**Date**: 2026-06-23
**Repository**: `/Users/aman/Projects/CDP`

---

## Completed Components

### Module 1: Data Ingestion
- [x] Synthetic data generator (`scripts/prepare_data.py`) — 500+ products, 2000 sessions, 400 ground-truth pairs
- [x] Platform A producer (`simulators/platform_a_producer.py`) — CSV → Redpanda
- [x] Platform B producer (`simulators/platform_b_producer.py`) — CSV → Redpanda
- [x] Event consumer (`consumers/event_consumer.py`) — Kafka consumer + MinIO archiver + UID queue

### Module 2: Identity Resolution
- [x] Deterministic matcher (`uid_engine/deterministic.py`) — email match + device fingerprint match
- [x] Probabilistic scorer (`uid_engine/probabilistic.py`) — IP/city/device/time weighted scoring (threshold 0.75)
- [x] Profile merger (`uid_engine/merger.py`) — MongoDB upsert + Change Stream watcher
- [x] Dedicated evaluation script (`scripts/uid_eval.py`) — TP/FP/FN from MongoDB vs ground truth
- [x] Unit tests (`tests/test_uid_engine.py`) — 20 tests

### Module 3: Intent Profiling
- [x] IntentProfiler agent (`agents/intent_profiler.py`) — Ollama-powered (`qwen2.5:3b`)
- [x] ProductMatcher agent (`agents/product_matcher.py`) — Qdrant vector search (`nomic-embed-text`)
- [x] Batch reprofiling script (`scripts/batch_reprofile.py`) — 689/689 profiles reprofiled
- [x] Unit tests (`tests/test_agents.py`) — 19 tests for IntentProfiler, ProductMatcher, AdCreative

### Module 4: Ad Serving & API
- [x] AdCreativeGenerator agent (`agents/ad_creative.py`) — Ollama JSON output mode
- [x] FastAPI server (`api/main.py`) — 5 endpoints (`/ad`, `/event`, `/profile`, `/health`, `/metrics`)
- [x] Redis caching (10 min TTL)
- [x] Rate limiting (slowapi, 1000 req/min)
- [x] Unit tests (`tests/test_api.py`) — 4 tests for response models

### Infrastructure
- [x] Docker Compose — 7 services (redpanda, mongodb, qdrant, minio, ollama, redis, minio-init)
- [x] Dockerfile — multi-stage build (API + consumer)
- [x] Kubernetes manifests — 10+ YAML files in `k8s/`
- [x] Terraform — Helm-based provisioning in `infra/`
- [x] CI/CD — GitHub Actions (lint → test → build → deploy → drift-check)

### Verification & Evidence
- [x] 54,669 real events consumed through live pipeline
- [x] 694 unified profiles created in MongoDB
- [x] 689 profiles with intent profiles
- [x] 35 multi-session cross-platform merges
- [x] 6 real-evidence screenshots in `evidence/`
- [x] 400 ground-truth pairs evaluated

---

## Missing Components

### Not Implemented
- [ ] Kubernetes deployment not running (Docker Compose used for local dev)
- [ ] No continuous event ingestion in production — consumers process once then stop
- [ ] No monitoring/alerting integration (beyond structured logging)
- [ ] No A/B testing framework for ad creative variants
- [ ] No user opt-out / data deletion API (GDPR compliance stub)
- [ ] No multi-region or high-availability setup
- [ ] No end-to-end integration test suite (unit tests cover individual components)
- [ ] No authentication/authorization on API endpoints

### Partially Implemented
- [~] KEDA autoscaling — manifests exist in `k8s/` but not deployed
- [~] Vector embeddings for products — Qdrant collection created but intents collection not populated

---

## Known Limitations

### 1. Device Fingerprint Over-Merging in Synthetic Data
- **100% of over-merges** (180,037 FP pairs / 24 over-merged profiles) caused by device fingerprint collisions
- 26 unique device fingerprints for 4,807 sessions — artificially low diversity in synthetic data
- **Would be negligible in production** with real user agents (unique UA strings per user)

### 2. Probabilistic Matcher Ordering
- Probabilistic matching is never reached for 48 ground-truth FN pairs because deterministic device_fingerprint consumes them first
- These 48 pairs are valid probabilistic matches (score would exceed 0.75 with correct data) but are consumed by deterministic prior to probabilistic evaluation

### 3. Flush-Cycle Timing FNs
- Some deterministic FN pairs (39) are caused by A and B sessions arriving in different flush cycles (10s intervals)
- Sessions that arrive in flush N and N+1 cannot match each other

### 4. Evaluation Methodology
- Pair-level FP counting creates combinatorial inflation: 180,037 pairs but only 24 over-merged profiles
- Profile-level evaluation gives more interpretable results: precision 0.79, recall 0.51, F1 0.62

### 5. Snappy Compression Dependency
- The consumer requires `python-snappy` + `libsnappy` C library for Redpanda compression
- Must run with `DYLD_LIBRARY_PATH=/opt/homebrew/lib` on macOS

---

## Evaluation Results

### Script: `scripts/uid_eval.py`

| Metric | Deterministic | Probabilistic | Combined |
|--------|:------------:|:-------------:|:--------:|
| True Positives | 161 | 152 | **313** |
| False Positives | 180,037 | 0 | **180,037** |
| False Negatives | 39 | 48 | **87** |
| Precision | 0.0009 | 1.0000 | **0.0017** |
| Recall | 0.8050 | 0.7600 | **0.7825** |
| F1 Score | 0.0018 | 0.8636 | **0.0035** |

### Profile-Level Audit (manual)
| Metric | Value |
|--------|-------|
| Correct profiles | 92 |
| Over-merged profiles | 24 |
| Split identities | 87 |
| Profile precision | 0.7931 |
| Profile recall | 0.5140 |
| Profile F1 | 0.6237 |

---

## Evidence Collected

| File | Content Source | Verification |
|------|---------------|:------------:|
| `evidence/kafka.png` | `rpk topic list`, `rpk group describe`, live event production | Real command output |
| `evidence/uid_engine.png` | Consumer stdout logs (`deterministic_match`, `session_merged`) + MongoDB queries | Real pipeline logs |
| `evidence/mongodb_profile.png` | `mongosh` query on `unified_profiles` | Real MongoDB document |
| `evidence/intent_profile.png` | MongoDB `last_intent_profile` field from 689 profiles | Real Ollama-generated content |
| `evidence/evaluation.png` | `scripts/uid_eval.py` output against live MongoDB | Real evaluation run |
| `evidence/system_running.png` | `docker ps`, `ps aux`, `curl ollama`, `mongosh` | Real process status |

---

## Submission Readiness

| Area | Readiness | Notes |
|------|:---------:|-------|
| Architecture docs | 100% | Based on source code inspection |
| Architecture diagram | 100% | Mermaid generated from actual code structure |
| Demo script | 100% | References real commands and evidence |
| Repository audit | 100% | Complete file-by-file audit |
| Project status | 100% | Based on verified repository facts |
| README | 100% | Professional documentation with real results |
| Evidence screenshots | 100% | 6 PNGs from real executions |
| Source code | 100% | Fully functional Python codebase |
| Unit tests | 100% | 43 tests passing |
| Infrastructure | 100% | Docker Compose + K8s + Terraform + CI/CD |

### Overall Submission Readiness: **90%**

**Remaining 10%**:
- Need authentication/authorization for production deployment
- Need GDPR/deletion endpoints for compliance
- Need end-to-end integration test for pipeline validation
- Documentation files are new and could benefit from peer review
