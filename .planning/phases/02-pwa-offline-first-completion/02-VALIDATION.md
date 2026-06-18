---
phase: 2
slug: pwa-offline-first-completion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ with pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && python -m pytest tests/test_sync_auth.py tests/test_sync_idempotency.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest -x -q` |
| **Estimated runtime** | ~30 seconds (backend only; frontend is manual) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_sync_auth.py tests/test_sync_idempotency.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest -x -q`
- **Before `/gsd:verify-work`:** Full backend suite green + manual device test on real Android
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-W0-01 | Wave 0 | 0 | AUTH-04 | integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ W0 | ⬜ pending |
| 02-W0-02 | Wave 0 | 0 | D-08 | integration | `cd backend && python -m pytest tests/test_driver_revocation.py -x -q` | ❌ W0 | ⬜ pending |
| 02-W0-03 | Wave 0 | 0 | AUTH-01/02 | integration | `cd backend && python -m pytest tests/test_token_refresh.py -x -q` | ❌ W0 | ⬜ pending |
| 02-AUTH04 | AUTH-04 plan | 1 | AUTH-04 | integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ W0 | ⬜ pending |
| 02-AUTH01 | AUTH-01 plan | 1 | AUTH-01 | integration | `cd backend && python -m pytest tests/test_token_refresh.py tests/test_auth_api.py -x -q` | partial ✅ | ⬜ pending |
| 02-AUTH02 | AUTH-02 plan | 1 | AUTH-02 | integration | `cd backend && python -m pytest tests/test_sync_auth.py tests/test_token_refresh.py -x -q` | partial ✅ | ⬜ pending |
| 02-D08 | Revocation plan | 1 | D-08 | integration | `cd backend && python -m pytest tests/test_driver_revocation.py -x -q` | ❌ W0 | ⬜ pending |
| 02-PWA01 | SW plan | 2 | PWA-01 | manual | Lighthouse audit + Android device test | No — manual only | ⬜ pending |
| 02-PWA02 | Manifest plan | 2 | PWA-02 | manual | Chrome "Add to Home Screen" on Android Chrome | No — manual only | ⬜ pending |
| 02-PWA03 | Cache plan | 2 | PWA-03 | manual | DevTools Network panel verification | No — manual only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_sync_update.py` — stubs for AUTH-04 (update ops for trip, fuel_log, trip_stop, delivery_proof)
- [ ] `backend/tests/test_driver_revocation.py` — stubs for D-08 (driver_access_revoked error code distinction)
- [ ] `backend/tests/test_token_refresh.py` — stubs for AUTH-01 (manager refresh) and AUTH-02 (driver refresh)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chrome "Add to Home Screen" prompt appears | PWA-02 | Requires real browser installability check | Open app in Android Chrome → three-dot menu → "Add to Home Screen" must appear |
| App launches in standalone mode (no browser chrome) | PWA-02 | Requires installed PWA on device | Launch installed PWA from home screen → no browser address bar should be visible |
| App works fully in airplane mode (all views load) | PWA-03 | Requires offline browser context | Enable airplane mode → open app → navigate to trip, fuel, stop views → no error messages |
| Offline-created records sync on reconnect within 60s | PWA-01 | Requires real network transition | Create records offline → disable airplane mode → watch manager dashboard for records within 60s |
| Background sync triggers without app open | PWA-01 | Requires BackgroundSync API support | Create records → close app → reconnect network → manager dashboard receives records |
| SW `Cache-Control: no-store` in DevTools | PWA-01 | Requires browser dev tools | Open DevTools → Network tab → filter for `sw.js` → verify `Cache-Control: no-store` header |
| Lighthouse PWA installability score | PWA-02 | Requires Lighthouse CLI | `npx lighthouse <url> --only-categories=pwa --output=json` → installability must PASS |
| Driver token refresh works after 4h offline | AUTH-02 | Requires time-elapsed token state | Configure access token with short TTL in test env → go offline → wait → reconnect → verify no 401 in sync |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
