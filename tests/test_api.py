"""Tests for the FastAPI application (api/main.py module).

Only unit-testable logic (response models, schemas). Integration tests
requiring real services are done via Steps 5-7 (manual / uvicorn).
"""

from __future__ import annotations

import pytest
from common.schemas import EventIngestResponse, HealthStatus, AdResponse, AdCreative
from datetime import datetime


class TestResponseModels:
    def test_health_status_ok(self):
        h = HealthStatus(status="ok", services={"mongodb": "ok"})
        assert h.status == "ok"
        assert h.services["mongodb"] == "ok"

    def test_health_status_degraded(self):
        h = HealthStatus(status="degraded", services={"mongodb": "error: timeout"})
        assert h.status == "degraded"

    def test_event_ingest_response(self):
        r = EventIngestResponse(accepted=True, event_id="e1")
        assert r.accepted is True
        assert r.event_id == "e1"

    def test_ad_response_shape(self):
        creative = AdCreative(
            headline="Test",
            body="Body",
            cta="Click",
            product_links=["p1"],
        )
        r = AdResponse(
            global_uid="uid_1",
            creative=creative,
            cached=False,
            generated_at=datetime.utcnow(),
        )
        assert r.global_uid == "uid_1"
        assert r.creative.headline == "Test"
        assert r.cached is False
