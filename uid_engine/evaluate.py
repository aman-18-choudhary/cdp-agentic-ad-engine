#!/usr/bin/env python3
"""Identity Resolution Evaluation Script.

Loads the synthetic ground truth along with the platform event CSVs,
runs every overlapping pair through both the deterministic and
probabilistic matchers, and reports Precision, Recall, and F1-Score
for each method individually and combined.

Usage:
    python uid_engine/evaluate.py \\
        --ground-truth data/synthetic_ground_truth.csv \\
        --platform-a data/platform_a_events.csv \\
        --platform-b data/platform_b_events.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.logging import setup_logging, get_logger
from common.schemas import IdentityMatchResult, MatchMethod
from uid_engine.deterministic import match_sessions as deterministic_match
from uid_engine.probabilistic import score_sessions as probabilistic_match, set_threshold

logger = get_logger("uid_engine.evaluate")

MIN_ACCEPTABLE_F1 = 0.85


# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────

def load_events_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Load events from a platform CSV and return as a list of dicts."""
    path = Path(csv_path)
    if not path.exists():
        logger.error("file_not_found", path=str(path))
        sys.exit(1)

    rows: List[Dict[str, Any]] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalise field names (handle both city/location_city)
            if "city" in row and "location_city" not in row:
                row["location_city"] = row["city"]
            if "country" in row and "location_country" not in row:
                row["location_country"] = row["country"]
            rows.append(row)

    logger.info("events_loaded", path=str(path), count=len(rows))
    return rows


def load_ground_truth(csv_path: str) -> List[Dict[str, Any]]:
    """Load synthetic ground truth records."""
    path = Path(csv_path)
    if not path.exists():
        logger.error("file_not_found", path=str(path))
        sys.exit(1)

    records: List[Dict[str, Any]] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    logger.info("ground_truth_loaded", path=str(path), count=len(records))
    return records


def group_into_sessions(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group flat event rows into session dicts keyed by ``session_id``.

    Each session aggregates:
        - ``session_id``, ``platform``, ``device_type``, ``ip_range``,
          ``location_city``, ``location_country``, ``user_agent``,
          ``hashed_email`` (taken from the first event)
        - ``event_types`` — list of all event types in the session
        - ``event_times`` — list of parsed :class:`datetime` objects
        - ``product_ids`` — list of products interacted with
    """
    sessions: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        sid = ev.get("session_id", "")
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "platform": ev.get("platform", ""),
                "device_type": ev.get("device_type", ""),
                "ip_range": ev.get("ip_range", ""),
                "location_city": ev.get("location_city", ev.get("city", "")),
                "location_country": ev.get("location_country", ev.get("country", "")),
                "user_agent": ev.get("user_agent", ""),
                "hashed_email": ev.get("hashed_email") or None,
                "event_types": [],
                "event_times": [],
                "product_ids": [],
            }

        sessions[sid]["event_types"].append(ev.get("event_type", ""))
        sessions[sid]["product_ids"].append(ev.get("product_id", ""))

        try:
            parsed = datetime.fromisoformat(
                ev.get("event_time", "").replace("Z", "+00:00").replace(" ", "T")
            )
            sessions[sid]["event_times"].append(parsed)
        except (ValueError, TypeError):
            pass

    return sessions


# ──────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────

def build_session_pairs(
    ground_truth: List[Dict[str, Any]],
    sessions_a: Dict[str, Dict[str, Any]],
    sessions_b: Dict[str, Dict[str, Any]],
    negative_ratio: float = 2.0,
) -> Tuple[
    List[Tuple[Dict[str, Any], Dict[str, Any], bool, str, str]],
    List[Tuple[Dict[str, Any], Dict[str, Any], bool, str, str]],
]:
    """Build positive and negative session pairs for evaluation.

    Returns
    -------
    Tuple of (positive_pairs, negative_pairs).
    Each pair is (session_a, session_b, is_match, expected_method, global_uid).
    """
    import random
    rng = random.Random(42)

    positive: List[Tuple[Dict[str, Any], Dict[str, Any], bool, str, str]] = []
    missing_a = 0
    missing_b = 0

    for gt in ground_truth:
        sid_a = gt.get("session_id_a", "")
        sid_b = gt.get("session_id_b", "")

        sess_a = sessions_a.get(sid_a)
        sess_b = sessions_b.get(sid_b)

        if not sess_a:
            missing_a += 1
            continue
        if not sess_b:
            missing_b += 1
            continue

        positive.append((
            sess_a,
            sess_b,
            True,
            gt.get("expected_method", "probabilistic"),
            gt.get("global_uid", ""),
        ))

    if missing_a or missing_b:
        logger.warning(
            "missing_sessions_in_ground_truth",
            missing_in_a=missing_a,
            missing_in_b=missing_b,
        )

    # Build negative pairs: sessions NOT in ground truth
    gt_a_ids = {gt["session_id_a"] for gt in ground_truth}
    gt_b_ids = {gt["session_id_b"] for gt in ground_truth}
    non_overlap_a = [s for sid, s in sessions_a.items() if sid not in gt_a_ids]
    non_overlap_b = [s for sid, s in sessions_b.items() if sid not in gt_b_ids]

    num_negatives = int(len(positive) * negative_ratio)
    negative: List[Tuple[Dict[str, Any], Dict[str, Any], bool, str, str]] = []

    for _ in range(num_negatives):
        if not non_overlap_a or not non_overlap_b:
            break
        sa = rng.choice(non_overlap_a)
        sb = rng.choice(non_overlap_b)
        negative.append((sa, sb, False, "none", ""))

    logger.info(
        "evaluation_pairs_built",
        positive=len(positive),
        negative=len(negative),
    )
    return positive, negative


# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────

class Metrics:
    """Precision, Recall, and F1-Score."""

    def __init__(self, name: str = "") -> None:
        self.name = name
        self.tp: int = 0
        self.fp: int = 0
        self.fn: int = 0

    def add(self, predicted_match: bool, actual_match: bool) -> None:
        if predicted_match and actual_match:
            self.tp += 1
        elif predicted_match and not actual_match:
            self.fp += 1
        elif not predicted_match and actual_match:
            self.fn += 1

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        denom = p + r
        return 2 * p * r / denom if denom > 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"{self.name:<18}  "
            f"Precision: {self.precision:.4f}   "
            f"Recall: {self.recall:.4f}   "
            f"F1: {self.f1:.4f}   "
            f"(TP={self.tp} FP={self.fp} FN={self.fn})"
        )


def evaluate_method(
    name: str,
    positive_pairs: List[Tuple],
    negative_pairs: List[Tuple],
    match_fn,
    method_filter: Optional[str] = None,
) -> Metrics:
    """Run *match_fn* on all pairs and collect metrics.

    Parameters
    ----------
    name: Label for the Metrics report.
    match_fn: A function that takes (session_a, session_b) and returns
        an ``IdentityMatchResult``.
    method_filter: If ``"deterministic"``, only evaluate pairs whose
        ``expected_method`` matches.  ``"probabilistic"`` similarly.
        ``None`` evaluates every pair.
    """
    metrics = Metrics(name)

    for pair_set, is_match in [(positive_pairs, True), (negative_pairs, False)]:
        for sa, sb, _, expected_method, expected_uid in pair_set:
            if method_filter and expected_method != method_filter:
                continue
            result = match_fn(sa, sb)
            metrics.add(predicted_match=result.match, actual_match=is_match)

    return metrics


# ──────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────

def print_report(det_metrics: Metrics, prob_metrics: Metrics, combined: Metrics) -> None:
    """Print a formatted evaluation report."""
    print()
    print("=" * 72)
    print("  IDENTITY RESOLUTION EVALUATION REPORT")
    print("=" * 72)
    print()

    header = "  {:<18} {:>12} {:>12} {:>12} {:>8} {:>8} {:>8}"
    print(header.format("Method", "Precision", "Recall", "F1", "TP", "FP", "FN"))
    print("  " + "-" * 70)

    for m in (det_metrics, prob_metrics, combined):
        print(
            "  {:<18} {:>12.4f} {:>12.4f} {:>12.4f} {:>8} {:>8} {:>8}".format(
                m.name, m.precision, m.recall, m.f1, m.tp, m.fp, m.fn,
            )
        )

    print()
    print(f"  Minimum acceptable combined F1: {MIN_ACCEPTABLE_F1:.2f}")
    print(f"  Combined F1: {combined.f1:.4f}")
    print()

    if combined.f1 >= MIN_ACCEPTABLE_F1:
        print("  ✅ PASS — Combined F1 meets the 0.85 threshold.")
    else:
        print("  ❌ FAIL — Combined F1 below 0.85 threshold.")
    print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate identity resolution accuracy against ground truth.",
    )
    parser.add_argument(
        "--ground-truth", type=str, default="data/synthetic_ground_truth.csv",
        help="Path to synthetic_ground_truth.csv (default: data/synthetic_ground_truth.csv)",
    )
    parser.add_argument(
        "--platform-a", type=str, default="data/platform_a_events.csv",
        help="Path to Platform A events CSV (default: data/platform_a_events.csv)",
    )
    parser.add_argument(
        "--platform-b", type=str, default="data/platform_b_events.csv",
        help="Path to Platform B events CSV (default: data/platform_b_events.csv)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.75,
        help="Probabilistic match threshold (default: 0.75)",
    )
    args = parser.parse_args()

    setup_logging(service_name="identity-evaluation", log_level="INFO")

    set_threshold(args.threshold)

    # Load data
    events_a = load_events_csv(args.platform_a)
    events_b = load_events_csv(args.platform_b)
    ground_truth = load_ground_truth(args.ground_truth)

    # Group into sessions
    sessions_a = group_into_sessions(events_a)
    sessions_b = group_into_sessions(events_b)

    logger.info(
        "data_summary",
        platform_a_sessions=len(sessions_a),
        platform_b_sessions=len(sessions_b),
        ground_truth_records=len(ground_truth),
    )

    # Build evaluation pairs
    positive_pairs, negative_pairs = build_session_pairs(
        ground_truth, sessions_a, sessions_b, negative_ratio=2.0,
    )

    # ── Evaluate Deterministic ──
    det_all = evaluate_method(
        "Deterministic",
        positive_pairs, negative_pairs,
        deterministic_match,
        method_filter=None,
    )
    det_filtered = evaluate_method(
        "Deterministic (det-only)",
        positive_pairs, negative_pairs,
        deterministic_match,
        method_filter="deterministic",
    )

    # ── Evaluate Probabilistic ──
    prob_all = evaluate_method(
        "Probabilistic",
        positive_pairs, negative_pairs,
        probabilistic_match,
        method_filter=None,
    )
    prob_filtered = evaluate_method(
        "Probabilistic (prob-only)",
        positive_pairs, negative_pairs,
        probabilistic_match,
        method_filter="probabilistic",
    )

    # ── Combined ──
    combined = evaluate_method(
        "Combined (any match)",
        positive_pairs, negative_pairs,
        lambda a, b: IdentityMatchResult(
            match=deterministic_match(a, b).match or probabilistic_match(a, b).match,
            global_uid=(
                deterministic_match(a, b).global_uid
                or probabilistic_match(a, b).global_uid
            ),
            method=(
                MatchMethod.deterministic
                if deterministic_match(a, b).match
                else MatchMethod.probabilistic
                if probabilistic_match(a, b).match
                else MatchMethod.none
            ),
            score=max(
                deterministic_match(a, b).score or 0.0,
                probabilistic_match(a, b).score or 0.0,
            ),
        ),
        method_filter=None,
    )

    print_report(det_filtered, prob_filtered, combined)

    # Exit with code 1 if combined F1 is below threshold
    if combined.f1 < MIN_ACCEPTABLE_F1:
        sys.exit(1)


if __name__ == "__main__":
    main()
