"""Tests for the Identity Resolution Engine (uid_engine module).

Covers deterministic matcher, probabilistic scorer, and evaluation.
"""

from __future__ import annotations

from datetime import datetime


from uid_engine.deterministic import compute_device_fingerprint, match_sessions
from uid_engine.probabilistic import score_sessions, batch_score, set_threshold, get_threshold
from uid_engine.evaluate import Metrics, group_into_sessions

from common.schemas import IdentityMatchResult, MatchMethod


# ══════════════════════════════════════════════
# Deterministic Matcher
# ══════════════════════════════════════════════

class TestDeterministic:
    def test_email_match(self):
        a = {"session_id": "s1", "hashed_email": "abc123", "user_agent": "Mozilla", "device_type": "mobile"}
        b = {"session_id": "s2", "hashed_email": "abc123", "user_agent": "Chrome", "device_type": "desktop"}
        result = match_sessions(a, b)
        assert result.match is True
        assert result.method == MatchMethod.deterministic
        assert result.score == 1.0
        assert result.details["matched_on"] == "hashed_email"

    def test_device_fingerprint_match(self):
        a = {"session_id": "s1", "hashed_email": None, "user_agent": "Mozilla/5.0", "device_type": "mobile"}
        b = {"session_id": "s2", "hashed_email": None, "user_agent": "Mozilla/5.0", "device_type": "mobile"}
        result = match_sessions(a, b)
        assert result.match is True
        assert result.method == MatchMethod.deterministic
        assert result.score == 1.0
        assert result.details["matched_on"] == "device_fingerprint"

    def test_no_match(self):
        a = {"session_id": "s1", "hashed_email": None, "user_agent": "Mozilla", "device_type": "mobile"}
        b = {"session_id": "s2", "hashed_email": None, "user_agent": "Safari", "device_type": "tablet"}
        result = match_sessions(a, b)
        assert result.match is False
        assert result.method == MatchMethod.none
        assert result.score == 0.0

    def test_email_takes_priority_over_device(self):
        a = {"session_id": "s1", "hashed_email": "email_a", "user_agent": "Mozilla", "device_type": "mobile"}
        b = {"session_id": "s2", "hashed_email": "email_a", "user_agent": "Safari", "device_type": "tablet"}
        result = match_sessions(a, b)
        assert result.match is True
        assert result.details["matched_on"] == "hashed_email"

    def test_device_fingerprint_consistency(self):
        fp1 = compute_device_fingerprint("Mozilla/5.0", "mobile")
        fp2 = compute_device_fingerprint("Mozilla/5.0", "mobile")
        fp3 = compute_device_fingerprint("Mozilla/5.0", "desktop")
        assert fp1 == fp2
        assert fp1 != fp3

    def test_none_email_not_matched(self):
        a = {"session_id": "s1", "hashed_email": None, "user_agent": "A", "device_type": "mobile"}
        b = {"session_id": "s2", "hashed_email": "", "user_agent": "A", "device_type": "mobile"}
        result = match_sessions(a, b)
        # Both have no email, but device fingerprint matches
        assert result.match is True
        assert result.details["matched_on"] == "device_fingerprint"


# ══════════════════════════════════════════════
# Probabilistic Scorer
# ══════════════════════════════════════════════

class TestProbabilistic:
    def test_high_similarity_returns_match(self):
        now = datetime.utcnow()
        a = {
            "session_id": "s1", "ip_range": "10.0.1.0/24",
            "city": "New York", "device_type": "mobile",
            "event_times": [now, now.replace(hour=10), now.replace(hour=11)],
        }
        b = {
            "session_id": "s2", "ip_range": "10.0.1.0/24",
            "city": "New York", "device_type": "mobile",
            "event_times": [now.replace(hour=10), now.replace(hour=11), now.replace(hour=14)],
        }
        result = score_sessions(a, b)
        assert result.match is True
        assert result.score >= 0.75
        assert result.method == MatchMethod.probabilistic
        assert result.global_uid is not None

    def test_low_similarity_returns_no_match(self):
        now = datetime.utcnow()
        a = {
            "session_id": "s1", "ip_range": "10.0.1.0/24",
            "city": "New York", "device_type": "mobile",
            "event_times": [now],
        }
        b = {
            "session_id": "s2", "ip_range": "192.168.5.0/24",
            "city": "Berlin", "device_type": "desktop",
            "event_times": [now.replace(hour=3)],
        }
        result = score_sessions(a, b)
        assert result.match is False
        assert result.score < 0.75
        assert result.method == MatchMethod.none

    def test_ip_range_overlap_scoring(self):
        from uid_engine.probabilistic import score_sessions as ss
        now = datetime.utcnow()
        a = {"session_id": "s1", "ip_range": "10.0.1.0/24", "city": "NY", "device_type": "mobile", "event_times": [now]}
        b = {"session_id": "s2", "ip_range": "10.0.1.0/24", "city": "Berlin", "device_type": "desktop", "event_times": [now.replace(hour=5)]}
        result = ss(a, b)
        # Only ip_range matches → 0.35 weight → score = 0.35 < 0.75
        assert result.score == 0.35 or abs(result.score - 0.35) < 0.01

    def test_batch_scoring(self):
        now = datetime.utcnow()
        pairs = [
            (
                {"session_id": "s1", "ip_range": "10.0.0.0/24", "city": "NY", "device_type": "mobile", "event_times": [now]},
                {"session_id": "s2", "ip_range": "10.0.0.0/24", "city": "NY", "device_type": "mobile", "event_times": [now]},
            ),
            (
                {"session_id": "s3", "ip_range": "10.0.5.0/24", "city": "Berlin", "device_type": "desktop", "event_times": [now]},
                {"session_id": "s4", "ip_range": "10.0.5.0/24", "city": "Berlin", "device_type": "desktop", "event_times": [now]},
            ),
        ]
        results = batch_score(pairs)
        assert len(results) == 2
        assert all(isinstance(r, IdentityMatchResult) for r in results)

    def test_threshold_configurable(self):
        original = get_threshold()
        set_threshold(0.5)
        assert get_threshold() == 0.5
        set_threshold(original)
        assert get_threshold() == original

    def test_location_case_insensitive(self):
        now = datetime.utcnow()
        a = {"session_id": "s1", "ip_range": "10.0.0.0/24", "city": "NEW YORK", "device_type": "mobile", "event_times": [now]}
        b = {"session_id": "s2", "ip_range": "10.0.0.0/24", "city": "new york", "device_type": "mobile", "event_times": [now]}
        result = score_sessions(a, b)
        assert result.match is True

    def test_time_window_empty_events(self):
        a = {"session_id": "s1", "ip_range": "10.0.0.0/24", "city": "NY", "device_type": "mobile", "event_times": []}
        b = {"session_id": "s2", "ip_range": "10.0.0.0/24", "city": "NY", "device_type": "mobile", "event_times": []}
        result = score_sessions(a, b)
        # ip_range + city + device = 0.35 + 0.25 + 0.20 = 0.80, time_window = 0
        assert result.score == 0.80


# ══════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════

class TestGroupIntoSessions:
    def test_groups_events_by_session_id(self):
        events = [
            {"session_id": "s1", "event_type": "view", "product_id": "p1", "event_time": "2024-03-01T10:00:00Z", "device_type": "mobile", "ip_range": "10.0.0.0/24", "city": "NY", "country": "US", "user_agent": "Mozilla", "platform": "A"},
            {"session_id": "s1", "event_type": "cart", "product_id": "p2", "event_time": "2024-03-01T11:00:00Z", "device_type": "mobile", "ip_range": "10.0.0.0/24", "city": "NY", "country": "US", "user_agent": "Mozilla", "platform": "A"},
            {"session_id": "s2", "event_type": "view", "product_id": "p3", "event_time": "2024-03-01T12:00:00Z", "device_type": "desktop", "ip_range": "192.168.1.0/24", "city": "Berlin", "country": "DE", "user_agent": "Chrome", "platform": "B"},
        ]
        sessions = group_into_sessions(events)
        assert len(sessions) == 2
        assert "s1" in sessions
        assert "s2" in sessions
        assert sessions["s1"]["device_type"] == "mobile"
        assert len(sessions["s1"]["event_types"]) == 2
        assert len(sessions["s2"]["event_times"]) == 1

    def test_handles_missing_fields(self):
        events = [
            {"session_id": "s1", "event_type": "view", "product_id": "p1", "event_time": "invalid", "device_type": "", "ip_range": "", "city": "", "country": "", "user_agent": "", "platform": "A"},
        ]
        sessions = group_into_sessions(events)
        assert len(sessions["s1"]["event_times"]) == 0  # invalid datetime skipped


# ══════════════════════════════════════════════
# Metrics
# ══════════════════════════════════════════════

class TestMetrics:
    def test_perfect_scores(self):
        m = Metrics("perfect")
        m.add(predicted_match=True, actual_match=True)
        m.add(predicted_match=True, actual_match=True)
        m.add(predicted_match=False, actual_match=False)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1 == 1.0

    def test_no_true_positives(self):
        m = Metrics("none")
        m.add(predicted_match=False, actual_match=True)
        m.add(predicted_match=False, actual_match=False)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0

    def test_partial_scores(self):
        m = Metrics("partial")
        m.add(predicted_match=True, actual_match=True)
        m.add(predicted_match=True, actual_match=False)
        m.add(predicted_match=False, actual_match=True)
        assert m.precision == 0.5
        assert m.recall == 0.5
        assert m.f1 == 0.5

    def test_repr_contains_metrics(self):
        m = Metrics("test")
        m.add(predicted_match=True, actual_match=True)
        r = repr(m)
        assert "Precision" in r
        assert "Recall" in r
        assert "F1" in r

# ══════════════════════════════════════════════
# Event Persistence and Significance
# ══════════════════════════════════════════════

class TestEventPersistence:
    def test_significant_event_validation(self):
        from uid_engine.merger import ProfileMerger
        profile = {
            "event_history": [
                {"session_id": "s_A", "event_type": "view"},
                {"session_id": "s_A", "event_type": "view"},
                {"session_id": "s_A", "event_type": "view"},
                {"session_id": "s_A", "event_type": "cart"}
            ]
        }
        assert len(profile["event_history"]) == 4
        assert ProfileMerger._is_significant_event(profile) is True
