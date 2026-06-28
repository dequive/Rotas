---
phase: 19
slug: route-optimization
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-27
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x/9.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_route_optimization.py -x -q` |
| **Full suite command** | `backend\.venv\Scripts\python.exe -m pytest -x -q` |
| **Estimated runtime** | ~50 seconds |

---

## Sampling Rate

- **After every task commit:** Run `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_route_optimization.py -x -q`
- **After every plan wave:** Run the full suite `backend\.venv\Scripts\python.exe -m pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 50 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | OPTIM-01 | migration | `backend\.venv\Scripts\python.exe -m alembic upgrade head` | ✅ | ⬜ pending |
| 19-01-02 | 01 | 1 | OPTIM-01 | sql | `psql -c "SELECT route_geometry, route_polyline FROM trips LIMIT 1"` | ✅ | ⬜ pending |
| 19-02-01 | 02 | 2 | OPTIM-01 | unit | `pytest backend/tests/test_route_optimization.py::test_optimize_waypoints_greedy` | ❌ W0 | ⬜ pending |
| 19-02-02 | 02 | 2 | OPTIM-02 | integration | `pytest backend/tests/test_route_optimization.py::test_osrm_integration_success` | ❌ W0 | ⬜ pending |
| 19-02-03 | 02 | 2 | OPTIM-02 | integration | `pytest backend/tests/test_route_optimization.py::test_osrm_fallback_haversine` | ❌ W0 | ⬜ pending |
| 19-03-01 | 03 | 3 | OPTIM-03 | unit | `pytest backend/tests/test_route_optimization.py::test_perpendicular_distance_calculation` | ❌ W0 | ⬜ pending |
| 19-03-02 | 03 | 3 | OPTIM-03 | integration | `pytest backend/tests/test_route_optimization.py::test_gps_ingestion_creates_deviation_alert` | ❌ W0 | ⬜ pending |
| 19-03-03 | 03 | 3 | OPTIM-03 | integration | `pytest backend/tests/test_route_optimization.py::test_gps_ingestion_no_deviation_no_alert` | ❌ W0 | ⬜ pending |
| 19-04-01 | 04 | 4 | OPTIM-01 | integration | `pytest backend/tests/test_route_optimization.py::test_trip_optimization_endpoint` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_route_optimization.py` — Stub test file containing all tests matching the verification map above, marked with `@pytest.mark.asyncio`.
- [ ] Conftest fixtures for route optimization: mock OSRM response payload, trip with multiple stops, and GPS coordinate sequences.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual route path display on Control Tower map | OPTIM-02 | Frontend GIS mapping required | Open manager dashboard → /viagens → click trip detail → verify optimized route geometry is rendered as a blue polyline on the map. |
| Route deviation alert displayed on dashboard | OPTIM-03 | Toast/Notification UI | Ingest deviating GPS location webhook → verify amber banner "Desvio de Rota detectado para a Viagem X" appears in Control Tower. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 50s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
