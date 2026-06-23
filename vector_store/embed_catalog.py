#!/usr/bin/env python3
"""Product Catalog Vectorisation.

Loads the product catalog from ``data/product_catalog.json``, embeds
each product's ``name + description + tags`` using Ollama, and upserts the vectors into a Qdrant collection
named ``products``.

Idempotent — safe to run multiple times (upserts by ``product_id``).

Usage:
    python vector_store/embed_catalog.py [--reset] [--batch-size 50]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
except ImportError:
    QdrantClient = None

try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    OllamaEmbeddings = None

from common.logging import setup_logging, get_logger
from common.settings import settings

logger = get_logger("vector_store.embed_catalog")


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_PRODUCTS", "products")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", settings.ollama_embed_model)
CATALOG_PATH = os.getenv("PRODUCT_CATALOG_PATH", "data/product_catalog.json")
EMBEDDING_DIM = 768  # adjust to match the configured embed model's output dim


# ──────────────────────────────────────────────
# Catalog Loading
# ──────────────────────────────────────────────

def load_catalog(path: str) -> List[Dict[str, Any]]:
    """Load products from ``product_catalog.json``."""
    if not os.path.exists(path):
        logger.error("catalog_not_found", path=path)
        sys.exit(1)
    with open(path) as f:
        products: List[Dict[str, Any]] = json.load(f)
    logger.info("catalog_loaded", path=path, count=len(products))
    return products


# ──────────────────────────────────────────────
# Qdrant Helpers
# ──────────────────────────────────────────────

def connect_qdrant(host: str = QDRANT_HOST, port: int = QDRANT_PORT) -> QdrantClient:
    """Create and return a Qdrant client."""
    if QdrantClient is None:
        logger.error("qdrant_client_not_installed")
        sys.exit(1)
    client = QdrantClient(host=host, port=port)
    logger.info("qdrant_connected", host=host, port=port)
    return client


def ensure_collection(
    client: QdrantClient,
    collection_name: str = QDRANT_COLLECTION,
    vector_size: int = EMBEDDING_DIM,
    reset: bool = False,
) -> None:
    """Ensure the Qdrant collection exists, optionally dropping and recreating it."""
    existing = client.get_collections()
    names = [c.name for c in existing.collections]

    if reset and collection_name in names:
        client.delete_collection(collection_name)
        logger.info("collection_deleted", collection=collection_name)

    if reset or collection_name not in names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        logger.info("collection_created", collection=collection_name, dim=vector_size)
    else:
        logger.info("collection_exists", collection=collection_name)


# ──────────────────────────────────────────────
# Embedding
# ──────────────────────────────────────────────

def build_embedder(
    base_url: str = OLLAMA_BASE_URL,
    model: str = OLLAMA_EMBED_MODEL,
) -> OllamaEmbeddings:
    """Create an Ollama embeddings instance."""
    if OllamaEmbeddings is None:
        logger.error("langchain_ollama_not_installed")
        sys.exit(1)
    embedder = OllamaEmbeddings(base_url=base_url, model=model)
    logger.info("embedder_initialised", model=model, base_url=base_url)
    return embedder


def embed_product_text(product: Dict[str, Any]) -> str:
    """Build the text to embed from a product's name, description, and tags."""
    name = product.get("name", "")
    desc = product.get("description", "")
    tags = product.get("tags", [])
    tag_str = " ".join(tags)
    return f"{name}: {desc} Tags: {tag_str}"


# ──────────────────────────────────────────────
# Upsert
# ──────────────────────────────────────────────

def upsert_products(
    client: QdrantClient,
    collection_name: str,
    products: List[Dict[str, Any]],
    embedder: OllamaEmbeddings,
    batch_size: int = 50,
) -> int:
    """Embed products and upsert them into Qdrant in batches.

    Returns the number of successfully upserted products.
    """
    total = len(products)
    upserted = 0

    for start_idx in range(0, total, batch_size):
        batch = products[start_idx : start_idx + batch_size]
        points: List[qdrant_models.PointStruct] = []

        for product in batch:
            text = embed_product_text(product)
            try:
                vector = embedder.embed_query(text)
            except Exception as exc:
                logger.error(
                    "embedding_failed",
                    product_id=product.get("product_id"),
                    error=str(exc),
                )
                continue

            payload = {
                "product_id": product.get("product_id", ""),
                "name": product.get("name", ""),
                "category": product.get("category", ""),
                "price": product.get("price", 0.0),
                "tags": product.get("tags", []),
            }
            points.append(
                qdrant_models.PointStruct(
                    id=int(hashlib.sha256(product.get("product_id", "").encode()).hexdigest(), 16) % (2**63),
                    vector=vector,
                    payload=payload,
                )
            )

        if points:
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True,
                )
                upserted += len(points)
            except Exception as exc:
                logger.error("upsert_batch_failed", batch_start=start_idx, error=str(exc))

        pct = (start_idx + len(batch)) / total * 100
        logger.info(
            "embedding_progress",
            processed=start_idx + len(batch),
            total=total,
            percent=f"{pct:.0f}%",
            batch_upserted=len(points),
        )
        print(f"  Progress: {start_idx + len(batch)} / {total} ({pct:.0f}%)")

    return upserted


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed product catalog into Qdrant vector store.",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop and recreate the Qdrant collection before upserting.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Number of products to embed per batch (default: 50)",
    )
    parser.add_argument(
        "--catalog", type=str, default=CATALOG_PATH,
        help="Path to product_catalog.json (default: data/product_catalog.json)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load catalog and show sample embeddings without writing to Qdrant.",
    )
    args = parser.parse_args()

    setup_logging(service_name="embed-catalog")
    logger.info("starting", catalog=args.catalog, reset=args.reset, dry_run=args.dry_run)

    # ── Load catalog ──
    products = load_catalog(args.catalog)

    if args.dry_run:
        print(f"\n  Dry-run mode — loaded {len(products)} products.")
        sample = products[0]
        text = embed_product_text(sample)
        print(f"  Sample product: {sample['product_id']}")
        print(f"  Embed text: {text[:120]}...")
        print(f"  Embedding dim: {EMBEDDING_DIM}")
        print("  ✅ Dry-run complete. No data written.\n")
        return

    # ── Connect to Qdrant ──
    client = connect_qdrant()
    ensure_collection(client, reset=args.reset)

    # ── Build embedder ──
    embedder = build_embedder()

    # ── Embed & upsert ──
    logger.info("embedding_started", product_count=len(products))
    start = time.time()
    upserted = upsert_products(client, QDRANT_COLLECTION, products, embedder, args.batch_size)
    elapsed = time.time() - start

    print()
    print("  Embedding complete.")
    print(f"  Products in catalog:  {len(products)}")
    print(f"  Vectors upserted:     {upserted}")
    print(f"  Time:                 {elapsed:.1f}s")
    print(f"  Rate:                 {upserted / elapsed:.1f} products/s" if elapsed > 0 else "  Rate: N/A")
    print(f"  Collection:           {QDRANT_COLLECTION}")
    print()

    # Verify
    info = client.get_collection(QDRANT_COLLECTION)
    print(f"  Collection vector count: {info.points_count}")
    print()


if __name__ == "__main__":
    main()
