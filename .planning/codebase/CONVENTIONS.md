# Coding Conventions
_Last updated: 2026-06-04_

## Summary

ROTAS follows a modular monolith pattern where each domain module owns its own `models.py`, `schemas.py`, `router.py`, `service.py`, and optionally a `domain.py` for pure business rules. All backend code is Python 3.11+ using FastAPI + SQLAlchemy 2.0 async. The authoritative standards document is `docs/ENGINEERING_STANDARDS.md`.

---

## Module Structure

Every domain module lives under `backend/app/modules/<module>/` and must have:

```
backend/app/modules/<module>/
    __init__.py
    models.py       # SQLAlchemy ORM models — no app logic
    schemas.py      # Pydantic input/output contracts
    router.py       # HTTP layer only: routing, dependencies, response
    service.py      # Use-case coordination; calls models and audit
    domain.py       # Optional: pure business rule functions (no DB, no HTTP)
```

Modules with domain logic extract it into `domain.py`:
- `backend/app/modules/billing/domain.py` — `BillableTripCandidate`, `billing_status_for_candidate`, `can_create_billing_item`, `belongs_to_billing_period`

Cross-module access must go through the other module's `service.py` or publicly exported contracts — never directly import another module's ORM internals.

---

## Naming Patterns

**Files and directories:** `snake_case`. Split routers for large modules use `_router` suffix (e.g., `fuel/operations_router.py`, `fuel/operations_schemas.py`).

**Python:** `snake_case` for functions and variables. `PascalCase` for classes, Pydantic models, and SQLAlchemy models. `UPPER_SNAKE_CASE` for module-level constants (e.g., `IDEMPOTENCY_TTL_DAYS`, `BILLING_BILLABLE`, `WRITE_ROLES`).

**Action names for audit logs:** `module.action_verb` format, all lowercase with dot separator. Examples from actual code:
- `vehicle.created`, `vehicle.updated`, `vehicle.qr_code_issued`, `vehicle.document_renewed`, `vehicle.odometer_updated_from_fuel`
- `driver.created`, `driver.updated`, `driver.document_renewed`
- `trip.billing_finalized`
- `cargo.load_permit_created`, `cargo.delivery_proof_created`, `cargo.delivery_proof_validated`, `cargo.delivery_proof_disputed`, `cargo.delivery_dispute_resolved`
- `billing.document_created`, `billing.item_created`, `billing.document_issued`, `billing.item_billed`
- `contract.created`, `contract.updated`
- `fuel_log.created`, `fuel_log.verified`
- `operational_exception.created`, `operational_exception.resolved`

**Error codes:** `snake_case` strings, descriptive of the rule violated. Examples: `vehicle_compliance_blocked`, `driver_compliance_blocked`, `odometer_regression`, `idempotency_key_reused`, `negative_margin_requires_approval`, `delivery_proof_disputed`, `tenant_mismatch`, `invalid_token_scope`.

**API prefixes:** All routes registered under `/api/v1` via `settings.api_v1_prefix`. Module routers set their own prefix: `APIRouter(prefix="/vehicles", tags=["vehicles"])`.

---

## Linting and Formatting

**Tool:** `ruff` (configured in `backend/pyproject.toml`).

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Rules enforced: pycodestyle errors (`E`), Pyflakes (`F`), isort (`I`), pyupgrade (`U`), flake8-bugbear (`B`). No formatter config beyond ruff's default (implicit Black-compatible style).

---

## API Error Envelope

All errors use a consistent JSON envelope via `ApiError` (`backend/app/core/errors.py`). There is **no success envelope** — success responses return the domain object directly as a flat dict.

**Error response shape:**
```json
{
  "error": {
    "code": "vehicle_compliance_blocked",
    "message": "Human-readable explanation.",
    "details": { "violations": [...] },
    "request_id": "x-request-id-value"
  }
}
```

**Raising errors in services:**
```python
raise ApiError(
    "vehicle_not_found",
    "Vehicle not found.",
    status_code=404
)

raise ApiError(
    "vehicle_compliance_blocked",
    "Vehicle has compliance violations that block assignment.",
    status_code=409,
    details={"violations": [...]}
)
```

The `not_implemented(operation)` helper raises a 501 with `code="not_implemented"`.

Stack traces are **never** sent to the client — `api_error_handler` only serialises `code`, `message`, `details`, and `request_id`.

---

## Request ID / Correlation

`RequestContextMiddleware` (`backend/app/core/request_context.py`) intercepts every request:
- Reads `X-Request-Id` header (max 128 chars). If absent or too long, generates a `uuid4().hex`.
- Stores in a `ContextVar` accessible via `get_request_id()`.
- Echoes the value back in the `X-Request-Id` response header.
- Error responses include `request_id` in the error body.

Audit logs automatically pick up the current `request_id` as `correlation_id` via `get_request_id()` in `record_audit_log`.

---

## Authentication Pattern

JWT access tokens (HS256) are short-lived (15 min default). Refresh tokens are opaque SHA-256 hashes stored in the DB.

**`Principal` dataclass** (`backend/app/core/auth.py`) carries:
```python
@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: UUID
    scope: str          # "dashboard" or "driver_app"
    role: str | None    # "owner" | "admin" | "manager" | "viewer" (dashboard only)
    user_id: UUID | None
    driver_id: UUID | None
    device_id: str | None
```

In test/dev environments, `Authorization: Bearer test-token` + `X-Tenant-Id` header activates a shortcut that returns a `Principal` with `scope="dashboard"` and `role="admin"` — **no DB hit for tests**.

Tenant is always resolved from the token. Clients may send `X-Tenant-Id` for double-check; a mismatch raises 403 `tenant_mismatch`.

---

## RBAC Pattern

Defined in `backend/app/core/permissions.py`:

```python
OWNER   = "owner"
ADMIN   = "admin"
MANAGER = "manager"
VIEWER  = "viewer"

DASHBOARD_ROLES = {OWNER, ADMIN, MANAGER, VIEWER}   # read access
WRITE_ROLES     = {OWNER, ADMIN, MANAGER}            # mutation access
ADMIN_ROLES     = {OWNER, ADMIN}                     # administrative ops
```

Route-level enforcement via FastAPI dependency:
```python
@router.post("")
async def create_vehicle(
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    ...
```

`require_roles(*roles)` raises `ApiError("forbidden", ..., 403)` with `details={"required_roles": sorted(allowed)}` on failure.

Driver-app endpoints use `get_driver_principal` which additionally asserts `principal.scope == "driver_app"`.

---

## Multitenancy Isolation

- Every tenant-owned table carries `tenant_id` (indexed FK to `tenants.id`).
- Tenant ID is **extracted from the JWT** by `get_current_principal` — clients can never inject their own `tenant_id` into request bodies for privileged operations.
- Services always scope queries with `WHERE tenant_id = ?`. The `_require_vehicle` / `_require_driver` pattern (checking `vehicle.tenant_id != tenant_id`) is the canonical way to enforce isolation on lookups.
- Tests explicitly verify cross-tenant isolation: e.g., same plate allowed in tenant B after creation in tenant A; history endpoint returns 404 for wrong tenant.

---

## Idempotency Pattern

Two idempotency mechanisms exist side by side:

### HTTP Idempotency (manager dashboard mutations)
`execute_http_idempotent` (`backend/app/core/idempotency.py`) wraps a mutating handler:
- Client sends `Idempotency-Key` header.
- First call: inserts `IdempotencyKey` record, executes handler, stores response.
- Replay (same key + same payload hash): returns cached response, no duplicate write.
- Replay with different payload: raises `ApiError("idempotency_key_reused", ..., 409)`.
- TTL: 30 days for operational entities, 90 days for billing entities (`billing_document`, `billing_item`).

Router usage:
```python
idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None
return await execute_http_idempotent(
    db,
    tenant_id=principal.tenant_id,
    user_id=principal.user_id,
    idempotency_key=idempotency_key,
    operation="vehicles.create",
    entity_type="vehicle",
    payload=payload,
    handler=lambda: service.create_vehicle(...),
)
```

### Sync Idempotency (offline PWA batch)
`POST /api/v1/sync/batch` accepts `{"device_id": "...", "operations": [...]}`. Each operation carries its own `idempotency_key`. Conflict returns `{"status": "conflict", "error_code": "idempotency_key_reused"}` in the batch result — the HTTP status is still 200.

---

## Audit Log Pattern

`record_audit_log` (`backend/app/modules/audit/service.py`) is called by services after every critical mutation:

```python
await record_audit_log(
    db,
    tenant_id=tenant_id,
    action="vehicle.created",
    entity_type="vehicle",
    entity_id=vehicle.id,
    user_id=actor_id,
    new_values={"plate": ..., "category": ...},
)
```

The `AuditLog` model (`backend/app/modules/audit/models.py`) stores:
- `tenant_id`, `user_id`, `driver_id`, `action`, `entity_type`, `entity_id`
- `old_values` (JSON), `new_values` (JSON)
- `ip_address`, `user_agent`
- `correlation_id` — automatically set from `get_request_id()` if not provided

`old_values` and `new_values` are serialised via `jsonable_encoder` before storage.

---

## Service Layer Conventions

- Services return plain `dict` (never raw ORM objects) for public-facing flows.
- Helper functions prefixed with `_` (e.g., `_require_vehicle`, `_plate_exists`) are module-private.
- `serialize_vehicle(vehicle: Vehicle) -> dict` pattern is used to decouple ORM shape from response shape.
- Services call `record_audit_log` directly inside the same DB session before committing, ensuring audit and mutation are in the same transaction.
- Services accept a `db: AsyncSession` parameter — sessions are opened by the router via `Depends(get_session)`.

---

## Router Conventions

- Routers handle HTTP mechanics only: parsing headers, injecting dependencies, forwarding to service.
- No business logic in routers.
- Response type annotations are omitted (returns untyped `dict`/`list` from service).
- Pagination via `limit` and `offset` query params with sensible defaults and bounds: `Query(50, ge=1, le=200)`.

---

## Frontend Conventions

**Manager (`apps/manager/`):** Next.js 14 + TypeScript 5.5. No test framework configured. No ESLint config detected in `package.json` beyond `next lint`.

**Driver PWA (`apps/driver/`):** React 18 + Vite + TypeScript 5.5. Offline storage via Dexie (IndexedDB wrapper). No test framework configured. TypeScript strict-mode is the only quality gate (`tsc --noEmit`).

Frontend naming follows TypeScript conventions: `PascalCase` for components and types, `camelCase` for functions and variables, kebab-case filenames for route files (Next.js convention for manager).

---

## Gaps / Unknowns

- No ESLint config file found for either frontend app — linting beyond TypeScript is unclear.
- Manager app has no explicit API error-handling conventions established in code (no shared `useError` hook or error boundary pattern observed).
- No shared `types/` package between driver and manager apps — schemas are duplicated or implicit.
- `domain.py` files only exist in `billing/`; other modules with complex rules (e.g., `availability`, `compliance`) embed rules in `service.py` — inconsistent placement.
- No pre-commit hooks configured (no `.pre-commit-config.yaml` found).
