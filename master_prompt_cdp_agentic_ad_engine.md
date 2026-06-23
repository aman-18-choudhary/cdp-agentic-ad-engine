# MASTER PROMPT: Cross-Platform Identity Resolution & Agentic Ad Engine

---

## ROLE & CONTEXT

You are a senior full-stack ML/AI engineer and data architect. You are building a **privacy-centric Customer Data Platform (CDP)** that:

1. Ingests high-volume cross-platform e-commerce clickstream data in real time
2. Resolves anonymous sessions into unified Global UIDs using probabilistic + deterministic matching (no PII)
3. Uses an LLM-driven agentic workflow (AgentOps) to extract semantic purchasing intent
4. Generates hyper-personalized ad creatives and serves them via a low-latency API

The codebase must be **production-grade**, **modular**, **event-driven**, and **containerized**. Every module must be independently testable. Use Python as the primary language unless another tool is explicitly better suited.

---

## TECH STACK (Non-Negotiable)

| Layer | Tool |
|---|---|
| Infrastructure | Terraform, Kubernetes (K8s), KEDA |
| Streaming | Apache Kafka (or RabbitMQ), Python producers/consumers |
| Data Lake | AWS S3 (or MinIO for local dev) |
| Profile Store | MongoDB with Change Streams enabled |
| AI Orchestration | LangChain or LlamaIndex |
| Vector DB | Milvus (self-hosted) or Pinecone (managed) |
| Serving API | FastAPI |
| LLM | Claude claude-sonnet-4-6 via Anthropic API (or OpenAI GPT-4o as fallback) |
| Containerization | Docker, Docker Compose (local), Helm charts (K8s) |
| CI/CD | GitHub Actions |

---

## DATA SOURCING INSTRUCTIONS

### Datasets
- **Dataset A** — Ecommerce Clickstream (Kaggle): raw behavioral logs with `event_time`, `event_type` (view/cart/purchase), `product_id`, `user_session`
- **Dataset B** — E-commerce User Behavior & Transactions (Kaggle): enriched with `Session_Count`, `Pages_Viewed`, `Avg_Order_Value`, `location`, demographics

### Synthetic Split (Critical)
After downloading both datasets:
1. Assign **60% of events → Platform A**, **40% → Platform B**
2. For a defined subset of users (~20%), **overlap them** across platforms by assigning matching `device_type`, `ip_range`, or `location` fields
3. These overlapping users are the ground truth for testing your identity resolution engine
4. Generate a `synthetic_ground_truth.csv` mapping overlapped users to a known shared `global_uid` for evaluation

---

## MODULE 1: DATA INGESTION & EVENT PROCESSING

### Goal
Simulate real-time clickstream traffic from two separate e-commerce platforms into a central message broker.

### Task 1.1 — Event Simulator (Producer)
Build `platform_a_producer.py` and `platform_b_producer.py`:
- Parse the Kaggle CSVs row by row
- Emit each row as a **JSON event** to a dedicated Kafka topic (`platform-a-events`, `platform-b-events`)
- JSON schema must include:
  ```json
  {
    "platform": "A",
    "session_id": "uuid",
    "event_type": "view|cart|purchase",
    "product_id": "str",
    "event_time": "ISO8601",
    "device_type": "mobile|desktop|tablet",
    "ip_range": "str",
    "location": {"city": "str", "country": "str"},
    "user_agent": "str",
    "hashed_email": "sha256_or_null"
  }
  ```
- Use a configurable replay speed (e.g., 100 events/sec) to simulate live traffic
- Add a `--throttle` flag to simulate traffic spikes

### Task 1.2 — Consumer Service
Build `event_consumer.py`:
- Consume from both Kafka topics
- Validate and deserialize each event
- Write raw JSON to **S3/MinIO** (data lake) with path `s3://raw-events/{platform}/{date}/{hour}/events.jsonl`
- Forward validated events to the **Identity Resolution Engine** (Module 2) via an internal queue or direct function call
- Deploy as a **K8s Deployment** with **KEDA ScaledObject** targeting Kafka consumer lag

### Task 1.3 — Kubernetes & KEDA Config
Provide:
- `k8s/consumer-deployment.yaml` — Deployment manifest for the consumer pods
- `k8s/keda-scaledobject.yaml` — KEDA ScaledObject that scales consumer pods based on Kafka topic lag (min: 1, max: 10, lag threshold: 100)

---

## MODULE 2: CROSS-PLATFORM IDENTITY RESOLUTION (UID ENGINE)

### Goal
Stitch together anonymous sessions from Platform A and Platform B into a unified `global_uid` without relying on PII.

### Architecture
```
Incoming Event
     │
     ▼
[Deterministic Matcher] ──── Hard ID match (hashed_email, exact device_fingerprint)
     │ No match
     ▼
[Probabilistic Scorer] ──── Similarity score from (ip_range + location + device_type + time_window)
     │ Score ≥ threshold
     ▼
[Profile Merger] ──── Link session_ids under one global_uid in MongoDB
     │
     ▼
[MongoDB Profile Store] ──── Upsert unified profile document
```

### Task 2.1 — Deterministic Matching
File: `uid_engine/deterministic.py`
- Input: two session objects
- Logic: if `hashed_email` is non-null and identical across platforms → merge immediately
- Return: `{"match": true, "global_uid": "existing_or_new_uuid", "method": "deterministic"}`

### Task 2.2 — Probabilistic Matching
File: `uid_engine/probabilistic.py`
- Compute a **weighted similarity score** (0.0–1.0) between two sessions:
  - `ip_range` match: weight 0.35
  - `location` (city-level) match: weight 0.25
  - `device_type` match: weight 0.20
  - `time_window` overlap (browsing hours): weight 0.20
- If score ≥ 0.75 → merge sessions under one `global_uid`
- Persist confidence score and method in the MongoDB profile
- Return: `{"match": true/false, "score": 0.82, "global_uid": "uuid", "method": "probabilistic"}`

### Task 2.3 — MongoDB Profile Schema
Collection: `unified_profiles`
```json
{
  "_id": "global_uid_uuid",
  "sessions": [
    {"platform": "A", "session_id": "...", "linked_at": "ISO8601", "method": "probabilistic", "confidence": 0.82}
  ],
  "event_history": [...],
  "devices": ["mobile", "desktop"],
  "locations": [{"city": "...", "country": "..."}],
  "last_intent_profile": "...",
  "last_updated": "ISO8601"
}
```
- Enable **Change Streams** on this collection to trigger the AI pipeline (Module 3) on every significant update (cart abandon, purchase, 3+ page views in session)

### Task 2.4 — Evaluation
File: `uid_engine/evaluate.py`
- Load `synthetic_ground_truth.csv`
- Run the engine against ground-truth pairs
- Output: Precision, Recall, F1-Score for both deterministic and probabilistic methods

---

## MODULE 3: AI & RECOMMENDATION ENGINE (AGENTOPS)

### Goal
Replace traditional collaborative filtering with an LLM agent that reads a unified profile and generates a rich semantic intent summary, then uses that to retrieve the best-matching products via vector search.

### Task 3.1 — User Profiling Agent
File: `agents/intent_profiler.py`
- Triggered by MongoDB Change Stream on `unified_profiles`
- Build a LangChain or LlamaIndex agent
- System prompt:
  ```
  You are a behavioral analyst for an e-commerce platform. 
  You will receive a unified cross-platform user profile as JSON.
  Your job is to write a concise semantic intent summary (2-3 sentences max) that captures:
  - What category/product the user is actively researching
  - Their apparent price sensitivity or budget range
  - Any behavioral signals (repeat views, cart abandons, comparison behavior)
  Output ONLY the intent summary string. No JSON, no preamble.
  ```
- Input: full `unified_profile` JSON document
- Output: plain-text intent string, e.g.:
  > "User is actively comparing ventilated motorcycle riding gear priced between $150–$300. They have abandoned cart twice on Platform A and viewed 4 similar products on Platform B, indicating high purchase intent. They prefer early-morning browsing sessions on mobile."
- Store this string back to `unified_profiles.last_intent_profile`

### Task 3.2 — Product Catalog Vectorization
File: `vector_store/embed_catalog.py`
- Create a mock product catalog (`data/product_catalog.json`) with 500+ items across relevant e-commerce categories
- Each product:
  ```json
  {"product_id": "str", "name": "str", "category": "str", "description": "str", "price": float, "tags": [...]}
  ```
- Embed each product's `name + description + tags` using `text-embedding-3-small` (OpenAI) or `claude` embeddings
- Store vectors in **Milvus** or **Pinecone** with `product_id` as the payload

### Task 3.3 — Product Matching via Vector Search
File: `agents/product_matcher.py`
- Embed the intent string from Task 3.1
- Query the vector DB for top-5 nearest neighbors
- Return: list of `{product_id, name, price, score}` ranked by relevance
- Apply a post-filter: exclude already-purchased products from the user's `event_history`

---

## MODULE 4: TARGETED AD GENERATION & SERVING

### Goal
Convert the product matches and intent profile into a personalized ad creative, and expose it via a real-time API.

### Task 4.1 — Ad Creative Agent
File: `agents/ad_creative.py`
- Input: `{intent_profile: str, top_products: [...], user_meta: {device, location}}`
- System prompt:
  ```
  You are a world-class performance marketer writing hyper-personalized ad copy.
  Given a user's intent profile and a list of recommended products, write a short ad creative with:
  - headline: (max 10 words, punchy, action-oriented)
  - body: (max 30 words, addresses the user's specific need)
  - cta: (3-5 words call-to-action)
  - product_links: list of product_ids to feature
  Output ONLY valid JSON matching this schema. No markdown.
  ```
- Output:
  ```json
  {
    "headline": "Gear Up Before Sunday's Ride",
    "body": "You've been eyeing ventilated riding jackets — these top-rated picks just hit your price range.",
    "cta": "Shop Riding Gear Now",
    "product_links": ["prod_123", "prod_456"]
  }
  ```

### Task 4.2 — Serving API
File: `api/main.py` (FastAPI)

Endpoints:
- `GET /ad/{global_uid}` — Returns the latest generated ad creative for a UID. Serves from MongoDB cache; triggers agent pipeline if stale (>10 min).
- `POST /event` — Accepts a new clickstream event, routes to consumer pipeline.
- `GET /profile/{global_uid}` — Returns the full unified profile (for debugging/internal use).
- `GET /health` — Health check.

Requirements:
- Sub-100ms p95 latency for `/ad/{global_uid}` (serve from cache, not live LLM)
- Background task regeneration using FastAPI `BackgroundTasks`
- Rate limiting: 1000 req/min per IP (use `slowapi`)

### Task 4.3 — Infrastructure as Code (Terraform)
Directory: `infra/`
- `main.tf` — Provisions: EKS cluster (or local K3s), S3 bucket (or MinIO), MongoDB Atlas (or local Mongo), Pinecone index
- `variables.tf` — Parameterize all env-specific values (region, instance sizes, API keys as secrets)
- `outputs.tf` — Kafka broker URL, MongoDB URI, API endpoint, S3 bucket ARN
- Implement **Terraform state drift detection** via a GitHub Actions scheduled job (daily `terraform plan` and alert on diff)

---

## CI/CD PIPELINE

File: `.github/workflows/ci.yml`

Jobs:
1. `lint` — Ruff (Python linting)
2. `test` — pytest for all modules (unit + integration)
3. `build` — Docker build for each service
4. `deploy` — Helm upgrade on merge to `main`
5. `drift-check` — Daily scheduled Terraform plan, post diff as PR comment if drift detected

---

## PROJECT STRUCTURE

```
cdp-agentic-ad-engine/
├── data/
│   ├── platform_a_events.csv       # 60% split
│   ├── platform_b_events.csv       # 40% split
│   ├── synthetic_ground_truth.csv
│   └── product_catalog.json
├── simulators/
│   ├── platform_a_producer.py
│   └── platform_b_producer.py
├── consumers/
│   └── event_consumer.py
├── uid_engine/
│   ├── deterministic.py
│   ├── probabilistic.py
│   ├── merger.py
│   └── evaluate.py
├── agents/
│   ├── intent_profiler.py
│   ├── product_matcher.py
│   └── ad_creative.py
├── vector_store/
│   └── embed_catalog.py
├── api/
│   └── main.py
├── k8s/
│   ├── consumer-deployment.yaml
│   └── keda-scaledobject.yaml
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── tests/
│   ├── test_uid_engine.py
│   ├── test_agents.py
│   └── test_api.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .github/workflows/ci.yml
```

---

## CODING STANDARDS

- All functions must have **type hints** and **docstrings**
- All external I/O (Kafka, MongoDB, S3, LLM calls) must be wrapped in **try/except** with structured logging (`structlog`)
- Use **Pydantic v2** models for all data schemas
- Environment variables via `.env` + `pydantic-settings` — no hardcoded secrets
- Every module must have a `__main__` block for standalone testing
- Log at DEBUG level inside all agent calls so LLM prompts/responses are inspectable

---

## EVALUATION CRITERIA

When this system is complete, it should demonstrably:

| Criterion | Evidence |
|---|---|
| Cross-domain tracking | A single user journey from Platform A browse → Platform B purchase maps to one `global_uid` |
| Identity resolution accuracy | F1 ≥ 0.85 on synthetic ground truth |
| Semantic intent quality | Intent profiles are specific (product category + price range + behavioral signal), not generic |
| Ad relevance | Top-5 product matches are semantically relevant to intent profile (manual spot check) |
| API performance | p95 latency < 100ms on `/ad/{uid}` endpoint under 500 concurrent requests |
| Infrastructure reproducibility | `terraform apply` on a clean environment brings up full stack with zero manual steps |

---

## HOW TO USE THIS PROMPT

When working through this project with an AI assistant:

1. **Start with Module 1** — get data flowing end-to-end before building intelligence on top
2. **Build Module 2 next** — the UID engine is the core IP of the platform; validate with `evaluate.py` before proceeding
3. **Module 3 depends on Module 2** — the Change Stream trigger is the handoff point
4. **Module 4 is the output layer** — build and test the API last, once the pipeline produces real data
5. **Use this prompt as your spec** — paste it (or the relevant module section) when asking for code generation, architecture review, or debugging help

For each module, ask:
> "Implement [Task X.Y] from the master prompt. Follow all coding standards. Return the full file."
