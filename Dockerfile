# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ── Consumer image ──────────────────────────────────────
FROM base AS consumer
CMD ["python", "-m", "consumers.event_consumer"]

# ── API image ───────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
