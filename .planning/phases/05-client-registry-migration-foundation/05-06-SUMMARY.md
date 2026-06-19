---
plan: 05-06
phase: 05-client-registry-migration-foundation
status: complete
completed: 2026-06-19
requirements:
  - CLI-03
---

## What was built

Implemented `test_backfill_zero_null_client_ids` in `backend/tests/test_clients_api.py` — the CLI-03 automated gate that was permanently skipped.

The test:
1. Seeds 3 contracts with distinct NUITs (`400000001`–`400000003`) and `client_id = NULL`
2. Runs Step 1+2 INSERT (clients from contracts, DISTINCT ON normalized name) from migration `f6a7b8c9d0e1`
3. Runs Step 3 UPDATE (`contracts.client_id` by name match) from migration `f6a7b8c9d0e1`
4. Asserts `count(*) WHERE client_id IS NULL AND client_name IS NOT NULL AND client_name != '' = 0`

**Why distinct NUITs are required:** Without them, all 3 contracts map to the placeholder nuit `'000000000'` and `ON CONFLICT (tenant_id, nuit) DO NOTHING` inserts only 1 client — leaving rows 2 and 3 unmatched in Step 3.

## Key files

- `backend/tests/test_clients_api.py` — skip removed, full test body at lines 148–219

## Test results

```
tests/test_clients_api.py::test_create_client PASSED
tests/test_clients_api.py::test_create_client_duplicate_nuit PASSED
tests/test_clients_api.py::test_list_clients_tenant_scoped PASSED
tests/test_clients_api.py::test_patch_client_deactivate PASSED
tests/test_clients_api.py::test_client_cross_tenant_isolation PASSED
tests/test_clients_api.py::test_credit_limit_warning_thresholds PASSED
tests/test_clients_api.py::test_backfill_zero_null_client_ids PASSED
7 passed
```

## Deviations

None — plan executed as specified. Added `from sqlalchemy import text` import and included all NOT NULL DB columns (without server-side defaults) in the raw SQL seed INSERT.

## Self-Check: PASSED
