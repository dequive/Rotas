---
phase: 23-third-party-registry
plan: 02
subsystem: third_party
tags: [third-party, registry, crud, fastapi, pydantic, service-layer]
dependency_graph:
  requires: [23-01]
  provides: [third_party_api, third_party_service]
  affects: [main.py, third_party module]
tech_stack:
  added: []
  patterns: [serialize_*, _require_*, record_audit_log in same transaction, upsert pattern]
key_files:
  created:
    - backend/app/modules/third_party/schemas.py
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/router.py
  modified:
    - backend/app/main.py
decisions:
  - "Used str instead of EmailStr for contact_email — email-validator not installed in project venv; consistent with all other schemas in the codebase"
  - "Unauthenticated /provinces endpoint uses AsyncSessionLocal directly to avoid get_session dependency on principal"
  - "Sub-resource routes (/{tp_id}/roles, /{tp_id}/supplier-profile, etc.) registered before /{tp_id} to prevent FastAPI matching path segments as UUIDs"
  - "PATCH used for update_third_party (matches plan spec) rather than PUT, consistent with drivers router pattern"
metrics:
  duration: ~25min
  completed: 2026-06-19
  tasks: 3
  files: 4
---

# Phase 23 Plan 02: Third Party Registry — Pydantic schemas, service layer, and FastAPI router for full third party CRUD

## What Was Built

Three files implementing the complete API layer for the third-party registry module:

**schemas.py** — Pydantic v2 models with `ConfigDict(from_attributes=True)` on all `*Out` classes:
- `ThirdPartyCreate` / `ThirdPartyUpdate` / `ThirdPartyOut`
- `RoleCreate` / `RoleOut` with `VALID_ROLE_TYPES` constant
- `SupplierProfileCreate` / `SupplierProfileOut`
- `ServiceProviderProfileCreate` / `ServiceProviderProfileOut`
- `ProvinceOut`

**service.py** — Full CRUD following the drivers/clients pattern:
- Serializers: `serialize_third_party`, `serialize_role`, `serialize_supplier_profile`, `serialize_service_provider_profile`
- Guards: `_require_third_party` (404 on missing/wrong-tenant), `_nuit_exists` (409 duplicate check)
- CRUD: `create_third_party`, `list_third_parties`, `get_third_party`, `update_third_party`
- Role CRUD: `create_role` (validates role_type, enforces unique per tp), `list_roles`
- Profile upsert: `upsert_supplier_profile`, `upsert_service_provider_profile` (SELECT then INSERT or UPDATE)
- Reference: `list_provinces` (no tenant filter, ORDER BY name)
- All mutations call `record_audit_log` inside the same DB session before `db.commit()`

**router.py** — FastAPI `APIRouter(prefix="/third-party")`:
- `GET /provinces` — unauthenticated (uses `AsyncSessionLocal` directly, no principal)
- `POST /` → 201, `GET /` with status/limit/offset filters
- `GET /{tp_id}`, `PATCH /{tp_id}`
- `GET /{tp_id}/roles`, `POST /{tp_id}/roles` → 201
- `PUT /{tp_id}/supplier-profile`, `PUT /{tp_id}/service-provider-profile`
- Sub-resource routes registered before `/{tp_id}` to avoid path segment conflicts
- Auth: `require_roles(*WRITE_ROLES)` on mutations, `require_roles(*DASHBOARD_ROLES)` on reads

**main.py** — Added import and `app.include_router(third_party_router, prefix=api)` between workshop and control_tower routers.

## Verification

```
python -c "from app.modules.third_party.router import router; print(router.prefix)"
# /third-party

python -c "from app.modules.third_party.router import router; print([r.path for r in router.routes])"
# ['/third-party/provinces', '/third-party', '/third-party', 
#  '/third-party/{tp_id}/roles', '/third-party/{tp_id}/roles',
#  '/third-party/{tp_id}/supplier-profile', '/third-party/{tp_id}/service-provider-profile',
#  '/third-party/{tp_id}', '/third-party/{tp_id}']
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced EmailStr with str for contact_email**
- **Found during:** Task 1 — import check
- **Issue:** `email-validator` package not installed in the project venv; `EmailStr` raises `ImportError` at schema class construction time, blocking the entire module
- **Fix:** Changed `Optional[EmailStr]` to `Optional[str]` in `ThirdPartyCreate` and `ThirdPartyUpdate`. No other schema in the codebase uses `EmailStr` — this is the project-wide convention
- **Files modified:** `backend/app/modules/third_party/schemas.py`
- **Commit:** bac3793

## Known Stubs

None — all service functions are fully implemented with real DB queries.

## Self-Check: PASSED

- `backend/app/modules/third_party/schemas.py` — exists, verified
- `backend/app/modules/third_party/service.py` — exists, verified
- `backend/app/modules/third_party/router.py` — exists, verified
- `backend/app/main.py` — modified with import + include_router
- Commit bac3793 — present in git log
