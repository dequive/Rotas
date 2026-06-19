# Phase 2 — Field Test Checklist

**Device:** [to be filled]
**Android version:** [to be filled]
**Chrome version:** [to be filled]
**Date:** [to be filled]
**Tester:** [to be filled]

## Automated Pre-Flight (Agent Executed)

- [x] `cd backend && python -m pytest -x -q` — ALL PASS (152 passed)
- [x] `cd backend && python -m pytest tests/test_sync_update.py tests/test_driver_revocation.py tests/test_token_refresh.py -v` — ALL PASS
- [x] `cd apps/driver && npx vite build` — exits 0, dist/sw.js exists
- [x] `cd apps/manager && npx tsc --noEmit` — exits 0

## Device Tests (Human fills during device testing)

### PWA-02: Installability

- [ ] Open app in Android Chrome on target device
- [ ] Three-dot menu shows "Add to Home Screen" or install banner appears
- [ ] App installs to home screen without error
- [ ] Launching from home screen: no browser address bar visible (standalone mode)
- [ ] App name on home screen shows "Motorista" (short_name)

### PWA-01 / PWA-03: Offline Operation

- [ ] Enable airplane mode on device
- [ ] Navigate to dashboard view — loads without error
- [ ] Navigate to fuel view — loads without error
- [ ] Navigate to trip stop view — loads without error
- [ ] Create a new trip entry in airplane mode — no error message
- [ ] Record a fuel log in airplane mode — no error message
- [ ] SyncStatusBanner shows orange "Sem ligação — a gravar localmente" during airplane mode
- [ ] Counter "X registos pendentes" increments as records are added

### PWA-01: Background Sync on Reconnect

- [ ] Disable airplane mode
- [ ] SyncStatusBanner transitions to green "A sincronizar..."
- [ ] Within 60 seconds: offline records appear in manager dashboard
- [ ] SyncStatusBanner returns to idle (hidden) after sync completes
- [ ] Check manager dashboard: all offline records present and correct

### PWA-01: SW Cache-Control Header

- [ ] Open Chrome DevTools (desktop via remote debugging) → Application → Service Workers
- [ ] Confirm sw.js is registered and active
- [ ] Open Network tab → filter for sw.js → confirm Cache-Control: no-store header

### AUTH-01: Manager Token Refresh

- [ ] Login to manager dashboard
- [ ] Wait 15 minutes (or temporarily reduce token TTL in dev env)
- [ ] Navigate to any manager page — page loads normally (no redirect to /login)
- [ ] Verify no 401 errors in browser Network tab after 15 minutes

### AUTH-02: Driver Token Refresh After Extended Offline

- [ ] With driver app open, go offline for > 15 minutes (or test with short TTL token)
- [ ] Come back online — sync proceeds without 401 error in logs
- [ ] SyncStatusBanner does NOT show "Sessão expirada" on reconnect

## Results

**Overall result:** [ ] PASS  [ ] FAIL — issues listed below

**Issues found:**
[list any issues]

**Sign-off:** [name] on [date]
