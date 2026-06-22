---
plan: 26-03
phase: 26
status: DONE
completed: 2026-06-22
---
# Plan 26-03 — create_client: find-or-create against third_parties

## What was done

Rewrote `create_client` in `backend/app/modules/clients/service.py` to perform a 4-step
find-or-create flow instead of a bare INSERT into `clients`:

1. **Step 1 — find-or-create ThirdParty** by `(tenant_id, nuit)`. On race condition
   (concurrent INSERT wins), catches IntegrityError, rolls back, and re-selects.
2. **Step 2 — ensure ThirdPartyRole 'client' exists** for the resolved `third_party_id`.
3. **Step 3 — ensure ClientProfile exists** for the resolved `third_party_id`,
   carrying `payment_terms_days` and `credit_limit` from the client payload.
4. **Step 4 — insert Client record** with `third_party_id` FK set. The UNIQUE constraint
   on `(tenant_id, nuit)` in `clients` still guards against duplicate client creation (→ 409).

Also fixed `backend/app/modules/gps/router.py`: bad import `FLEET_READ`/`FLEET_WRITE` from
`app.core.permissions` (deprecated shim) → moved to `app.core.rbac`. Same fix for
`require_permission` which was never in `app.core.auth`.

## Tests

3 new tests added to `backend/tests/test_clients_api.py` (GT-05 block):

- **GT-05a** `test_create_client_duplicate_nuit_no_duplicate_third_party`: two POSTs same
  NUIT → second 409; only 1 `third_parties` row exists.
- **GT-05b** `test_create_client_links_to_preexisting_third_party`: pre-existing supplier
  `third_party` row reused — client links to it, no duplicate created.
- **GT-05c** `test_create_client_cross_tenant_same_nuit_separate_third_parties`: same NUIT
  in two tenants → 2 separate `third_parties` rows (cross-tenant isolation preserved).

All 13 tests in `test_clients_api.py` GREEN.

## Files modified

- `backend/app/modules/clients/service.py` — `create_client` rewritten
- `backend/app/modules/gps/router.py` — import fix (permissions → rbac)
- `backend/tests/test_clients_api.py` — 3 GT-05 tests appended (done in prior session)
