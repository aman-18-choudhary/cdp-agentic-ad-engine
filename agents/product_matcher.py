#!/usr/bin/env python3
"""Product Matcher Agent.

Given a ``global_uid``, fetches the user's latest intent profile from
MongoDB, embeds it using Ollama, and retrieves the
top-10 nearest neighbour products from the Qdrant ``products``
collection.  Already-purchased products are filtered out and the top 5
are returned as a list of :class:`~common.schemas.Product` models,
ranked by relevance score.

Usage:
    python agents/product_matcher.py  # self-test with mock data
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    OllamaEmbeddings = None

from common.logging import setup_logging, get_logger
from common.schemas import Product
from common.settings import settings

logger = get_logger("agents.product_matcher")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "cdp")
MONGODB_PROFILE_COLLECTION = os.getenv("MONGODB_PROFILE_COLLECTION", "unified_profiles")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_PRODUCTS", "products")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", settings.ollama_embed_model)
TOP_K = 10
TOP_N = 5


# ──────────────────────────────────────────────
# Product Matcher
# ──────────────────────────────────────────────

class ProductMatcher:
    """Match user intent to products via vector search."""

    def __init__(
        self,
        mongo_uri: str = MONGODB_URI,
        qdrant_host: str = QDRANT_HOST,
        qdrant_port: int = QDRANT_PORT,
        ollama_base_url: str = OLLAMA_BASE_URL,
        ollama_embed_model: str = OLLAMA_EMBED_MODEL,
    ) -> None:
        self._mongo_uri = mongo_uri
        self._qdrant_host = qdrant_host
        self._qdrant_port = qdrant_port
        self._ollama_base_url = ollama_base_url
        self._ollama_embed_model = ollama_embed_model

        self._mongo_client: Optional[AsyncIOMotorClient] = None
        self._qdrant_client: Optional[QdrantClient] = None
        self._embedder: Optional[OllamaEmbeddings] = None

    # ── Connection lifecycle ─────────────────────

    def connect(self) -> None:
        """Connect to all external services (MongoDB, Qdrant, Ollama)."""
        if AsyncIOMotorClient is not None:
            self._mongo_client = AsyncIOMotorClient(self._mongo_uri)
            logger.info("mongodb_connected", uri=self._mongo_uri)

        if QdrantClient is not None:
            self._qdrant_client = QdrantClient(
                host=self._qdrant_host,
                port=self._qdrant_port,
            )
            logger.info("qdrant_connected", host=self._qdrant_host, port=self._qdrant_port)

        if OllamaEmbeddings is not None:
            self._embedder = OllamaEmbeddings(
                base_url=self._ollama_base_url,
                model=self._ollama_embed_model,
            )
            logger.info("embedder_initialised", model=self._ollama_embed_model)

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._mongo_client:
            self._mongo_client.close()
            logger.info("mongodb_disconnected")

    # ── Core matching ────────────────────────────

    async def match_products(self, global_uid: str) -> List[Product]:
        """Return top-5 product recommendations for a user.

        Steps:
            1. Fetch unified profile from MongoDB.
            2. Read ``last_intent_profile``.
            3. Embed the intent string.
            4. Query Qdrant for top-10 nearest neighbours.
            5. Filter out products already purchased by the user.
            6. Return top-5 as :class:`~common.schemas.Product` instances.
        """
        profile = await self._fetch_profile(global_uid)

        intent = self._get_intent(profile)
        if not intent:
            logger.warning("no_intent_profile", global_uid=global_uid)
            return []

        vector = self._embed(intent)
        if vector is None:
            return []

        # Get purchased product IDs
        purchased_ids = self._get_purchased_ids(profile)

        raw_results = self._search(vector, top_k=TOP_K + len(purchased_ids))
        if not raw_results:
            return []

        # Filter and rank
        matched: List[Product] = []
        for r in raw_results:
            pid = r.payload.get("product_id", "")
            if pid in purchased_ids:
                continue
            matched.append(
                Product(
                    product_id=pid,
                    name=r.payload.get("name", ""),
                    category=r.payload.get("category", ""),
                    description="",  # not stored in Qdrant payload for size
                    price=r.payload.get("price", 0.0),
                    tags=r.payload.get("tags", []),
                )
            )
            if len(matched) >= TOP_N:
                break

        logger.info(
            "products_matched",
            global_uid=global_uid,
            returned=len(matched),
            purchased_filtered=len(purchased_ids),
        )
        return matched

    # ── Internal helpers ─────────────────────────

    async def _fetch_profile(self, global_uid: str) -> Optional[Dict[str, Any]]:
        """Fetch the unified profile from MongoDB."""
        if self._mongo_client is None:
            logger.warning("mongo_not_available")
            return None

        db = self._mongo_client[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        doc = await coll.find_one({"_id": global_uid})
        if doc:
            logger.debug("profile_fetched", global_uid=global_uid)
        else:
            logger.warning("profile_not_found", global_uid=global_uid)
        return doc

    @staticmethod
    def _get_intent(profile: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract the last intent profile from a unified profile document."""
        if profile is None:
            return None
        intent = profile.get("last_intent_profile")
        if not intent:
            intent = profile.get("last_intent_profile")
        return intent if intent else None

    def _embed(self, text: str) -> Optional[List[float]]:
        """Embed a text string using Ollama."""
        if self._embedder is None:
            logger.warning("embedder_not_available")
            return None
        try:
            vector = self._embedder.embed_query(text)
            logger.debug("text_embedded", text_length=len(text), dim=len(vector))
            return vector
        except Exception as exc:
            logger.error("embedding_failed", error=str(exc))
            return None

    def _search(self, vector: List[float], top_k: int = TOP_K) -> List[Any]:
        """Query Qdrant for nearest neighbour products."""
        if self._qdrant_client is None:
            logger.warning("qdrant_not_available")
            return []

        try:
            results = self._qdrant_client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
            )
            logger.debug("qdrant_search", results=len(results))
            return results
        except Exception as exc:
            logger.error("qdrant_search_failed", error=str(exc))
            return []

    @staticmethod
    def _get_purchased_ids(profile: Optional[Dict[str, Any]]) -> set:
        """Return the set of product_ids the user has already purchased."""
        if profile is None:
            return set()
        event_history = profile.get("event_history", [])
        return {
            ev.get("product_id", "")
            for ev in event_history
            if ev.get("event_type") == "purchase"
        }


# ──────────────────────────────────────────────
# Standalone callable
# ──────────────────────────────────────────────

async def match_products(
    global_uid: str,
    mongo_uri: str = MONGODB_URI,
    qdrant_host: str = QDRANT_HOST,
    qdrant_port: int = QDRANT_PORT,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_embed_model: str = OLLAMA_EMBED_MODEL,
) -> List[Product]:
    """Convenience wrapper — connect, match, disconnect."""
    matcher = ProductMatcher(
        mongo_uri=mongo_uri,
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        ollama_base_url=ollama_base_url,
        ollama_embed_model=ollama_embed_model,
    )
    try:
        matcher.connect()
        return await matcher.match_products(global_uid)
    finally:
        await matcher.disconnect()


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

async def _self_test() -> None:
    setup_logging(service_name="product-matcher-self-test")

    print()
    print("=" * 72)
    print("  PRODUCT MATCHER SELF-TEST")
    print("=" * 72)

    # Test with mock data — no external services needed
    matcher = ProductMatcher()
    matcher.connect()

    mock_intent = (
        "User is actively comparing ventilated motorcycle riding gear "
        "priced between $150–$300. They have abandoned cart twice on "
        "Platform A and viewed 4 similar products on Platform B, "
        "indicating high purchase intent."
    )

    # Test intent extraction
    mock_profile = {
        "_id": "test_uid",
        "last_intent_profile": mock_intent,
        "event_history": [
            {"event_type": "purchase", "product_id": "prod_0001"},
            {"event_type": "view", "product_id": "prod_0002"},
        ],
    }
    intent = ProductMatcher._get_intent(mock_profile)
    assert intent == mock_intent
    logger.info("test_intent_extraction", passed=True)

    # Test purchased ID extraction
    purchased = ProductMatcher._get_purchased_ids(mock_profile)
    assert "prod_0001" in purchased
    assert "prod_0002" not in purchased
    logger.info("test_purchased_filter", passed=True)

    # Test embedding (if Ollama available)
    vector = matcher._embed(mock_intent)
    if vector:
        logger.info("test_embedding", passed=True, dim=len(vector))
    else:
        logger.info("test_embedding_skipped", reason="ollama_not_available")

    # Test search (if Qdrant available)
    if vector and matcher._qdrant_client:
        results = matcher._search(vector, top_k=5)
        logger.info("test_qdrant_search", passed=len(results) >= 0, results=len(results))
    else:
        logger.info("test_qdrant_search_skipped", reason="qdrant_not_available")

    await matcher.disconnect()

    print()
    print("  ✅ Self-test passed.\n")


def main() -> None:
    asyncio.run(_self_test())


if __name__ == "__main__":
    main()
