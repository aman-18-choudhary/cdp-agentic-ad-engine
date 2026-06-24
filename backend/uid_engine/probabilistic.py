#!/usr/bin/env python3
"""Probabilistic Identity Scorer.

Computes a weighted similarity score (0.0 – 1.0) between two sessions
based on four signals:

    +---------------------+--------+
    | Signal              | Weight |
    +---------------------+--------+
    | IP range (CIDR)     |  0.35  |
    | Location (city)     |  0.25  |
    | Device type         |  0.20  |
    | Time window (hours) |  0.20  |
    +---------------------+--------+

A score >= ``MATCH_THRESHOLD`` (0.75) indicates the sessions likely
belong to the same user and should be merged under one ``global_uid``.

Provides :func:`score_sessions` for a single pair and :func:`batch_score`
for bulk evaluation.

Usage:
    python uid_engine/probabilistic.py  # runs self-test
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.logging import setup_logging, get_logger
from common.schemas import IdentityMatchResult, MatchMethod

logger = get_logger("uid_engine.probabilistic")

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

WEIGHTS = {
    "ip_range": 0.35,
    "location_city": 0.25,
    "device_type": 0.20,
    "time_window": 0.20,
}

MATCH_THRESHOLD = 0.75


# ──────────────────────────────────────────────
# Individual Scorers
# ──────────────────────────────────────────────

def _score_ip_range(ip_range_a: str, ip_range_b: str) -> float:
    """Return 1.0 if both CIDR ranges overlap, 0.0 otherwise.

    Overlap means the two networks share at least one IP address.
    """
    try:
        net_a = ipaddress.ip_network(ip_range_a, strict=False)
        net_b = ipaddress.ip_network(ip_range_b, strict=False)
        return 1.0 if net_a.overlaps(net_b) else 0.0
    except ValueError:
        logger.warning("invalid_ip_range", a=ip_range_a, b=ip_range_b)
        return 0.0


def _score_location_city(city_a: str, city_b: str) -> float:
    """Return 1.0 if both cities match (case-insensitive), 0.0 otherwise."""
    return 1.0 if city_a.strip().lower() == city_b.strip().lower() else 0.0


def _score_device_type(device_a: str, device_b: str) -> float:
    """Return 1.0 if both device types match exactly, 0.0 otherwise."""
    return 1.0 if device_a.strip().lower() == device_b.strip().lower() else 0.0


def _score_time_window(event_times_a: List[datetime], event_times_b: List[datetime]) -> float:
    """Score based on overlap of active browsing hours (0–23).

    Each session's active hours are the set of hours its events occurred
    in.  The score is the Jaccard similarity of the two hour-sets.
    """
    if not event_times_a or not event_times_b:
        return 0.0

    hours_a = {t.hour for t in event_times_a}
    hours_b = {t.hour for t in event_times_b}

    intersection = hours_a & hours_b
    union = hours_a | hours_b

    if not union:
        return 0.0
    return len(intersection) / len(union)


# ──────────────────────────────────────────────
# Score Computation
# ──────────────────────────────────────────────

def _parse_event_times(session: Dict[str, Any]) -> List[datetime]:
    """Extract and parse all event timestamps from a session dict.

    The session may contain a single ``event_time`` (string) or a list
    ``event_times`` (already-parsed datetimes held from bulk evaluation).
    """
    if "event_times" in session and isinstance(session["event_times"], list):
        return session["event_times"]
    raw = session.get("event_time", "")
    if isinstance(raw, list):
        return [datetime.fromisoformat(t.replace("Z", "+00:00").replace(" ", "T")) for t in raw]
    if isinstance(raw, str) and raw:
        return [datetime.fromisoformat(raw.replace("Z", "+00:00").replace(" ", "T"))]
    return []


def score_sessions(
    session_a: Dict[str, Any],
    session_b: Dict[str, Any],
) -> IdentityMatchResult:
    """Compute a weighted probabilistic similarity between two sessions.

    Parameters
    ----------
    session_a, session_b:
        Session dicts with keys ``ip_range``, ``city`` or ``location_city``,
        ``device_type``, and either ``event_time`` (str) or ``event_times``
        (list of :class:`datetime`).

    Returns
    -------
    IdentityMatchResult
    """
    location_city_a = session_a.get("location_city") or session_a.get("city", "")
    location_city_b = session_b.get("location_city") or session_b.get("city", "")
    ip_a = session_a.get("ip_range", "")
    ip_b = session_b.get("ip_range", "")
    dev_a = session_a.get("device_type", "")
    dev_b = session_b.get("device_type", "")

    scores = {
        "ip_range": _score_ip_range(ip_a, ip_b),
        "location_city": _score_location_city(location_city_a, location_city_b),
        "device_type": _score_device_type(dev_a, dev_b),
    }

    times_a = _parse_event_times(session_a)
    times_b = _parse_event_times(session_b)
    scores["time_window"] = _score_time_window(times_a, times_b)

    weighted = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    rounded = round(weighted, 4)

    matched = rounded >= MATCH_THRESHOLD
    global_uid = None
    if matched:
        raw_id = (
            f"{ip_a}|{location_city_a}|{dev_a}|"
            f"{ip_b}|{location_city_b}|{dev_b}"
        )
        global_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id))

    logger.debug(
        "probabilistic_score",
        session_a=session_a.get("session_id"),
        session_b=session_b.get("session_id"),
        matched=matched,
        score=rounded,
        component_scores=scores,
    )

    return IdentityMatchResult(
        match=matched,
        global_uid=global_uid,
        method=MatchMethod.probabilistic if matched else MatchMethod.none,
        score=rounded,
        details={"component_scores": scores} if not matched else {
            "component_scores": scores,
            "matched_on": [k for k, v in scores.items() if v >= 0.5],
        },
    )


# ──────────────────────────────────────────────
# Batch Scoring (for evaluation)
# ──────────────────────────────────────────────

def batch_score(
    session_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
) -> List[IdentityMatchResult]:
    """Score multiple session pairs and return a list of results.

    Useful for bulk evaluation against ground-truth data.

    Parameters
    ----------
    session_pairs:
        List of ``(session_a, session_b)`` tuples.

    Returns
    -------
    List[IdentityMatchResult]
    """
    return [score_sessions(a, b) for a, b in session_pairs]


# ──────────────────────────────────────────────
# Threshold Helper
# ──────────────────────────────────────────────

def set_threshold(value: float) -> None:
    """Override the global match threshold (default 0.75).

    Used during evaluation to test sensitivity.
    """
    global MATCH_THRESHOLD
    MATCH_THRESHOLD = value
    logger.info("threshold_updated", new_threshold=value)


def get_threshold() -> float:
    """Return the current match threshold."""
    return MATCH_THRESHOLD


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

def _self_test() -> None:
    setup_logging(service_name="probabilistic-self-test")

    now = datetime.utcnow()

    # Sessions that SHOULD match (same IP range, city, device, overlapping hours)
    a = {
        "session_id": "sess_a",
        "ip_range": "10.0.1.0/24",
        "city": "New York",
        "device_type": "mobile",
        "event_times": [now, now.replace(hour=10), now.replace(hour=11)],
    }
    b = {
        "session_id": "sess_b",
        "ip_range": "10.0.1.0/24",
        "city": "New York",
        "device_type": "mobile",
        "event_times": [now.replace(hour=10), now.replace(hour=11), now.replace(hour=14)],
    }
    r = score_sessions(a, b)
    assert r.match, f"Expected match, got score={r.score}"
    assert r.score >= MATCH_THRESHOLD, f"Score {r.score} below threshold"
    logger.info("test_match", passed=True, score=r.score)

    # Sessions that should NOT match (different everything)
    c = {
        "session_id": "sess_c",
        "ip_range": "192.168.5.0/24",
        "city": "Berlin",
        "device_type": "desktop",
        "event_times": [now.replace(hour=2), now.replace(hour=3)],
    }
    r = score_sessions(a, c)
    assert not r.match, f"Expected no match, got score={r.score}"
    assert r.score < MATCH_THRESHOLD
    logger.info("test_no_match", passed=True, score=r.score)

    # Batch test
    pairs = [(a, b), (a, c)]
    results = batch_score(pairs)
    assert len(results) == 2
    assert results[0].match
    assert not results[1].match
    logger.info("test_batch", passed=True)

    print("All probabilistic self-tests passed.")
    print(f"  Match threshold: {MATCH_THRESHOLD}")
    print(f"  Weights: {WEIGHTS}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probabilistic Identity Scorer")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
    else:
        _self_test()


if __name__ == "__main__":
    main()
