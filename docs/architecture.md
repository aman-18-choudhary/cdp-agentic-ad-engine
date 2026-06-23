# CDP Agentic Ad Engine — Architecture

## 1. System Overview

The CDP (Customer Data Platform) Agentic Ad Engine is a privacy-centric, cross-platform identity resolution and personalised advertising platform. It ingests clickstream events from two simulated platforms (A and B), resolves anonymous sessions into unified global user profiles using deterministic and probabilistic matching, extracts semantic purchasing intent via an LLM (Ollama), and generates hyper-personalized ad creatives.

The system is built as a modular **event-driven** pipeline on top of **Kafka (Redpanda)**, **MongoDB**, **Qdrant**, **Redis**, and **MinIO**, orchestrated via Docker Compose.

---

## 2. Data Flow

```
Synthetic Data Generator (scripts/prepare_data.py)
    │
    ▼
Platform A Producer (simulators/platform_a_producer.py) ──┐
                                                            ├──► Redpanda Topics
Platform B Producer (simulators/platform_b_producer.py) ──┘       (platform-a-events, platform-b-events)
                                                                        │
                                                                        ▼
                                                              Event Consumer (consumers/event_consumer.py)
                                                                   │                    │
                                                            ┌──────┘                    └──────┐
                                                            ▼                                  ▼
                                                     MinIO / S3                     UID Engine Queue
                                                   (raw JSONL lake)               (in-memory asyncio.Queue)
                                                                                        │
                                                                                        ▼
                                                                              UID Engine Worker
                                                                           ┌─────────┴─────────┐
                                                                           ▼                   ▼
                                                                    Deterministic        Probabilistic
                                                                    Matching             Matching
                                                                           │                   │
                                                                           └─────────┬─────────┘
                                                                                     ▼
                                                                           ProfileMerger
                                                                           (MongoDB upsert)
                                                                                     │
                                                                                     ▼
                                                                        ┌────────────────────┐
                                                                        │  unified_profiles  │
                                                                        │  collection        │
                                                                        └─────────┬──────────┘
                                                                                  │
                                                                                  ▼
                                                                       IntentProfiler
                                                                       (Ollama qwen2.5:3b)
                                                                                  │
                                                                                  ▼
                                                                        last_intent_profile
                                                                        written to MongoDB
                                                                                  │
                                                                                  ▼
                                                                       ProductMatcher
                                                                       (Qdrant vector search)
                                                                                  │
                                                                                  ▼
                                                                       AdCreativeGenerator
                                                                       (Ollama qwen2.5:3b)
                                                                                  │
                                                                                  ▼
                                                                       FastAPI /ad/{uid}
                                                                       (Redis-cached)
```

---

## 3. Component Responsibilities

### 3.1 Data Generation (`scripts/prepare_data.py`)
Generates synthetic clickstream data for development and evaluation:
- 500+ product catalog across 8 categories
- 2000 sessions total, 20% cross-platform overlap
- 400 ground-truth identity pairs (200 deterministic + 200 probabilistic)
- Event types weighted: 70% view, 20% cart, 10% purchase

### 3.2 Simulators (`simulators/platform_a_producer.py`, `simulators/platform_b_producer.py`)
- Read generated CSV files row by row
- Enrich rows with timestamps
- Produce JSON-serialized events to Redpanda topics
- Support throttling and max-event limits

### 3.3 Event Consumer (`consumers/event_consumer.py`)
- **Consumes** from both `platform-a-events` and `platform-b-events` topics
- **Validates** against `ClickstreamEvent` Pydantic schema
- **Archives** raw events to MinIO S3 as partitioned JSONL (`raw-events/{platform}/{date}/{hour}/events.jsonl`)
- **Forwards** validated events to an internal async `UIDEngineQueue`
- **Flushes** accumulated sessions every 10s via `uid_engine_worker`

### 3.4 UID Engine (`uid_engine/`)

#### Deterministic Matching (`deterministic.py`)
Two strict identity signals, checked in priority order:
1. **Hashed email match** — both sessions have identical `hashed_email` → UUID5(`email:{hash}`), confidence 1.0
2. **Device fingerprint match** — SHA-256(`user_agent||device_type`) identical → UUID5(`device:{fingerprint}`), confidence 1.0

#### Probabilistic Matching (`probabilistic.py`)
Weighted scoring of four signals when deterministic fails:
| Signal | Weight | Match Logic |
|--------|--------|-------------|
| IP range | 0.35 | CIDR subnet overlap |
| Location city | 0.25 | Case-insensitive string equality |
| Device type | 0.20 | Exact enum match |
| Time window | 0.20 | Jaccard similarity of active-hour sets |

Threshold: **0.75** (configurable via `UID_PROBABILISTIC_THRESHOLD`)

#### Profile Merger (`merger.py`)
- Manages MongoDB connection and CRUD for `unified_profiles`
- Indexes: `sessions.session_id`, `last_updated`
- Merges sessions: appends `SessionLink`, `$addToSet` for devices/locations, pushes events to `event_history`
- Watches Change Stream for significant events (cart abandon, 3+ views, purchase)
- Triggers `IntentProfiler.change_stream_callback` on significance

### 3.5 Intent Profiler (`agents/intent_profiler.py`)
- Triggered by MongoDB Change Stream on `unified_profiles`
- Builds LLM context from profile: event count, categories browsed, price range, device types, locations, behavioral signals
- Calls Ollama (`qwen2.5:3b`) for semantic intent summary
- Writes `last_intent_profile` string back to MongoDB

### 3.6 Product Matcher (`agents/product_matcher.py`)
- Embeds intent string via Ollama (`nomic-embed-text`)
- Queries Qdrant for top-10 nearest-neighbor products
- Filters out already-purchased items
- Returns top-5 product matches

### 3.7 Ad Creative Generator (`agents/ad_creative.py`)
- Fetches intent profile + top-5 product matches
- Calls Ollama (`qwen2.5:3b`) with JSON output mode
- Generates headline (max 60 chars), body (max 180 chars), CTA (max 40 chars)
- Validates output against Pydantic schema
- Writes creative to MongoDB `ad_creatives` collection

### 3.8 API Server (`api/main.py`)
- FastAPI application with 5 endpoints:
  - `GET /ad/{uid}` — Retrieve cached or generate new ad creative
  - `POST /event` — Ingest a new clickstream event
  - `GET /profile/{uid}` — Retrieve unified profile
  - `GET /health` — Service health check
  - `GET /metrics` — Rate-limit metrics
- Redis caching (10 min TTL) for ad creatives
- Rate-limited via slowapi (1000 req/min)

---

## 4. Identity Resolution Pipeline

The matching pipeline runs in `uid_engine_worker` within `consumers/event_consumer.py`:

1. **Session accumulation**: Events arrive into a dict keyed by `session_id`
2. **Flush cycle**: Every 10 seconds (or immediately on queue empty), `_flush_matches` runs
3. **Deterministic pass**: For each unmatched session, iterate cross-platform candidates:
   - Check `hashed_email` equality first → if match, merge via UUID5
   - Check `device_fingerprint` second → if match, merge via UUID5
4. **Probabilistic pass**: Sessions that didn't find a deterministic match:
   - Compute weighted score across IP, city, device, time
   - If score >= 0.75, merge via UUID5 of concatenated fields
5. **Fallback**: Unmatched sessions create their own new profiles

The matching priority ensures deterministic signals (email, device) always take precedence over probabilistic scoring.

---

## 5. Intent Profiling Pipeline

1. **Trigger**: MongoDB Change Stream watches `unified_profiles` for `insert`/`update` operations
2. **Significance filter**: Only profiles containing significant events proceed:
   - Cart without subsequent purchase (cart abandonment signal)
   - 3+ view events (high-intent browsing)
   - Any purchase event
3. **Context building** (`IntentProfiler.build_context_from_profile`):
   - Event statistics: total events per platform, unique products, event type distribution
   - Category distribution: which product categories were browsed
   - Price range: min/max product prices viewed
   - Behavioral signals: repeat views, cross-platform activity, high-intent indicators
   - Device & location diversity
4. **LLM call**: Context formatted as a prompt, sent to Ollama (`qwen2.5:3b`)
5. **Persistence**: Response written to `unified_profiles.last_intent_profile`

---

## 6. Storage Layer

| System | Purpose | Data |
|--------|---------|------|
| **Redpanda** (Kafka API, port 19093) | Event ingestion | Topics: `platform-a-events`, `platform-b-events` |
| **MongoDB** (port 27017) | Profile & event persistence | Collection: `unified_profiles` (694 profiles, 689 with intent) |
| **MinIO** (S3 API, port 9000) | Raw event data lake | Bucket: `raw-events`, partitioned by platform/date/hour |
| **Qdrant** (port 6333) | Vector search for product matching | Collection: `products` |
| **Redis** (port 6379) | Ad creative cache | Key-value cache with 10 min TTL |

---

## 7. Evaluation Layer

### Evaluation Script (`scripts/uid_eval.py`)
- Reads ground truth from `data/synthetic_ground_truth.csv` (400 pairs)
- Queries live MongoDB `unified_profiles` for session-to-UID mapping
- Computes:
  - **TP**: Ground-truth sessions in same profile
  - **FN**: Ground-truth sessions in different profiles
  - **FP**: Cross-platform sessions merged into same profile not in ground truth
- Reports precision, recall, F1 per matching method
- Analyzes device fingerprint collisions
- Tests probabilistic scores on FN pairs

### Known Results (from real execution):
| Metric | Deterministic | Probabilistic | Combined |
|--------|:------------:|:-------------:|:--------:|
| True Positives | 161 | 152 | 313 |
| False Positives | 180,037 | 0 | 180,037 |
| False Negatives | 39 | 48 | 87 |
| Precision | 0.0009 | 1.0000 | 0.0017 |
| Recall | 0.8050 | 0.7600 | 0.7825 |
| F1 | 0.0018 | 0.8636 | 0.0035 |

### Root Causes
1. **Device fingerprint over-merging**: 26 unique fingerprints for 4,807 sessions in synthetic data → combinatorial FP explosion (24 over-merged profiles contribute 180,016 of 180,037 FPs)
2. **Probabilistic matcher never evaluated**: Deterministic device_fingerprint consumes probabilistic FN candidates before they reach the probabilistic matcher
3. **Batch-timing FNs**: Some session pairs arrive in different flush cycles
