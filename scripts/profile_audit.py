#!/usr/bin/env python3
"""Profile-Level Audit — replaces manual profile-quality calculations.

Loads ground truth from data/synthetic_ground_truth.csv and MongoDB
unified_profiles, then computes:

  - Correct profiles: profiles containing exactly one GT identity
  - Over-merged profiles: profiles containing multiple GT identities
  - Split identities: GT identities spread across multiple profiles
  - Profile precision: correct / (correct + over-merged)
  - Profile recall: correct / (correct + split)
  - Profile F1: harmonic mean of precision and recall

Usage:
    python scripts/profile_audit.py [--mongo-uri ...]
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
GT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_ground_truth.csv"))


def load_ground_truth(path: str) -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []
    with open(path) as f:
        for row in csv.DictReader(f):
            pairs.append(row)
    return pairs


def load_profiles(mongo_uri: str) -> List[Dict[str, Any]]:
    from pymongo import MongoClient
    client = MongoClient(mongo_uri)
    db = client["cdp"]
    profiles = list(db.unified_profiles.find({}))
    client.close()
    return profiles


def build_session_uid_map(profiles: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for p in profiles:
        uid = str(p["_id"])
        for s in p.get("sessions", []):
            mapping[s["session_id"]] = uid
    return mapping


def build_uid_session_map(profiles: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for p in profiles:
        uid = str(p["_id"])
        mapping[uid] = set()
        for s in p.get("sessions", []):
            mapping[uid].add(s["session_id"])
    return mapping


def audit() -> Dict[str, Any]:
    print("=" * 72)
    print("  PROFILE-LEVEL AUDIT")
    print("=" * 72)

    # 1. Load ground truth — build identity groups
    gt_pairs = load_ground_truth(GT_PATH)
    print(f"\n  Ground truth pairs: {len(gt_pairs)}")

    # Build global_uid → set of session IDs from ground truth
    gt_identity_groups: Dict[str, Set[str]] = defaultdict(set)
    for p in gt_pairs:
        gt_uid = p["global_uid"]
        gt_identity_groups[gt_uid].add(p["session_id_a"])
        gt_identity_groups[gt_uid].add(p["session_id_b"])
    print(f"  Ground truth identities: {len(gt_identity_groups)}")

    gt_all_sessions: Set[str] = set()
    for sids in gt_identity_groups.values():
        gt_all_sessions.update(sids)
    print(f"  Ground truth session IDs: {len(gt_all_sessions)}")

    # 2. Load profiles
    print("\n  Loading unified_profiles from MongoDB...")
    profiles = load_profiles(MONGODB_URI)
    session_uid = build_session_uid_map(profiles)
    uid_sessions = build_uid_session_map(profiles)
    print(f"  Profiles: {len(profiles)}")
    print(f"  Unique session IDs in profiles: {len(session_uid)}")

    gt_found = sum(1 for s in gt_all_sessions if s in session_uid)
    gt_missing = len(gt_all_sessions) - gt_found
    print(f"  GT sessions found in profiles: {gt_found}")
    print(f"  GT sessions missing from profiles: {gt_missing}")

    # 3. Evaluate each profile against ground truth identities
    # A "correct" profile maps sessions from exactly one GT identity
    # An "over-merged" profile maps sessions from multiple GT identities
    # A "split" identity has sessions across multiple profiles

    # Build reverse map: profile_uid → set of GT identities it contains
    profile_gt_identities: Dict[str, Set[str]] = defaultdict(set)
    # Need to map session_id → gt_uid
    session_to_gt_uid: Dict[str, str] = {}
    for gt_uid, sids in gt_identity_groups.items():
        for sid in sids:
            session_to_gt_uid[sid] = gt_uid

    for profile_uid, sess_ids in uid_sessions.items():
        for sid in sess_ids:
            if sid in session_to_gt_uid:
                profile_gt_identities[profile_uid].add(session_to_gt_uid[sid])

    # Build reverse: gt_identity → set of profile_uids
    gt_profile_uids: Dict[str, Set[str]] = defaultdict(set)
    for profile_uid, gt_ids in profile_gt_identities.items():
        for gt_id in gt_ids:
            gt_profile_uids[gt_id].add(profile_uid)

    correct_profiles = 0
    over_merged_profiles = 0
    split_identities = 0
    neutral_profiles = 0  # profiles with no GT sessions

    for profile_uid, gt_ids in profile_gt_identities.items():
        if len(gt_ids) == 0:
            neutral_profiles += 1
        elif len(gt_ids) == 1:
            correct_profiles += 1
        else:
            over_merged_profiles += 1

    for gt_id, profile_ids in gt_profile_uids.items():
        if len(profile_ids) > 1:
            split_identities += 1

    # Compute metrics
    total_with_gt = correct_profiles + over_merged_profiles
    precision = correct_profiles / total_with_gt if total_with_gt > 0 else 0.0
    recall = correct_profiles / (correct_profiles + split_identities) if (correct_profiles + split_identities) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"\n  {'─'*60}")
    print(f"  {'Metric':<30} {'Value':<15}")
    print(f"  {'─'*60}")
    print(f"  {'Correct profiles':<30} {correct_profiles:<15}")
    print(f"  {'Over-merged profiles':<30} {over_merged_profiles:<15}")
    print(f"  {'Split identities':<30} {split_identities:<15}")
    print(f"  {'Neutral profiles (no GT)':<30} {neutral_profiles:<15}")
    print(f"  {'─'*60}")
    print(f"  {'Profile Precision':<30} {precision:<15.4f}")
    print(f"  {'Profile Recall':<30} {recall:<15.4f}")
    print(f"  {'Profile F1 Score':<30} {f1:<15.4f}")
    print(f"  {'─'*60}")

    # Over-merge breakdown by profile
    if over_merged_profiles > 0:
        print(f"\n  Over-merged profile details:")
        om_list = sorted(
            [(len(gt_ids), puid, gt_ids) for puid, gt_ids in profile_gt_identities.items() if len(gt_ids) > 1],
            key=lambda x: -x[0],
        )
        for count, puid, gt_ids in om_list[:10]:
            print(f"    uid={puid[:20]}... identities={count} gt_ids={list(gt_ids)[:5]}")

    # Summary
    print(f"\n  {'='*60}")
    print(f"  Profile Precision: {precision:.4f}  ({correct_profiles} / {total_with_gt})")
    print(f"  Profile Recall:    {recall:.4f}  ({correct_profiles} / {correct_profiles + split_identities})")
    print(f"  Profile F1:        {f1:.4f}")
    print(f"  {'='*60}")
    print()

    return {
        "correct_profiles": correct_profiles,
        "over_merged_profiles": over_merged_profiles,
        "split_identities": split_identities,
        "neutral_profiles": neutral_profiles,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


if __name__ == "__main__":
    audit()
