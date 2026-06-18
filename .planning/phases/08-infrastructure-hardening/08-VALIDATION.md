---
phase: 8
slug: infrastructure-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-06
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_tenant_user_alert_api.py tests/test_vehicle_driver_api.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Req | Test Type | Automated Command | File Exists | Status |
|---------|-----|-----------|-------------------|-------------|--------|
| 08-W0-01 | INFRA-01 | unit | `pytest tests/test_sentry_integration.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-W0-02 | INFRA-01 | unit | `pytest tests/test_sentry_integration.py::test_scrub_pii -x` | ❌ Wave 0 | ⬜ pending |
| 08-W0-03 | INFRA-02 | unit | `pytest tests/test_storage.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-W0-04 | INFRA-02 | unit | `pytest tests/test_migrate_files.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-W0-05 | INFRA-03 | integration | `pytest tests/test_tenant_limits_api.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-01 | INFRA-01 | unit | `pytest tests/test_sentry_integration.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-02 | INFRA-02 | unit | `pytest tests/test_storage.py tests/test_migrate_files.py -x` | ❌ Wave 0 | ⬜ pending |
| 08-03 | INFRA-03 | integration | `pytest tests/test_vehicle_driver_api.py tests/test_tenant_user_alert_api.py tests/test_tenant_limits_api.py -x` | Partial | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sentry_integration.py` — stubs for INFRA-01 (PII scrubber, init guard, SQL breadcrumbs)
- [ ] `tests/test_storage.py` — stubs for INFRA-02 (LOCAL/R2 provider with mocked boto3)
- [ ] `tests/test_migrate_files.py` — stubs for INFRA-02 migration script (skip behavior, exit codes, gate query)
- [ ] `tests/test_tenant_limits_api.py` — stubs for INFRA-03 (GET /tenant/limits, Redis cache hit, null=unlimited)

Existing tests needing assertion updates (not new files):
- `tests/test_vehicle_driver_api.py` — add `upgrade_url` assertion to limit tests
- `tests/test_tenant_user_alert_api.py` — add `upgrade_url` assertion + null limit test

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sentry event appears in dashboard within 60s | INFRA-01 | Requires live Sentry DSN and network | Trigger a 500 error on staging; verify event in Sentry UI |
| R2 file survives Railway deploy (disk wipe) | INFRA-02 | Requires Railway deploy + R2 account | Upload file, redeploy, verify presigned URL still resolves |
| LimitWarningBanner at 80% | INFRA-03 | Frontend visual check | Create vehicles up to 80% of limit; verify banner renders in manager |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
