from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class EventType(str, Enum):
    view = "view"
    cart = "cart"
    purchase = "purchase"


class DeviceType(str, Enum):
    mobile = "mobile"
    desktop = "desktop"
    tablet = "tablet"


class Platform(str, Enum):
    A = "A"
    B = "B"


class MatchMethod(str, Enum):
    deterministic = "deterministic"
    probabilistic = "probabilistic"
    none = "none"


# ──────────────────────────────────────────────
# Location
# ──────────────────────────────────────────────

class Location(BaseModel):
    city: str
    country: str


# ──────────────────────────────────────────────
# Clickstream Event
# ──────────────────────────────────────────────

class ClickstreamEvent(BaseModel):
    platform: Platform
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    product_id: str
    event_time: datetime
    device_type: DeviceType
    ip_range: str
    location: Location
    user_agent: str
    hashed_email: Optional[str] = None

    @field_validator("event_time", mode="before")
    @classmethod
    def parse_event_time(cls, v: Any) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T"))
        if isinstance(v, datetime):
            return v
        raise ValueError(f"Invalid event_time: {v!r}")

    @field_validator("hashed_email", mode="before")
    @classmethod
    def normalize_email(cls, v: Any) -> Optional[str]:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v.lower() if isinstance(v, str) else v

    model_config = {"json_schema_extra": {"example": {
        "platform": "A",
        "session_id": "a1b2c3d4-1234-5678-9abc-def012345678",
        "event_type": "view",
        "product_id": "prod_001",
        "event_time": "2024-03-15T14:30:00Z",
        "device_type": "mobile",
        "ip_range": "192.168.1.0/24",
        "location": {"city": "New York", "country": "US"},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
        "hashed_email": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }}}


# ──────────────────────────────────────────────
# Session Link (within a unified profile)
# ──────────────────────────────────────────────

class SessionLink(BaseModel):
    platform: Platform
    session_id: str
    linked_at: datetime
    method: MatchMethod
    confidence: float = Field(ge=0.0, le=1.0)


# ──────────────────────────────────────────────
# Unified Profile (MongoDB document)
# ──────────────────────────────────────────────

class UnifiedProfile(BaseModel):
    id: str = Field(alias="_id", default_factory=lambda: str(uuid.uuid4()))
    sessions: List[SessionLink] = Field(default_factory=list)
    event_history: List[ClickstreamEvent] = Field(default_factory=list)
    devices: List[DeviceType] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    last_intent_profile: Optional[str] = None
    last_ad_creative: Optional[dict] = None
    last_ad_generated_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def merge_event(self, event: ClickstreamEvent) -> None:
        self.event_history.append(event)
        if event.device_type not in self.devices:
            self.devices.append(event.device_type)
        if event.location not in self.locations:
            self.locations.append(event.location)
        self.last_updated = datetime.utcnow()

    def add_session(
        self,
        session_id: str,
        platform: Platform,
        method: MatchMethod,
        confidence: float = 1.0,
    ) -> None:
        existing = any(
            s.session_id == session_id and s.platform == platform
            for s in self.sessions
        )
        if not existing:
            self.sessions.append(
                SessionLink(
                    platform=platform,
                    session_id=session_id,
                    linked_at=datetime.utcnow(),
                    method=method,
                    confidence=confidence,
                )
            )
            self.last_updated = datetime.utcnow()

    model_config = {"populate_by_name": True, "json_schema_extra": {"example": {
        "_id": "global_001",
        "sessions": [{
            "platform": "A",
            "session_id": "sess_a_001",
            "linked_at": "2024-03-15T14:30:00Z",
            "method": "probabilistic",
            "confidence": 0.82
        }],
        "event_history": [],
        "devices": ["mobile", "desktop"],
        "locations": [{"city": "New York", "country": "US"}],
        "last_intent_profile": "User is actively comparing...",
        "last_updated": "2024-03-15T14:30:00Z"
    }}}


# ──────────────────────────────────────────────
# Identity Match Results
# ──────────────────────────────────────────────

class IdentityMatchResult(BaseModel):
    match: bool
    global_uid: Optional[str] = None
    method: MatchMethod
    score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────
# Product Catalog
# ──────────────────────────────────────────────

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    description: str
    price: float = Field(ge=0.0)
    tags: List[str] = Field(default_factory=list)


class ProductMatch(BaseModel):
    product_id: str
    name: str
    price: float
    score: float = Field(ge=0.0, le=1.0)


# ──────────────────────────────────────────────
# Ad Creative
# ──────────────────────────────────────────────

class AdCreative(BaseModel):
    headline: str = Field(max_length=60)
    body: str = Field(max_length=180)
    cta: str = Field(max_length=40)
    product_links: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# API Models
# ──────────────────────────────────────────────

class AdResponse(BaseModel):
    global_uid: str
    creative: AdCreative
    cached: bool = False
    generated_at: datetime


class ProfileResponse(BaseModel):
    profile: UnifiedProfile


class EventIngestResponse(BaseModel):
    accepted: bool
    event_id: str
    message: str = "Event accepted for processing"


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# Ground Truth (for evaluation)
# ──────────────────────────────────────────────

class GroundTruthRecord(BaseModel):
    session_id_a: str
    session_id_b: str
    global_uid: str
    platform_a_match_fields: Dict[str, Any] = Field(default_factory=dict)
    platform_b_match_fields: Dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# Vector Embedding
# ──────────────────────────────────────────────

class VectorEmbedding(BaseModel):
    id: str
    vector: List[float]
    payload: Dict[str, Any] = Field(default_factory=dict)
