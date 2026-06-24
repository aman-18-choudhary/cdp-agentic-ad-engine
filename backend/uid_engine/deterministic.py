#!/usr/bin/env python3
"""Deterministic Identity Matcher.

Matches two sessions based on hard identifiers:
    - **Hashed email**: if both sessions contain a non-null ``hashed_email``
      and they match exactly, the sessions belong to the same user.
    - **Device fingerprint**: a SHA-256 hash of ``user_agent`` + ``device_type``.
      If both fingerprints match, the sessions belong to the same user
      (same physical device).

Returns an :class:`~common.schemas.IdentityMatchResult` with
``confidence = 1.0`` since the match is deterministic.

Usage:
    python uid_engine/deterministic.py  # runs self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.logging import setup_logging, get_logger
from common.schemas import IdentityMatchResult, MatchMethod

logger = get_logger("uid_engine.deterministic")


# ──────────────────────────────────────────────
# Device Fingerprint
# ──────────────────────────────────────────────

def compute_device_fingerprint(user_agent: str, device_type: str) -> str:
    """Create a SHA-256 fingerprint from device characteristics.

    Two sessions that share the exact same device are highly likely
    to belong to the same user (shared desktop / mobile device).
    """
    raw = f"{user_agent}||{device_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────
# Match
# ──────────────────────────────────────────────

def match_sessions(
    session_a: Dict[str, Any],
    session_b: Dict[str, Any],
) -> IdentityMatchResult:
    """Attempt a deterministic identity match between two sessions.

    Parameters
    ----------
    session_a, session_b:
        Dicts with at least the keys ``hashed_email``, ``user_agent``,
        and ``device_type``.

    Returns
    -------
    IdentityMatchResult
        ``match = True`` when a deterministic link is found.
    """
    email_a = session_a.get("hashed_email") or None
    email_b = session_b.get("hashed_email") or None

    # ── Email match (highest confidence) ──
    if email_a and email_b and email_a == email_b:
        global_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"email:{email_a}"))
        logger.info(
            "deterministic_match",
            method="email",
            session_a=session_a.get("session_id"),
            session_b=session_b.get("session_id"),
            global_uid=global_uid,
        )
        return IdentityMatchResult(
            match=True,
            global_uid=global_uid,
            method=MatchMethod.deterministic,
            score=1.0,
            details={"matched_on": "hashed_email"},
        )

    # ── Device fingerprint match ──
    ua_a = session_a.get("user_agent", "")
    dt_a = session_a.get("device_type", "")
    ua_b = session_b.get("user_agent", "")
    dt_b = session_b.get("device_type", "")

    fp_a = compute_device_fingerprint(ua_a, dt_a)
    fp_b = compute_device_fingerprint(ua_b, dt_b)

    if fp_a == fp_b:
        global_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"device:{fp_a}"))
        logger.info(
            "deterministic_match",
            method="device_fingerprint",
            session_a=session_a.get("session_id"),
            session_b=session_b.get("session_id"),
            global_uid=global_uid,
        )
        return IdentityMatchResult(
            match=True,
            global_uid=global_uid,
            method=MatchMethod.deterministic,
            score=1.0,
            details={"matched_on": "device_fingerprint"},
        )

    # ── No deterministic match ──
    return IdentityMatchResult(
        match=False,
        global_uid=None,
        method=MatchMethod.none,
        score=0.0,
        details=None,
    )


# ──────────────────────────────────────────────
# Self-Test
# ──────────────────────────────────────────────

def _self_test() -> None:
    """Run a quick sanity check against built-in examples."""
    setup_logging(service_name="deterministic-self-test")

    # Test 1: matching emails
    a = {"session_id": "sess_a", "hashed_email": "abc123", "user_agent": "Mozilla", "device_type": "mobile"}
    b = {"session_id": "sess_b", "hashed_email": "abc123", "user_agent": "Chrome", "device_type": "desktop"}
    r = match_sessions(a, b)
    assert r.match and r.method == MatchMethod.deterministic and r.score == 1.0
    logger.info("test_1_email_match", passed=True, global_uid=r.global_uid)

    # Test 2: matching device fingerprint
    c = {"session_id": "sess_c", "hashed_email": None, "user_agent": "Mozilla/5", "device_type": "mobile"}
    d = {"session_id": "sess_d", "hashed_email": None, "user_agent": "Mozilla/5", "device_type": "mobile"}
    r = match_sessions(c, d)
    assert r.match and r.method == MatchMethod.deterministic and r.score == 1.0
    logger.info("test_2_device_match", passed=True, global_uid=r.global_uid)

    # Test 3: no match
    e = {"session_id": "sess_e", "hashed_email": None, "user_agent": "Safari", "device_type": "tablet"}
    r = match_sessions(c, e)
    assert not r.match and r.method == MatchMethod.none
    logger.info("test_3_no_match", passed=True)

    print("All deterministic self-tests passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Identity Matcher")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
    else:
        _self_test()


if __name__ == "__main__":
    main()
