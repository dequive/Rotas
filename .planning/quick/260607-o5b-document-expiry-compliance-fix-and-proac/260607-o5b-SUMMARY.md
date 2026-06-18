# Quick Task 260607-o5b — Summary

**Task:** Document expiry compliance fix and proactive alerts
**Date:** 2026-06-07
**Status:** Complete

---

## What Was Built

### Task 1 — Fix `driver_compliance_violations()` (commit e48413b)

**File:** `backend/app/modules/availability/service.py`

The old implementation only checked `license_valid_until` (flat field), silently skipping passport and BI expiry. The function now uses the same `candidates` dict pattern as `driver_compliance_warnings()`, covering all three documents:

```python
candidates = {
    "driving_license": driver.license_valid_until,
    "passport":        driver.passport_valid_until,
    "bi":              driver.bi_valid_until,
}
```

Default required set when policy has no `driver_required_documents`: `{"driving_license", "passport", "bi"}`.

**Tests added:** `backend/tests/test_availability_service.py` — 8 tests, all pass. Pure function tests using `MagicMock(spec=Driver)`, no DB required.

### Task 2 — ARQ daily job `scan_expiring_documents` (commit 8d26ca6)

**Files:**
- `backend/app/jobs/tasks/document_expiry.py` (new)
- `backend/app/jobs/worker.py` (updated)

New ARQ task runs at 03:00 UTC daily (offset from maintenance at 02:00 UTC to avoid DB contention). For each active tenant, calls `get_document_expiry_alerts(db, tenant_id, horizon_days=30)` and creates Alert records.

**Idempotency:** `request_reference = f"doc_expiry:{tenant_id}:{entity_id}:{doc_type}:{iso_week}"` — week-scoped so re-runs within the same calendar week skip existing alerts (create_alert returns 409 on duplicate reference, treated as idempotent skip).

**Priority mapping:** `critical → critical`, `urgent → high`, `warning → medium`.

### Task 3 — `DocumentExpiryBanner` + layout integration (commit f4c04b5)

**Files:**
- `apps/manager/app/components/DocumentExpiryBanner.tsx` (new)
- `apps/manager/app/layout.tsx` (updated)

Server component (no `"use client"`) receiving `alerts: ExpiryAlert[]` props. Renders:
- **Amber banner** (`bg-amber-400 text-amber-950`) when any document expires in 8–30 days
- **Red banner** (`bg-red-600 text-white`) when any document expires in ≤7 days (critical)
- **No banner** when alerts list is empty or fetch fails

Fetched in parallel with `getTenantLimits()` in `RootLayout` using `Promise.all`. Returns `[]` (not null) on unauthenticated routes — safe for `/login`. Cache: `revalidate: 60`.

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Week-scoped `request_reference` | Prevents duplicate alerts across daily re-runs; allows weekly renewal reminders |
| `revalidate: 60` for expiry fetch | Documents renew slowly; 60s is sufficient vs. 30s for limits (which Redis caches) |
| `Promise.all([getTenantLimits(), getDocumentExpiry()])` | Parallel fetches — neither blocks the other; banner appears or doesn't independently |
| 03:00 UTC cron (not 02:00) | Maintenance job at 02:00 UTC is heavy; staggering by 1h avoids DB contention |
| Returns `[]` not `null` on failure | Simpler null-check logic in layout; no conditional spread needed |

---

## Verification

- `backend/tests/test_availability_service.py` → 8/8 pass
- `npx tsc --noEmit -p apps/manager/tsconfig.json` → clean
- Worker: `WorkerSettings.functions` contains `scan_expiring_documents`; `cron_jobs` has `cron:scan_expiring_documents` at `hour={3}`

---

## Human Checkpoint Required

To verify the banner visually:

1. Start dev server: `cd apps/manager && npm run dev`
2. Set a driver's `passport_valid_until` to 5 days from today:
   ```sql
   UPDATE drivers SET passport_valid_until = CURRENT_DATE + 5 WHERE tenant_id = '<your_tenant>' LIMIT 1;
   ```
3. Hard-reload dashboard — **red banner** should appear
4. Set to 20 days — **amber banner** should appear instead
5. Set to NULL or > 30 days — **no banner**
6. Log out → `/login` — no banner (unauthenticated path returns `[]`)
