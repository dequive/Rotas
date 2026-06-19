---
phase: 05
plan: 04
subsystem: contracts + clients
tags: [cli-04, contracts, combobox, client-registry, frontend, backend]
requirements: [CLI-04]

dependency_graph:
  requires: [05-01-PLAN.md]
  provides: [client_id on contracts, ClientCombobox, contract form client selection]
  affects: [contracts API, ContractFormModal, billing downstream]

tech_stack:
  added: []
  patterns:
    - Radix Popover + native search input for combobox (no cmdk dependency)
    - Next.js API route proxy for client component auth (httpOnly cookie forwarding)
    - Backend client_id resolution in service layer with cross-tenant guard

key_files:
  created:
    - apps/manager/app/components/ClientCombobox.tsx
    - backend/tests/test_contracts_api.py
  modified:
    - backend/app/modules/contracts/schemas.py
    - backend/app/modules/contracts/service.py
    - backend/app/modules/contracts/router.py
    - apps/manager/app/components/ContractFormModal.tsx
    - apps/manager/app/lib/contracts-api.ts
    - apps/manager/app/api/clients/route.ts

decisions:
  - "Radix Popover + native <input> + <ul> for combobox instead of cmdk — cmdk not installed in manager app; native implementation satisfies all UI-SPEC behavior requirements"
  - "Fetch /api/clients (Next.js proxy) not backend directly — httpOnly cookies cannot be read by client components; proxy route reads cookies server-side and forwards Authorization/X-Tenant-Id"
  - "serialize_contract includes client_id — required for edit mode pre-population and Contract type alignment"

metrics:
  duration_minutes: 12
  completed_date: "2026-06-19"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 8
---

# Phase 5 Plan 04: Contract form — client_id combobox + backend schema update Summary

Contract form now has a search-as-you-type ClientCombobox backed by GET /api/v1/clients, and the backend resolves client_name from Client.trading_name when client_id is supplied.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Backend: ContractCreate client_id support + test suite (5 tests) | a2d8476 |
| 2 | ClientCombobox component + GET /api/clients proxy route | d0e0b15 |
| 3 | ContractFormModal: ClientCombobox replaces free-text client_name input | c15c5cd |

## What Was Built

### Backend Changes

**`contracts/schemas.py`**
- `ContractCreate.client_name`: changed from `str` (required) to `str | None` (optional)
- `ContractCreate.client_id`: added `UUID | None = None`
- `ContractCreate.client_nuit`: moved from missing to explicit `str | None = None`
- `ContractPatch.client_id`: added `UUID | None = None`

**`contracts/service.py`**
- `create_contract`: validates that at least one of `client_id` or `client_name` is provided (ApiError 422 if neither)
- `create_contract`: looks up `Client` by `client_id`, verifies `tenant_id` match (404 if missing/cross-tenant), populates `contract.client_name = client.trading_name`
- `create_contract`: uses `model_dump(exclude={"client_name"})` then sets `client_name` from resolved value
- `list_contracts`: supports `client_id` filter parameter (`WHERE Contract.client_id == client_id`)
- `serialize_contract`: includes `client_id` in response dict

**`contracts/router.py`**
- `GET /contracts/`: exposes `client_id: UUID | None` query param, passes to `list_contracts`

### Frontend Changes

**`app/components/ClientCombobox.tsx`** (new)
- `"use client"` component wrapping Radix Popover
- Fetches `/api/clients?limit=200` on popover open (Next.js proxy route handles auth)
- Search: native `<input>` with client-side filter on `trading_name` and `nuit`
- Loading state: 3x `<Skeleton>` rows
- Empty state: "Nenhum cliente encontrado. Crie um cliente primeiro."
- Selected item: checkmark in amber, NUIT in IBM Plex Mono 11px in list row
- Below trigger when selected: `NUIT: {nuit}` in IBM Plex Mono 11px muted
- Trigger: full-width min-height 38px, amber focus ring matching DESIGN.md inputs

**`app/api/clients/route.ts`**
- Added `GET` handler: proxies to `GET /api/v1/clients` with `limit`/`offset` params
- Reads httpOnly cookies server-side, injects `Authorization` + `X-Tenant-Id`

**`app/components/ContractFormModal.tsx`**
- `ClientCombobox` replaces `<input name="client_name">` (free-text removed)
- State: `clientId`, `clientName`, `clientError` controlled by `ClientCombobox.onChange`
- Submit validation: `!clientId && !clientName` → sets `clientError = "Seleccione um cliente."`
- Payload: `client_id` UUID + `client_name` snapshot included in POST/PATCH body
- Edit mode: pre-populates `clientId`/`clientName` from `contract.client_id/client_name` on open

**`app/lib/contracts-api.ts`**
- `Contract` interface: added `client_id: string | null` field

## Tests

**`backend/tests/test_contracts_api.py`** (5 tests, all passing):

| Test | What it covers |
|------|---------------|
| `test_create_contract_requires_client_id_or_name` | 422 when neither client_id nor client_name provided |
| `test_create_contract_with_client_name_legacy` | Legacy client_name path still works, client_id = null |
| `test_create_contract_with_client_id` | client_name populated from Client.trading_name |
| `test_create_contract_client_id_cross_tenant` | 404 when client_id belongs to another tenant |
| `test_list_contracts_filter_by_client_id` | GET ?client_id= returns only matching contracts |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] No `cmdk` package — ComboBox built with Radix Popover + native elements**
- **Found during:** Task 2
- **Issue:** Plan specified using `Command`, `CommandEmpty`, `CommandGroup`, `CommandInput`, `CommandItem`, `CommandList` from `@/components/ui/command`. No `cmdk` package in `package.json` and no `command.tsx` in `components/ui/`.
- **Fix:** Implemented combobox using Radix `Popover` + native `<input>` search + `<ul>/<li>` list. All specified UI-SPEC behavior is preserved: loading skeletons, empty state message, NUIT in IBM Plex Mono, checkmark on selected item, NUIT below trigger.
- **Files modified:** `apps/manager/app/components/ClientCombobox.tsx`
- **Commit:** d0e0b15

**2. [Rule 2 - Missing functionality] GET /api/clients proxy route missing**
- **Found during:** Task 2
- **Issue:** `app/api/clients/route.ts` only had POST. ClientCombobox needs to fetch client list via the same Next.js proxy pattern (required because httpOnly cookies cannot be read by client components).
- **Fix:** Added GET handler to `/api/clients/route.ts` proxying to backend with auth headers.
- **Files modified:** `apps/manager/app/api/clients/route.ts`
- **Commit:** d0e0b15

**3. [Rule 2 - Missing functionality] `serialize_contract` missing `client_id` field**
- **Found during:** Task 1
- **Issue:** `serialize_contract` did not include `client_id` in the response dict — required for edit mode pre-population and for `test_create_contract_with_client_id` assertion.
- **Fix:** Added `"client_id": contract.client_id` to `serialize_contract` return dict.
- **Files modified:** `backend/app/modules/contracts/service.py`
- **Commit:** a2d8476

**4. [Rule 3 - Blocking] Contract type missing `client_id` field**
- **Found during:** Task 3
- **Issue:** `contracts-api.ts` `Contract` interface had no `client_id` field; TypeScript would error when accessing `contract.client_id` in ContractFormModal.
- **Fix:** Added `client_id: string | null` to `Contract` interface.
- **Files modified:** `apps/manager/app/lib/contracts-api.ts`
- **Commit:** c15c5cd

**5. [Rule 1 - Bug] Test URLs missing trailing slash caused 307 redirect**
- **Found during:** Task 1 test run
- **Issue:** FastAPI router redirects `/api/v1/contracts` (no slash) to `/api/v1/contracts/` (with slash) with 307. Tests were using `/api/v1/contracts` without trailing slash.
- **Fix:** Updated all test POST URLs to `/api/v1/contracts/`.
- **Commit:** a2d8476

## Known Stubs

None. All implemented behavior is fully wired.
