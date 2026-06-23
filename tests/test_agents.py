"""Tests for the AI agent modules (intent profiler, product matcher, ad creative).

Uses pytest-mock to mock external dependencies (MongoDB, Ollama, Qdrant).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from common.schemas import AdCreative, Product
from agents.intent_profiler import IntentProfiler, build_context_from_profile
from agents.product_matcher import ProductMatcher
from agents.ad_creative import AdCreativeGenerator


# ══════════════════════════════════════════════
# Intent Profiler
# ══════════════════════════════════════════════

class TestIntentProfiler:
    def test_build_context_includes_sessions_and_signals(self):
        product_map = {"prod_001": {"product_id": "prod_001", "name": "Test Product", "category": "electronics", "price": 99.99}}
        profile = {
            "_id": "uid_1",
            "sessions": [{"platform": "A", "session_id": "s1"}, {"platform": "B", "session_id": "s2"}],
            "event_history": [
                {"session_id": "s1", "event_type": "view", "product_id": "prod_001"},
                {"session_id": "s1", "event_type": "view", "product_id": "prod_001"},
                {"session_id": "s1", "event_type": "view", "product_id": "prod_001"},
                {"session_id": "s1", "event_type": "cart", "product_id": "prod_001"},
            ],
            "devices": ["mobile", "desktop"],
            "locations": [{"city": "NY", "country": "US"}],
            "last_intent_profile": None,
        }
        context = build_context_from_profile(profile, product_map)
        assert "Cross-platform" in context
        assert "Cart abandon" in context
        assert "High-intent browsing" in context
        assert "electronics" in context
        assert "$99.99" in context

    def test_build_context_empty_history(self):
        context = build_context_from_profile(
            {"_id": "uid_2", "sessions": [], "event_history": [], "devices": [], "locations": [], "last_intent_profile": None},
            {},
        )
        assert "uid_2" in context
        assert "Total events: 0" in context

    def test_mock_intent_fallback(self):
        import asyncio
        profiler = IntentProfiler()
        context = "Product categories browsed: electronics(3)\nPrice range seen: $10.00 - $100.00\n[Signal] Cart abandon in session s1"
        intent = asyncio.run(profiler._mock_intent(context))
        assert isinstance(intent, str)
        assert len(intent) > 10
        assert "electronics" in intent.lower() or "cart" in intent.lower()

    @pytest.mark.asyncio
    async def test_profile_user_returns_none_when_no_mongo(self, mocker):
        profiler = IntentProfiler()
        profiler._mongo_client = None
        result = await profiler.profile_user("test_uid")
        assert result is None

    @pytest.mark.asyncio
    async def test_profile_user_calls_llm_and_writes_intent(self, mocker):
        mocker.patch.object(IntentProfiler, "_fetch_profile", return_value={"_id": "uid_1", "event_history": [], "sessions": [], "devices": [], "locations": []})
        mocker.patch.object(IntentProfiler, "_call_llm_with_retry", return_value="test intent summary")
        mocker.patch.object(IntentProfiler, "_write_intent", AsyncMock())

        profiler = IntentProfiler()
        profiler._llm = mocker.MagicMock()
        result = await profiler.profile_user("uid_1")
        assert result == "test intent summary"


# ══════════════════════════════════════════════
# Product Matcher
# ══════════════════════════════════════════════

class TestProductMatcher:
    def test_get_intent_from_profile(self):
        profile = {"last_intent_profile": "User is researching gaming laptops"}
        intent = ProductMatcher._get_intent(profile)
        assert intent == "User is researching gaming laptops"

    def test_get_intent_returns_none_when_missing(self):
        assert ProductMatcher._get_intent(None) is None
        assert ProductMatcher._get_intent({}) is None
        assert ProductMatcher._get_intent({"last_intent_profile": None}) is None

    def test_get_purchased_ids(self):
        profile = {
            "event_history": [
                {"event_type": "purchase", "product_id": "p1"},
                {"event_type": "view", "product_id": "p2"},
                {"event_type": "purchase", "product_id": "p3"},
            ]
        }
        purchased = ProductMatcher._get_purchased_ids(profile)
        assert purchased == {"p1", "p3"}

    def test_get_purchased_ids_empty(self):
        assert ProductMatcher._get_purchased_ids(None) == set()
        assert ProductMatcher._get_purchased_ids({}) == set()

    @pytest.mark.asyncio
    async def test_match_products_returns_empty_when_no_intent(self, mocker):
        matcher = ProductMatcher()
        matcher._mongo_client = mocker.MagicMock()
        mocker.patch.object(ProductMatcher, "_fetch_profile", return_value={"_id": "uid_1", "last_intent_profile": None, "event_history": []})
        products = await matcher.match_products("uid_1")
        assert products == []

    @pytest.mark.asyncio
    async def test_match_products_filters_purchased(self, mocker):
        profile = {
            "_id": "uid_1",
            "last_intent_profile": "looking for electronics",
            "event_history": [
                {"event_type": "purchase", "product_id": "purchased_1"},
                {"event_type": "view", "product_id": "available_1"},
            ],
        }
        matcher = ProductMatcher()
        matcher._mongo_client = mocker.MagicMock()
        matcher._qdrant_client = mocker.MagicMock()
        matcher._embedder = mocker.MagicMock()

        mocker.patch.object(ProductMatcher, "_fetch_profile", return_value=profile)
        mocker.patch.object(ProductMatcher, "_embed", return_value=[0.1] * 4)
        mocker.patch.object(ProductMatcher, "_search", return_value=[
            mocker.MagicMock(payload={"product_id": "available_1", "name": "A", "category": "electronics", "price": 10.0, "tags": []}),
            mocker.MagicMock(payload={"product_id": "purchased_1", "name": "B", "category": "electronics", "price": 20.0, "tags": []}),
            mocker.MagicMock(payload={"product_id": "available_2", "name": "C", "category": "electronics", "price": 30.0, "tags": []}),
        ])

        result = await matcher.match_products("uid_1")
        assert len(result) == 2
        pids = [p.product_id for p in result]
        assert "purchased_1" not in pids
        assert "available_1" in pids
        assert "available_2" in pids


# ══════════════════════════════════════════════
# Ad Creative
# ══════════════════════════════════════════════

class TestAdCreative:
    def test_fallback_creative_with_products(self):
        products = [
            Product(product_id="p1", name="Product A", category="cat1", description="", price=10.0, tags=[]),
            Product(product_id="p2", name="Product B", category="cat2", description="", price=20.0, tags=[]),
        ]
        generator = AdCreativeGenerator()
        creative = generator._build_fallback(products)
        assert isinstance(creative, AdCreative)
        assert "Product A" in creative.headline
        assert len(creative.product_links) == 2
        assert creative.cta == "Shop These Picks"

    def test_fallback_creative_empty_products(self):
        generator = AdCreativeGenerator()
        creative = generator._build_fallback([])
        assert creative.headline == "Discover Something New Today"
        assert creative.product_links == []
        assert creative.cta == "Shop Now"

    def test_parse_valid_json_response(self):
        products = [
            Product(product_id="p1", name="A", category="cat", description="", price=10.0, tags=[]),
        ]
        raw = '{"headline": "Great Deal!", "body": "Amazing product just for you.", "cta": "Buy Now", "product_links": ["p1"]}'
        generator = AdCreativeGenerator()
        creative = generator._parse_response(raw, products)
        assert creative.headline == "Great Deal!"
        assert creative.body == "Amazing product just for you."
        assert creative.cta == "Buy Now"
        assert creative.product_links == ["p1"]

    def test_parse_markdown_code_fence(self):
        products = [Product(product_id="p1", name="A", category="cat", description="", price=10.0, tags=[])]
        raw = '```json\n{"headline": "Sale!", "body": "Limited time offer.", "cta": "Shop Sale", "product_links": ["p1"]}\n```'
        generator = AdCreativeGenerator()
        creative = generator._parse_response(raw, products)
        assert creative.headline == "Sale!"

    def test_parse_missing_product_links_falls_back(self):
        products = [Product(product_id="p1", name="A", category="cat", description="", price=10.0, tags=[])]
        raw = '{"headline": "Hi", "body": "Body text here.", "cta": "Click", "product_links": []}'
        generator = AdCreativeGenerator()
        creative = generator._parse_response(raw, products)
        assert creative.product_links == ["p1"]

    def test_parse_invalid_json_raises(self):
        products = []
        generator = AdCreativeGenerator()
        with pytest.raises(Exception):
            generator._parse_response("not json at all", products)

    def test_build_prompt_includes_intent_and_products(self):
        intent = "User is researching headphones"
        products = [
            Product(product_id="p1", name="Wireless Headphones", category="electronics", description="", price=99.99, tags=[]),
        ]
        prompt = AdCreativeGenerator._build_prompt(intent, products)
        assert "User Intent:" in prompt
        assert "Wireless Headphones" in prompt
        assert "$99.99" in prompt

    def test_call_llm_three_retries_then_fallback(self):
        """When the LLM fails all 3 retries, the fallback creative is returned."""
        import asyncio
        generator = AdCreativeGenerator()
        products = [Product(product_id="p1", name="A", category="cat", description="", price=10.0, tags=[])]
        generator._call_ollama = AsyncMock(side_effect=Exception("LLM unavailable"))
        creative = asyncio.run(generator._call_llm_with_retry("test prompt", products))
        assert isinstance(creative, AdCreative)
        assert creative.cta == "Shop These Picks"
        assert generator._call_ollama.call_count == 3
