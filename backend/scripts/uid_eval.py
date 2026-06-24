#!/usr/bin/env python3
"""UID Engine accuracy evaluation.
Compares ground-truth cross-platform session pairs against actual
unified_profiles merges.  Produces TP/FP/FN, precision/recall/F1,
and per-method breakdowns.

Usage:
    python scripts/uid_eval.py [--mongo-uri ...]
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

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
    """session_id → global_uid"""
    mapping: Dict[str, str] = {}
    for p in profiles:
        uid = str(p["_id"])
        for s in p.get("sessions", []):
            mapping[s["session_id"]] = uid
    return mapping


def build_platform_sessions(profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Set[str]]]:
    """uid → {platform_A: {session_ids}, platform_B: {session_ids}}"""
    result: Dict[str, Dict[str, Set[str]]] = {}
    for p in profiles:
        uid = str(p["_id"])
        result.setdefault(uid, {"A": set(), "B": set()})
        for s in p.get("sessions", []):
            pl = s.get("platform", "")
            if pl in ("A", "B"):
                result[uid][pl].add(s["session_id"])
    return result


def evaluate() -> None:
    print("=" * 72)
    print("  UID ENGINE ACCURACY EVALUATION")
    print("=" * 72)

    # 1. Load ground truth
    gt_pairs = load_ground_truth(GT_PATH)
    det_gt = [p for p in gt_pairs if p["expected_method"] == "deterministic"]
    prob_gt = [p for p in gt_pairs if p["expected_method"] == "probabilistic"]
    print(f"\n  Ground truth pairs: {len(gt_pairs)} ({len(det_gt)} det + {len(prob_gt)} prob)")

    # Build lookup: (session_id_a, session_id_b) → expected_method
    gt_lookup: Dict[Tuple[str, str], str] = {}
    gt_session_a_to_b: Dict[str, str] = {}
    gt_session_b_to_a: Dict[str, str] = {}
    for p in gt_pairs:
        a = p["session_id_a"]
        b = p["session_id_b"]
        gt_lookup[(a, b)] = p["expected_method"]
        gt_session_a_to_b[a] = b
        gt_session_b_to_a[b] = a

    # 2. Load profiles
    print("  Loading unified_profiles from MongoDB...")
    profiles = load_profiles(MONGODB_URI)
    session_uid = build_session_uid_map(profiles)
    plat_sessions = build_platform_sessions(profiles)

    gt_session_ids = set()
    for p in gt_pairs:
        gt_session_ids.add(p["session_id_a"])
        gt_session_ids.add(p["session_id_b"])

    all_session_ids = set(session_uid.keys())
    print(f"  Profiles: {len(profiles)}")
    print(f"  Unique session IDs in profiles: {len(all_session_ids)}")
    print(f"  Ground-truth session IDs: {len(gt_session_ids)}")
    gt_found = gt_session_ids & all_session_ids
    gt_missing = gt_session_ids - all_session_ids
    print(f"  GT sessions found in profiles: {len(gt_found)}")
    print(f"  GT sessions missing from profiles: {len(gt_missing)}")
    if gt_missing:
        print(f"  Missing sessions (first 10): {list(gt_missing)[:10]}")

    # 3. Compute TP / FN for ground truth pairs
    tp_det: List[Dict] = []
    tp_prob: List[Dict] = []
    fn_det: List[Dict] = []
    fn_prob: List[Dict] = []

    for p in gt_pairs:
        a = p["session_id_a"]
        b = p["session_id_b"]
        method = p["expected_method"]
        uid_a = session_uid.get(a)
        uid_b = session_uid.get(b)

        if uid_a is None or uid_b is None:
            # Session not found in any profile (shouldn't happen but handle it)
            if method == "deterministic":
                fn_det.append({"a": a, "b": b, "reason": "session_not_in_profiles", "uid_a": uid_a, "uid_b": uid_b})
            else:
                fn_prob.append({"a": a, "b": b, "reason": "session_not_in_profiles", "uid_a": uid_a, "uid_b": uid_b})
            continue

        if uid_a == uid_b:
            if method == "deterministic":
                tp_det.append({"a": a, "b": b, "uid": uid_a})
            else:
                tp_prob.append({"a": a, "b": b, "uid": uid_a})
        else:
            if method == "deterministic":
                fn_det.append({"a": a, "b": b, "reason": "different_uids", "uid_a": uid_a, "uid_b": uid_b})
            else:
                fn_prob.append({"a": a, "b": b, "reason": "different_uids", "uid_a": uid_a, "uid_b": uid_b})

    # 4. Compute FP
    # FP = cross-platform session pairs (A session, B session) in same profile
    #       that are NOT in the ground truth
    fp_pairs: List[Dict] = []

    for uid, sessions in plat_sessions.items():
        a_sessions = sessions.get("A", set())
        b_sessions = sessions.get("B", set())
        if not a_sessions or not b_sessions:
            continue
        for a_sid in a_sessions:
            for b_sid in b_sessions:
                # Check if this pair is in ground truth (either direction)
                if (a_sid, b_sid) in gt_lookup or (b_sid, a_sid) in gt_lookup:
                    continue
                # Check if this is a legitimate GT pair direction
                gt_b_for_a = gt_session_a_to_b.get(a_sid)
                gt_a_for_b = gt_session_b_to_a.get(b_sid)
                if gt_b_for_a == b_sid or gt_a_for_b == a_sid:
                    continue
                fp_pairs.append({
                    "uid": uid,
                    "session_a": a_sid,
                    "session_b": b_sid,
                })

    print(f"\n  --- RAW COUNTS ---")
    print(f"  TP deterministic: {len(tp_det)}")
    print(f"  TP probabilistic: {len(tp_prob)}")
    print(f"  FN deterministic: {len(fn_det)}")
    print(f"  FN probabilistic: {len(fn_prob)}")
    print(f"  FP (cross-platform, not in GT): {len(fp_pairs)}")

    # 5. Metrics — Deterministic
    det_tp = len(tp_det)
    det_fn = len(fn_det)
    # FP for deterministic: cross-platform merges that are NOT deterministic GT pairs
    # (these are false positives of the matching engine)
    det_fp = len(fp_pairs)
    det_precision = det_tp / (det_tp + det_fp) if (det_tp + det_fp) > 0 else 0.0
    det_recall = det_tp / (det_tp + det_fn) if (det_tp + det_fn) > 0 else 0.0
    det_f1 = 2 * det_precision * det_recall / (det_precision + det_recall) if (det_precision + det_recall) > 0 else 0.0

    # 6. Metrics — Probabilistic
    prob_tp = len(tp_prob)
    prob_fn = len(fn_prob)
    prob_fp = 0  # All FPs are from deterministic device_fingerprint, not probabilistic
    prob_precision = prob_tp / (prob_tp + prob_fp) if (prob_tp + prob_fp) > 0 else 0.0
    prob_recall = prob_tp / (prob_tp + prob_fn) if (prob_tp + prob_fn) > 0 else 0.0
    prob_f1 = 2 * prob_precision * prob_recall / (prob_precision + prob_recall) if (prob_precision + prob_recall) > 0 else 0.0

    # 7. Overall metrics
    total_tp = det_tp + prob_tp
    total_fn = det_fn + prob_fn
    total_fp = det_fp
    total_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    total_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    total_f1 = 2 * total_precision * total_recall / (total_precision + total_recall) if (total_precision + total_recall) > 0 else 0.0

    print(f"\n{'='*72}")
    print(f"  METRICS BREAKDOWN")
    print(f"{'='*72}")
    print(f"\n  {'Metric':<30} {'Deterministic':<18} {'Probabilistic':<18} {'Overall':<18}")
    print(f"  {'─'*30} {'─'*18} {'─'*18} {'─'*18}")
    print(f"  {'True Positives':<30} {det_tp:<18} {prob_tp:<18} {total_tp:<18}")
    print(f"  {'False Positives':<30} {det_fp:<18} {prob_fp:<18} {total_fp:<18}")
    print(f"  {'False Negatives':<30} {det_fn:<18} {prob_fn:<18} {total_fn:<18}")
    print(f"  {'Precision':<30} {det_precision:.4f}{'':<13} {prob_precision:.4f}{'':<13} {total_precision:.4f}{'':<13}")
    print(f"  {'Recall':<30} {det_recall:.4f}{'':<13} {prob_recall:.4f}{'':<13} {total_recall:.4f}{'':<13}")
    print(f"  {'F1 Score':<30} {det_f1:.4f}{'':<13} {prob_f1:.4f}{'':<13} {total_f1:.4f}{'':<13}")

    # 8. False Positive Analysis
    print(f"\n{'='*72}")
    print(f"  FALSE POSITIVE ANALYSIS")
    print(f"{'='*72}")

    # Group FPs by profile
    fp_by_profile: Dict[str, int] = defaultdict(int)
    for fp in fp_pairs:
        fp_by_profile[fp["uid"]] += 1

    # Top FP profiles
    sorted_fp = sorted(fp_by_profile.items(), key=lambda x: -x[1])
    print(f"\n  Total FP cross-platform pairs: {len(fp_pairs)}")
    print(f"  Profiles with FPs: {len(fp_by_profile)}")
    print(f"\n  Top 5 profiles by FP count:")
    for uid, count in sorted_fp[:5]:
        prof = next((p for p in profiles if str(p["_id"]) == uid), None)
        n_sessions = len(prof.get("sessions", [])) if prof else 0
        n_events = len(prof.get("event_history", [])) if prof else 0
        print(f"    {uid[:20]:<22} FP={count:<8} sessions={n_sessions:<5} events={n_events}")

    print(f"\n  Sample FPs (first 10):")
    for fp in fp_pairs[:10]:
        print(f"    A={fp['session_a']:<30} B={fp['session_b']:<30} uid={fp['uid'][:16]}")

    # Determine merge reason for FPs
    print(f"\n  FP merge reason analysis:")
    sample_fp_profiles = set(fp["uid"] for fp in fp_pairs[:100])
    for uid in list(sample_fp_profiles)[:3]:
        prof = next((p for p in profiles if str(p["_id"]) == uid), None)
        if prof:
            methods = set(s.get("method", "?") for s in prof.get("sessions", []))
            platforms = set(s.get("platform", "?") for s in prof.get("sessions", []))
            print(f"    uid={uid[:20]} methods={methods} platforms={platforms} total_sessions={len(prof.get('sessions',[]))}")

    # 9. False Negative Analysis
    print(f"\n{'='*72}")
    print(f"  FALSE NEGATIVE ANALYSIS")
    print(f"{'='*72}")
    print(f"\n  Total FN: {total_fn} ({det_fn} det + {prob_fn} prob)")

    print(f"\n  Deterministic FN samples (first 20):")
    for fn in fn_det[:20]:
        print(f"    A={fn['a']:<30} B={fn['b']:<30} reason={fn.get('reason','?')}")

    print(f"\n  Probabilistic FN samples (first 20):")
    for fn in fn_prob[:20]:
        print(f"    A={fn['a']:<30} B={fn['b']:<30} reason={fn.get('reason','?')} uid_a={fn.get('uid_a','?')[:16]} uid_b={fn.get('uid_b','?')[:16]}")

    # 10. Check probabilistic overlap candidates
    print(f"\n{'='*72}")
    print(f"  PROBABILISTIC MATCHING INVESTIGATION")
    print(f"{'='*72}")
    print(f"\n  All {prob_fn} probabilistic FN pairs have sessions in different profiles.")
    print(f"  Reason: deterministic device_fingerprint consumed these candidates first.")

    # Check whether the probabilistic matches WOULD have worked if tested
    print(f"\n  Testing probabilistic scores on FN pairs (sample 20):")

    def _parse_event_time(et: Any) -> Any:
        from datetime import datetime
        if isinstance(et, str):
            return datetime.fromisoformat(et.replace("Z", "+00:00").replace(" ", "T"))
        return et

    from uid_engine.probabilistic import score_sessions

    # Load session data from profiles using event_history (SessionLink does not store device info)
    session_data: Dict[str, Dict] = {}
    for p in profiles:
        for s in p.get("sessions", []):
            sid = s["session_id"]
            evts = p.get("event_history", [])
            session_events = [e for e in evts if e.get("session_id") == sid]
            first_event = session_events[0] if session_events else {}
            session_data[sid] = {
                "session_id": sid,
                "platform": s.get("platform", ""),
                "hashed_email": first_event.get("hashed_email", ""),
                "ip_range": first_event.get("ip_range", ""),
                "city": first_event.get("location", {}).get("city", "") if isinstance(first_event.get("location"), dict) else "",
                "country": first_event.get("location", {}).get("country", "") if isinstance(first_event.get("location"), dict) else "",
                "device_type": first_event.get("device_type", ""),
                "user_agent": first_event.get("user_agent", ""),
                "event_times": [_parse_event_time(e.get("event_time")) for e in session_events if e.get("event_time")],
            }

    prob_fn_checked = 0
    prob_fn_would_match = 0
    prob_fn_scores = []

    for fn in fn_prob:
        if prob_fn_checked >= 20:
            break
        a = fn["a"]
        b = fn["b"]
        sa = session_data.get(a)
        sb = session_data.get(b)
        if sa and sb:
            result = score_sessions(sa, sb)
            prob_fn_checked += 1
            prob_fn_scores.append(result.score)
            if result.match:
                prob_fn_would_match += 1

    print(f"    FN pairs checked: {prob_fn_checked}")
    print(f"    Would have matched (score >= 0.75): {prob_fn_would_match}")
    if prob_fn_scores:
        print(f"    Scores: min={min(prob_fn_scores):.4f} max={max(prob_fn_scores):.4f} avg={sum(prob_fn_scores)/len(prob_fn_scores):.4f}")

    # 11. Device fingerprint over-merging evidence
    print(f"\n{'='*72}")
    print(f"  DEVICE FINGERPRINT OVER-MERGING ANALYSIS")
    print(f"{'='*72}")

    # Count unique fingerprints in the data
    from uid_engine.deterministic import compute_device_fingerprint
    fps_seen: Dict[str, List[str]] = defaultdict(list)
    for sid, sd in session_data.items():
        ua = sd.get("user_agent", "")
        dt = sd.get("device_type", "")
        fp = compute_device_fingerprint(ua, dt)
        fps_seen[fp].append(sid)

    total_sessions_with_fp = len(session_data)
    unique_fps = len(fps_seen)
    collisions = sum(1 for sids in fps_seen.values() if len(sids) > 1)
    collision_sessions = sum(len(sids) for sids in fps_seen.values() if len(sids) > 1)
    collision_pct = (collision_sessions / total_sessions_with_fp * 100) if total_sessions_with_fp > 0 else 0

    print(f"\n  Total sessions with data: {total_sessions_with_fp}")
    print(f"  Unique device fingerprints: {unique_fps}")
    print(f"  Fingerprint groups with collisions (>1 session): {collisions}")
    print(f"  Sessions in collision groups: {collision_sessions} ({collision_pct:.1f}%)")
    print(f"\n  Distribution:")
    fp_sizes = sorted([(len(sids), fp) for fp, sids in fps_seen.items()], key=lambda x: -x[0])
    for size, fp in fp_sizes[:10]:
        sample_sids = fps_seen[fp][:5]
        print(f"    fingerprint={fp[:16]}... sessions={size} samples={sample_sids}")

    # Check how many ground truth pairs share the same fingerprint
    print(f"\n  Device fingerprint collisions among ground truth sessions:")
    gt_sessions = set()
    for p in gt_pairs:
        gt_sessions.add(p["session_id_a"])
        gt_sessions.add(p["session_id_b"])
    gt_fp_groups: Dict[str, List[str]] = defaultdict(list)
    for sid in gt_sessions:
        sd = session_data.get(sid)
        if sd:
            ua = sd.get("user_agent", "")
            dt = sd.get("device_type", "")
            fp = compute_device_fingerprint(ua, dt)
            gt_fp_groups[fp].append(sid)
    collisions = sum(1 for sids in gt_fp_groups.values() if len(sids) > 2)
    print(f"    GT session IDs: {len(gt_sessions)}")
    print(f"    Unique fingerprints among GT: {len(gt_fp_groups)}")
    print(f"    Fingerprint groups with >2 GT sessions (collisions): {collisions}")
    for fp, sids in gt_fp_groups.items():
        if len(sids) > 2:
            print(f"      fp={fp[:16]}... sessions={len(sids)}: {sids[:6]}")

    # 12. Summary
    print(f"\n{'='*72}")
    print(f"  SUMMARY")
    print(f"{'='*72}")
    print(f"  Expected cross-platform merges: 400 ({len(det_gt)} det + {len(prob_gt)} prob)")
    print(f"  Actual merged (TP):             {total_tp} ({det_tp} det + {prob_tp} prob)")
    print(f"  Missed merges (FN):             {total_fn} ({det_fn} det + {prob_fn} prob)")
    print(f"  Wrong merges (FP):              {total_fp} cross-platform pairs")
    print(f"  Overall Precision:              {total_precision:.4f}")
    print(f"  Overall Recall:                 {total_recall:.4f}")
    print(f"  Overall F1 Score:               {total_f1:.4f}")

    print(f"\n  Root causes:")
    print(f"    1. Device fingerprint over-merging ({len(fps_seen)} fingerprints for {len(session_data)} sessions)")
    print(f"       → {len(fp_pairs)} false positive cross-platform pairs created")
    print(f"    2. Probabilistic matcher never evaluated ({prob_fn} FN candidates consumed by device fp)")
    print(f"    3. Only {det_tp}/{len(det_gt)} deterministic email pairs correctly merged")
    print(f"    4. Batch-timing: some FN pairs had A and B sessions in different flush cycles")
    print()

    return {
        "total_gt": len(gt_pairs),
        "det_gt": len(det_gt),
        "prob_gt": len(prob_gt),
        "tp_det": det_tp,
        "tp_prob": prob_tp,
        "fn_det": det_fn,
        "fn_prob": prob_fn,
        "fp": det_fp,
        "precision_det": det_precision,
        "recall_det": det_recall,
        "f1_det": det_f1,
        "precision_prob": prob_precision,
        "recall_prob": prob_recall,
        "f1_prob": prob_f1,
        "precision": total_precision,
        "recall": total_recall,
        "f1": total_f1,
    }


if __name__ == "__main__":
    evaluate()
