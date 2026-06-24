#!/usr/bin/env python3
"""Ad Creative Agent.

Given a ``global_uid``, fetches the user's intent profile and top-5
matched products, then calls Ollama with JSON output
mode enforced to produce a hyper-personalised ad creative with
headline, body, CTA, and product links.

The result is validated against the :class:`~common.schemas.AdCreative`
Pydantic schema, written back to MongoDB, and returned.

Usage:
    python agents/ad_creative.py  # self-test with mock data
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import ollama as ollama_client
except ImportError:
    ollama_client = None

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

from common.logging import setup_logging, get_logger
from common.schemas import AdCreative, Product
from common.settings import settings
from agents.product_matcher import ProductMatcher

logger = get_logger("agents.ad_creative")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", settings.ollama_chat_model)
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "cdp")
MONGODB_PROFILE_COLLECTION = os.getenv("MONGODB_PROFILE_COLLECTION", "unified_profiles")

MAX_RETRIES = 3
RETRY_DELAY_S = 1.5

SYSTEM_PROMPT = """You are a world-class performance marketer writing hyper-personalised ad copy.
Given a user's intent profile and a list of recommended products, write a short ad creative with:
- headline: (max 10 words, punchy, action-oriented)
- body: (max 30 words, addresses the user's specific need)
- cta: (3-5 words call-to-action)
- product_links: list of product_ids to feature (max 3 IDs)

Output ONLY valid JSON matching this schema. No markdown, no preamble, no code fences:
{"headline": "...", "body": "...", "cta": "...", "product_links": ["prod_123", "prod_456"]}"""

FALLBACK_CREATIVE = {
    "headline": "Discover Something New Today",
    "body": "Check out our curated collection of top-rated products tailored just for you.",
    "cta": "Shop Now",
    "product_links": [],
}


# ──────────────────────────────────────────────
# Ad Creative Generator
# ──────────────────────────────────────────────

class AdCreativeGenerator:
    """Generate and persist personalised ad creatives."""

    def __init__(
        self,
        mongo_uri: str = MONGODB_URI,
        ollama_base_url: str = OLLAMA_BASE_URL,
        ollama_model: str = OLLAMA_CHAT_MODEL,
    ) -> None:
        self._mongo_uri = mongo_uri
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._mongo_client: Optional[AsyncIOMotorClient] = None
        self._product_matcher: Optional[ProductMatcher] = None

    # ── Connection lifecycle ─────────────────────

    async def connect(self) -> None:
        """Connect to MongoDB and initialise the product matcher."""
        if AsyncIOMotorClient is not None:
            self._mongo_client = AsyncIOMotorClient(self._mongo_uri)
            logger.info("mongodb_connected", uri=self._mongo_uri)

        self._product_matcher = ProductMatcher(
            mongo_uri=self._mongo_uri,
            ollama_base_url=self._ollama_base_url,
            ollama_embed_model=os.getenv("OLLAMA_EMBED_MODEL", settings.ollama_embed_model),
        )
        self._product_matcher.connect()
        logger.info("product_matcher_ready")

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._product_matcher:
            await self._product_matcher.disconnect()
        if self._mongo_client:
            self._mongo_client.close()
            logger.info("mongodb_disconnected")

    # ── Core generation ──────────────────────────

    async def generate_ad(self, global_uid: str) -> AdCreative:
        """Generate a personalised ad creative for a user.

        Steps:
            1. Fetch the unified profile from MongoDB.
            2. Read ``last_intent_profile``.
            3. Retrieve top-5 matched products via :class:`ProductMatcher`.
            4. Build an LLM prompt from intent + products.
            5. Call Ollama with JSON format enforced.
            6. Validate the response as :class:`AdCreative` (retry on failure).
            7. Persist to MongoDB and return.

        Returns a sensible fallback creative if all retries are exhausted.
        """
        profile = await self._fetch_profile(global_uid)
        intent = self._get_intent(profile)
        products = await self._get_matched_products(global_uid)

        if not intent:
            logger.warning("no_intent_profile", global_uid=global_uid)
            if not products:
                return self._fallback(global_uid, profile, products)
            # Still try LLM with just products when intent is missing
            prompt = self._build_prompt("User is interested in similar products.", products)
            creative = await self._call_llm_with_retry(prompt, products)
            await self._write_creative(global_uid, creative)
            return creative

        prompt = self._build_prompt(intent, products)
        logger.debug("llm_prompt_built", prompt_length=len(prompt))

        creative = await self._call_llm_with_retry(prompt, products)
        await self._write_creative(global_uid, creative)
        logger.info(
            "ad_generated",
            global_uid=global_uid,
            headline=creative.headline,
            products=len(creative.product_links),
        )
        return creative

    # ── Internal helpers ─────────────────────────

    async def _fetch_profile(self, global_uid: str) -> Optional[Dict[str, Any]]:
        """Fetch a unified profile by ``_id`` from MongoDB."""
        if self._mongo_client is None:
            return None
        db = self._mongo_client[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        return await coll.find_one({"_id": global_uid})

    @staticmethod
    def _get_intent(profile: Optional[Dict[str, Any]]) -> Optional[str]:
        if profile is None:
            return None
        return profile.get("last_intent_profile") or None

    async def _get_matched_products(self, global_uid: str) -> List[Product]:
        """Get top-5 matched products for this user."""
        if self._product_matcher is None:
            return []
        try:
            return await self._product_matcher.match_products(global_uid)
        except Exception as exc:
            logger.error("product_match_failed", error=str(exc))
            return []

    @staticmethod
    def _build_prompt(intent: str, products: List[Product]) -> str:
        """Build the user message for the LLM."""
        product_lines = []
        for p in products[:5]:
            product_lines.append(
                f"- {p.product_id}: {p.name} (${p.price:.2f}) — {p.category}"
            )
        return (
            f"User Intent:\n{intent}\n\n"
            f"Recommended Products:\n" + "\n".join(product_lines)
        )

    async def _call_llm_with_retry(
        self,
        prompt: str,
        products: List[Product],
    ) -> AdCreative:
        """Call Ollama with JSON output mode, retrying on parse failure."""
        last_error: Optional[str] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = await self._call_ollama(prompt)
                creative = self._parse_response(raw, products)
                logger.debug("llm_success", attempt=attempt)
                return creative
            except (json.JSONDecodeError, ValueError, Exception) as exc:
                last_error = str(exc)
                logger.warning("llm_retry", attempt=attempt, error=last_error)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_S * attempt)

        logger.error("llm_all_retries_exhausted", last_error=last_error)
        return self._build_fallback(products)

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama with JSON format enforcement.

        Uses the official ``ollama`` Python client when available, or
        falls back to LangChain's ChatOllama.
        """
        if ollama_client is not None:
            # Official Ollama client with explicit JSON mode
            client_kwargs = {}
            if self._ollama_base_url != "http://localhost:11434":
                client_kwargs["host"] = self._ollama_base_url

            response = ollama_client.chat(
                model=self._ollama_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format="json",
                options={"temperature": 0.4},
                **client_kwargs,
            )
            raw = response["message"]["content"]
            logger.debug("ollama_response_received", content_length=len(raw))
            return raw

        # Fallback to LangChain ChatOllama
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            llm = ChatOllama(
                base_url=self._ollama_base_url,
                model=self._ollama_model,
                temperature=0.4,
                format="json",
                num_predict=256,
            )
            chain = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("human", "{prompt}"),
            ]) | llm | StrOutputParser()

            result = await chain.ainvoke({"prompt": prompt})
            logger.debug("langchain_response_received", content_length=len(result))
            return result
        except ImportError:
            logger.error("no_llm_client_available")
            raise RuntimeError("No LLM client available (install ollama or langchain-ollama)")

    def _parse_response(self, raw: str, products: List[Product]) -> AdCreative:
        """Parse and validate the LLM JSON response as an AdCreative."""
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n```", 1)[0]
        if text.startswith("```json"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n```", 1)[0]

        data = json.loads(text)
        # Validate required fields
        for field in ("headline", "body", "cta"):
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Constrain product_links to those we recommended
        valid_ids = {p.product_id for p in products}
        links = [pid for pid in data.get("product_links", []) if pid in valid_ids]
        if not links and products:
            links = [products[0].product_id]

        return AdCreative(
            headline=str(data["headline"])[:60],
            body=str(data["body"])[:180],
            cta=str(data["cta"])[:40],
            product_links=links,
            generated_at=datetime.utcnow(),
        )

    def _build_fallback(self, products: List[Product]) -> AdCreative:
        """Build a sensible fallback creative when the LLM fails."""
        if products:
            names = [p.name for p in products[:3]]
            headline = f"Top Picks: {names[0][:30]}" if names else FALLBACK_CREATIVE["headline"]
            body = f"Explore {', '.join(names[:2])} and more handpicked items for you." if names else FALLBACK_CREATIVE["body"]
            cta = "Shop These Picks" if products else FALLBACK_CREATIVE["cta"]
            links = [p.product_id for p in products[:3]]
        else:
            headline = FALLBACK_CREATIVE["headline"]
            body = FALLBACK_CREATIVE["body"]
            cta = FALLBACK_CREATIVE["cta"]
            links = []

        return AdCreative(
            headline=headline[:60],
            body=body[:180],
            cta=cta[:40],
            product_links=links,
            generated_at=datetime.utcnow(),
        )

    def _fallback(
        self,
        global_uid: str,
        profile: Optional[Dict[str, Any]],
        products: List[Product],
    ) -> AdCreative:
        """Generate fallback ad when no intent profile exists."""
        creative = self._build_fallback(products)
        logger.info("fallback_ad_used", global_uid=global_uid)
        return creative

    async def _write_creative(self, global_uid: str, creative: AdCreative) -> None:
        """Write the generated creative to MongoDB."""
        if self._mongo_client is None:
            logger.info("mock_write_creative", global_uid=global_uid, headline=creative.headline)
            return

        db = self._mongo_client[MONGODB_DATABASE]
        coll = db[MONGODB_PROFILE_COLLECTION]
        await coll.update_one(
            {"_id": global_uid},
            {
                "$set": {
                    "last_ad_creative": creative.model_dump(mode="json"),
                    "last_ad_generated_at": datetime.utcnow(),
                },
            },
        )
        logger.debug("creative_written", global_uid=global_uid)


# ──────────────────────────────────────────────
# Standalone callable
# ──────────────────────────────────────────────

async def generate_ad(
    global_uid: str,
    mongo_uri: str = MONGODB_URI,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_model: str = OLLAMA_CHAT_MODEL,
) -> AdCreative:
    """Convenience wrapper — connect, generate, disconnect."""
    generator = AdCreativeGenerator(
        mongo_uri=mongo_uri,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )
    try:
        await generator.connect()
        return await generator.generate_ad(global_uid)
    finally:
        await generator.disconnect()


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

async def _self_test() -> None:
    setup_logging(service_name="ad-creative-self-test")
    generator = AdCreativeGenerator()

    # Test with mock data — no external services needed
    test_intent = (
        "User is actively comparing ventilated motorcycle riding gear "
        "priced between $150–$300. They have abandoned cart twice and "
        "viewed 4 similar products across platforms."
    )
    test_products = [
        Product(product_id="prod_0001", name="Ventilated Riding Jacket", category="sports_gear", description="", price=199.99, tags=["gear"]),
        Product(product_id="prod_0002", name="Perforated Leather Gloves", category="sports_gear", description="", price=79.99, tags=["gear"]),
        Product(product_id="prod_0003", name="Mesh Riding Pants", category="sports_gear", description="", price=159.99, tags=["gear"]),
    ]

    # 1. Test prompt building
    prompt = AdCreativeGenerator._build_prompt(test_intent, test_products)
    assert "User Intent:" in prompt
    assert "Ventilated Riding Jacket" in prompt
    logger.info("test_prompt_build", passed=True)

    # 2. Test fallback creative
    fallback = generator._build_fallback(test_products)
    assert isinstance(fallback, AdCreative)
    assert "Top Picks:" in fallback.headline
    assert len(fallback.product_links) == 3
    logger.info("test_fallback", passed=True, headline=fallback.headline)

    # 3. Test empty products fallback
    empty = generator._build_fallback([])
    assert empty.headline == FALLBACK_CREATIVE["headline"]
    assert empty.product_links == []
    logger.info("test_empty_fallback", passed=True)

    # 4. Test response parsing
    valid_json = '{"headline": "Gear Up!", "body": "Top-rated riding jackets just hit your price range.", "cta": "Shop Now", "product_links": ["prod_0001", "prod_0002"]}'
    parsed = generator._parse_response(valid_json, test_products)
    assert parsed.headline == "Gear Up!"
    assert parsed.cta == "Shop Now"
    logger.info("test_parse_valid_json", passed=True)

    # 5. Test response parsing with markdown fences
    md_json = '```json\n{"headline": "Ride Ready!", "body": "Check out our ventilated jackets.", "cta": "Browse Gear", "product_links": ["prod_0001"]}\n```'
    parsed_md = generator._parse_response(md_json, test_products)
    assert parsed_md.headline == "Ride Ready!"
    logger.info("test_parse_markdown_json", passed=True)

    # 6. Test missing product link fallback
    no_link_json = '{"headline": "Great Deals", "body": "Awesome products await.", "cta": "Shop Now", "product_links": []}'
    parsed_no = generator._parse_response(no_link_json, test_products)
    assert parsed_no.product_links == ["prod_0001"]
    logger.info("test_parse_missing_links", passed=True)

    print()
    print("=" * 72)
    print("  AD CREATIVE SELF-TEST")
    print("=" * 72)
    print(f"\n  Fallback headline: {fallback.headline}")
    print(f"  Test JSON parsing: ✅ ({parsed.headline})")
    print(f"  Test markdown parsing: ✅ ({parsed_md.headline})")
    print()
    print("  ✅ All tests passed.\n")


def main() -> None:
    asyncio.run(_self_test())


if __name__ == "__main__":
    main()
