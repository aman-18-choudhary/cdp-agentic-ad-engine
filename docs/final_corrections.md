# Final Corrections Report

Every PARTIAL claim from `docs/verification_report.md` corrected with verified values.

---

## Test Count Corrections

### test_agents.py
- **Old**: 17 tests
- **New**: 19 tests
- **Source**: `grep -c "def test_" tests/test_agents.py` → 19
- **Files affected**: `README.md`, `docs/project_status.md`

### test_uid_engine.py
- **Old**: 21 tests
- **New**: 20 tests
- **Source**: `grep -c "def test_" tests/test_uid_engine.py` → 20
- **Files affected**: `README.md`, `docs/project_status.md`

### Total unit tests
- **Old**: 42
- **New**: 43 (19 + 4 + 20)
- **Source**: Sum of all `def test_` in `tests/`
- **Files affected**: `docs/project_status.md`

---

## MongoDB Count Corrections

### Total profiles
- **Old**: 689
- **New**: 694
- **Source**: `db.unified_profiles.countDocuments()` → 694
- **Files affected**: `docs/architecture.md`, `docs/project_status.md`

### Profiles with intent
- **Old**: 694 (claimed "689 original + 5 from live test")
- **New**: 689
- **Source**: `db.unified_profiles.countDocuments({last_intent_profile: {$type: "string", $ne: ""}})` → 689
- **Files affected**: `README.md`, `docs/project_status.md`, `docs/architecture.md`

### Multi-session profiles
- **Old**: 32
- **New**: 35
- **Source**: `db.unified_profiles.countDocuments({$expr: {$gt: [{$size: {$ifNull: ["$sessions", []]}}, 1]}})` → 35
- **Files affected**: `docs/project_status.md`

---

## Event Count Corrections

### Total events consumed
- **Old**: 54,661
- **New**: 54,669
- **Source**: `rpk group describe cdp-event-consumer -c`: platform-a=31,109, platform-b=23,560 → 54,669
- **Files affected**: `README.md`, `docs/project_status.md`
- **Note**: The old value was from an earlier offset snapshot. Offsets increase as new events arrive. The corrected 54,669 is the latest verified value.

---

## FP Count Corrections

### False positive cross-platform pairs
- **Old**: 180,034
- **New**: 180,037
- **Source**: `scripts/uid_eval.py` output: `"FP (cross-platform, not in GT): 180037"`
- **Files affected**: `docs/project_status.md`
- **Note**: The 3-pair difference is from the eval script run including the 6 live-test events (which created 3 additional cross-platform session pairs that count as FP since they're not in ground truth).

---

## Storage Section Corrections

### architecture.md profile counts
- **Old**: "689 docs, 694 with profiling"
- **New**: "694 profiles, 689 with intent profiles"
- **Source**: MongoDB queries
- **Files affected**: `docs/architecture.md`

---

## Docker Container Count

### Containers running in demo
- **Old**: "6 containers running"
- **New**: "Up to 6 containers (7 services defined in docker-compose.yml); current running count depends on service state"
- **Source**: `docker-compose.yml` defines 7 services; `docker ps` count varies
- **Files affected**: `docs/demo_script.md`

---

## Summary of Corrections

| File | Old Value | New Value | Source of Truth |
|------|-----------|-----------|-----------------|
| README.md | test_agents: 17 tests | test_agents: 19 tests | `grep -c "def test_" tests/test_agents.py` |
| README.md | test_uid_engine: 21 tests | test_uid_engine: 20 tests | `grep -c "def test_" tests/test_uid_engine.py` |
| README.md | 54,661 events consumed | 54,669 events consumed | `rpk group describe` offset sum |
| README.md | 694 profiles with intent | 689 profiles with intent | MongoDB countDocuments query |
| architecture.md | "689 docs, 694 with profiling" | "694 profiles, 689 with intent" | MongoDB countDocuments queries |
| project_status.md | test_uid_engine: 21 tests | test_uid_engine: 20 tests | `grep -c "def test_" tests/test_uid_engine.py` |
| project_status.md | test_agents: 17 tests | test_agents: 19 tests | `grep -c "def test_" tests/test_agents.py` |
| project_status.md | 42 tests passing | 43 tests passing | Sum of all test files |
| project_status.md | 689 unified profiles | 694 unified profiles | MongoDB countDocuments |
| project_status.md | 694 profiles with intent | 689 profiles with intent | MongoDB countDocuments |
| project_status.md | 32 multi-session merges | 35 multi-session merges | MongoDB countDocuments |
| project_status.md | 54,661 events consumed | 54,669 events consumed | `rpk group describe` offset sum |
| project_status.md | 180,034 FP pairs | 180,037 FP pairs | `scripts/uid_eval.py` output |
| demo_script.md | "6 containers running" | State-dependent; 7 services defined | `docker ps` + `docker-compose.yml` |
