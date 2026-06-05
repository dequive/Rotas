---
phase: 1
slug: security-hardening-deploy-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| PyJWT migration | 01 | 1 | SEC-05 | integration | `cd backend && python -m pytest tests/test_auth_api.py -v` | ✅ | ⬜ pending |
| alg=none rejection | 01 | 1 | SEC-05 | integration | `cd backend && python -m pytest tests/test_auth_api.py::test_alg_none_token_rejected -v` | ❌ W0 | ⬜ pending |
| JWT secret validation | 01 | 1 | SEC-01 | unit | `cd backend && python -m pytest tests/test_startup_validation.py -v` | ❌ W0 | ⬜ pending |
| Startup env guard | 01 | 1 | DEPLOY-01 | unit | `cd backend && python -m pytest tests/test_startup_validation.py -v` | ❌ W0 | ⬜ pending |
| CORS production guard | 01 | 1 | SEC-02 | integration | `cd backend && python -m pytest tests/test_cors.py -v` | ❌ W0 | ⬜ pending |
| Rate limiting | 01 | 2 | SEC-03 | integration | `cd backend && python -m pytest tests/test_rate_limiting.py -v` | ❌ W0 | ⬜ pending |
| Sync driver-only auth | 01 | 2 | AUTH-03 | integration | `cd backend && python -m pytest tests/test_sync_auth.py -v` | ❌ W0 | ⬜ pending |
| Cross-tenant isolation | 01 | 2 | SEC-01..05 | integration | `cd backend && python -m pytest tests/test_cross_tenant_isolation.py -v` | ❌ W0 | ⬜ pending |
| railway.toml | 01 | 3 | DEPLOY-02/04 | manual | Verify `railway.toml` present at repo root | ✅ after write | ⬜ pending |
| vercel.json | 01 | 3 | DEPLOY-03 | manual | Verify `apps/manager/vercel.json` present | ✅ after write | ⬜ pending |
| Node engines field | 01 | 3 | DEPLOY-03 | unit | `node -e "const p=require('./package.json'); if (!p.engines?.node) process.exit(1)"` | ✅ after write | ⬜ pending |
| Secure cookies (Next.js) | 01 | 2 | SEC-04 | manual | See Manual-Only Verifications table below | ✅ after edit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_startup_validation.py` — stubs for DEPLOY-01 / SEC-01 startup env guard tests
- [ ] `backend/tests/test_cors.py` — stubs for SEC-02 CORS production enforcement tests
- [ ] `backend/tests/test_rate_limiting.py` — stubs for SEC-03 rate limiting tests
- [ ] `backend/tests/test_sync_auth.py` — stubs for AUTH-03 driver-only sync endpoint tests
- [ ] `backend/tests/test_cross_tenant_isolation.py` — stubs for D-21 cross-tenant isolation tests
- [ ] Add `alg=none` rejection test case to existing `backend/tests/test_auth_api.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Railway deploy succeeds, Alembic runs pre-deploy | DEPLOY-02, DEPLOY-04 | Requires live Railway environment | Deploy to Railway, verify preDeployCommand output in Railway logs |
| Vercel deploy reachable, communicates with backend | DEPLOY-03 | Requires live Vercel environment | Visit Vercel URL, attempt login, verify API requests hit Railway backend |
| Manager dashboard login sets Secure cookie in production | SEC-04 | Requires HTTPS deployment; Next.js `cookies()` API does not expose `Set-Cookie` headers in test responses, so Secure flag can only be verified by inspecting browser DevTools on a production HTTPS deployment | Open browser devtools → Application → Cookies on the deployed Vercel URL, verify Secure flag is checked on `rotas_access_token` cookie |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
