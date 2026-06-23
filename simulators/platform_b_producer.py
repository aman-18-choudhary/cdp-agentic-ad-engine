#!/usr/bin/env python3
"""Platform B event producer for the CDP Agentic Ad Engine.

Reads the Platform B clickstream CSV and emits each row as a JSON
event to the Redpanda (Kafka-compatible) topic ``platform-b-events``.

Usage:
    python simulators/platform_b_producer.py \\
        --csv data/platform_b_events.csv \\
        --bootstrap-servers localhost:19093 \\
        --throttle 100 \\
        --seed 42
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from aiokafka import AIOKafkaProducer
except ImportError:
    AIOKafkaProducer = None

from common.logging import setup_logging, get_logger

logger = get_logger("platform_b_producer")

CSV_FIELDS = [
    "session_id", "event_time", "event_type", "product_id",
    "platform", "device_type", "ip_range", "city", "country",
    "user_agent", "hashed_email",
]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Platform B Event Producer — emits CSV rows to Redpanda topic.",
    )
    parser.add_argument(
        "--csv", type=str, default="data/platform_b_events.csv",
        help="Path to Platform B events CSV (default: data/platform_b_events.csv)",
    )
    parser.add_argument(
        "--bootstrap-servers", type=str, default="localhost:19093",
        help="Redpanda/Kafka bootstrap servers (default: localhost:19093)",
    )
    parser.add_argument(
        "--topic", type=str, default="platform-b-events",
        help="Kafka topic name (default: platform-b-events)",
    )
    parser.add_argument(
        "--throttle", type=int, default=0,
        help="Target events per second. 0 = no throttling (default: 0)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--max-events", type=int, default=0,
        help="Max events to emit. 0 = all (default: 0)",
    )
    return parser.parse_args(argv)


def read_csv_rows(csv_path: str) -> List[Dict[str, Any]]:
    """Read all rows from a CSV file and return as list of dicts."""
    if not os.path.exists(csv_path):
        logger.error("csv_file_not_found", path=csv_path)
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    logger.info("csv_rows_loaded", path=csv_path, count=len(rows))
    return rows


def enrich_row(row: Dict[str, Any]) -> bytes:
    """Convert a CSV row into a JSON byte-string matching the
    :class:`common.schemas.ClickstreamEvent` schema.
    """
    payload = {
        "platform": "B",
        "session_id": row.get("session_id", ""),
        "event_type": row.get("event_type", "view"),
        "product_id": row.get("product_id", ""),
        "event_time": row.get("event_time", datetime.utcnow().isoformat() + "Z"),
        "device_type": row.get("device_type", "desktop"),
        "ip_range": row.get("ip_range", ""),
        "location": {
            "city": row.get("city", ""),
            "country": row.get("country", ""),
        },
        "user_agent": row.get("user_agent", ""),
        "hashed_email": row.get("hashed_email") or None,
    }
    return json.dumps(payload, default=str).encode("utf-8")


def _throttle_delay(throttle: int) -> float:
    if throttle <= 0:
        return 0.0
    return 1.0 / throttle


async def produce(
    csv_path: str,
    bootstrap_servers: str,
    topic: str,
    throttle: int,
    max_events: int,
) -> int:
    """Read CSV rows and emit each to the Kafka topic."""
    rows = read_csv_rows(csv_path)
    if max_events > 0:
        rows = rows[:max_events]

    delay = _throttle_delay(throttle)
    produced = 0

    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        client_id="platform-b-producer",
        acks="all",
        compression_type="gzip",
        linger_ms=10,
    )

    try:
        await producer.start()
        logger.info("producer_started", bootstrap_servers=bootstrap_servers, topic=topic)

        for idx, row in enumerate(rows, start=1):
            message = enrich_row(row)

            try:
                await producer.send(topic, value=message)
                produced += 1
            except Exception as exc:
                logger.error("send_failed", row=idx, error=str(exc))
                continue

            if delay > 0:
                await asyncio.sleep(delay)

            if idx % 500 == 0:
                logger.debug("progress", produced=produced, total=len(rows))

        await producer.flush()
        logger.info("production_complete", produced=produced)

    except asyncio.CancelledError:
        logger.warning("production_cancelled", produced=produced)
    except Exception as exc:
        logger.error("production_failed", error=str(exc))
        raise
    finally:
        await producer.stop()

    return produced


async def main_async() -> None:
    args = parse_args()
    setup_logging(service_name="platform-b-producer")

    logger.info(
        "starting",
        csv=args.csv,
        bootstrap=args.bootstrap_servers,
        topic=args.topic,
        throttle=args.throttle,
        max_events=args.max_events,
    )

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("signal_received", signal="SIGINT/SIGTERM")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    produce_task = asyncio.create_task(
        produce(
            csv_path=args.csv,
            bootstrap_servers=args.bootstrap_servers,
            topic=args.topic,
            throttle=args.throttle,
            max_events=args.max_events,
        )
    )

    done, _ = await asyncio.wait(
        [produce_task, asyncio.create_task(stop_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if stop_event.is_set():
        produce_task.cancel()
        try:
            await produce_task
        except asyncio.CancelledError:
            pass


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
