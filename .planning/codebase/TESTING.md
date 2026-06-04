# Testing Patterns
_Last updated: 2026-06-04_

## Summary

The backend has 18 test files covering all major domain modules through integration-style API tests against a real PostgreSQL database. There is no `conftest.py` — each test file is self-contained with its own seed helpers. Neither frontend app has any test infrastructure configured. Coverage tooling is not set up.

---

## Test Framework

**Runner:** pytest 8.2+ with `pytest-asyncio` 0.23+
**Config:** `backend/pyproject.toml`
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**HTTP client:** `httpx.AsyncClient` with `httpx.ASGITransport(app=app)` — the FastAPI app is tested in-process, no server required.

**Run commands:**
```bash
# From backend/
pytest                          # run all tests
pytest tests/test_billing_domain.py   # single file
pytest -k "idempotency"         # filter by name
# No coverage command configured — add --cov=app if needed
```

---

## Test File Inventory

All 18 test files live flat in `backend/tests/`. There is no subdirectory organisation.

| File | Type | Domain | DB Required |
|------|------|--------|-------------|
| `test_billing_domain.py` | Unit | Billing pure rules | No |
| `test_auth_api.py` | API integration | Auth, JWT, pairing | Yes |
| `test_http_idempotency.py` | API integration | Idempotency (HTTP) | Yes |
| `test_sync_idempotency.py` | API integration | Idempotency (sync/batch) | Yes |
| `test_request_context_audit.py` | API integration | Request ID, audit correlation | Yes |
| `test_vehicle_driver_api.py` | API integration | Vehicles, drivers, compliance, history | Yes |
| `test_cargo_billing_flow.py` | API integration | Full cargo+billing pipeline, disputes | Yes |
| `test_fuel_api.py` | API integration | Fuel logs, consumption, anomalies, sync | Yes |
| `test_fuel_operations_api.py` | API integration | Internal fuel tanks, movements, stock | Yes |
| `test_trip_orders_api.py` | API integration | Trip orders, dispatch | Yes |
| `test_dispatch_execution_api.py` | API integration | Trip lifecycle, incidents, costs | Yes |
| `test_workshop_operations_api.py` | API integration | Maintenance requests, work orders | Yes |
| `test_checklist_api.py` | API integration | Checklists, templates | Yes |
| `test_control_tower_api.py` | API integration | Control tower board, queues | Yes |
| `test_tenant_user_alert_api.py` | API integration | Tenants, users, alerts | Yes |
| `test_files_api.py` | API integration | File uploads, tenant scoping | Yes |
| `test_operational_close_api.py` | API integration | Trip close, execution events | Yes |
| `test_operational_exceptions_api.py` | API integration | Operational exceptions lifecycle | Yes |

---

## Test Structure

### No conftest.py — Self-Contained Files

Each test file provides its own:
- Seed function (`seed_entities`, `create_seed_entities`, `create_tenant`) that writes directly to the DB via `AsyncSessionLocal`
- `auth_headers(tenant_id)` helper returning `{"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}`
- `create_api_client()` helper returning an `httpx.AsyncClient`

**Mandatory per-file fixture:**
```python
@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()
```
This prevents connection pool contamination between tests.

### Typical Test Shape
```python
@pytest.mark.asyncio
async def test_vehicle_crud_and_plate_conflict_are_tenant_scoped() -> None:
    tenant = await create_tenant()
    other_tenant = await create_tenant()

    async with await create_api_client() as client:
        # 1. Happy path
        response = await client.post("/api/v1/vehicles", headers=auth_headers(tenant.id), json={...})
        assert response.status_code == 200

        # 2. Conflict within same tenant
        duplicate = await client.post("/api/v1/vehicles", headers=auth_headers(tenant.id), json={...})
        assert duplicate.status_code == 409

        # 3. Same data allowed in different tenant (isolation)
        other = await client.post("/api/v1/vehicles", headers=auth_headers(other_tenant.id), json={...})
        assert other.status_code == 200

    # 4. DB-level assertions
    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(select(AuditLog.action).where(...))
        assert set(audit_rows.scalars()) == {"vehicle.created", "vehicle.updated"}
```

### Postgres Skip Pattern
Tests requiring Postgres that can fail locally wrap with:
```python
from sqlalchemy.exc import OperationalError
try:
    ...
except OperationalError as exc:
    pytest.skip(f"Local Postgres is not available: {exc}")
```
Used in: `test_cargo_billing_flow.py`, `test_trip_orders_api.py`, `test_dispatch_execution_api.py`, `test_workshop_operations_api.py`, `test_operational_close_api.py`, `test_operational_exceptions_api.py`.

---

## Authentication in Tests

Tests use the dev token shortcut defined in `backend/app/core/auth.py`:
```python
if token == "test-token" and settings.environment in {"development", "test"}:
    return Principal(subject="development:user", tenant_id=x_tenant_id, scope="dashboard", role="admin")
```

All test requests send:
```python
{"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}
```

The `test_auth_api.py` file tests the real JWT flow using `hash_password` + actual login endpoints.

---

## What Is Tested

### Idempotency
- **HTTP idempotency** (`test_http_idempotency.py`): same key + same payload replays response; same key + different payload returns 409; DB confirms single row created; audit log has exactly 1 entry.
- **Sync/batch idempotency** (`test_sync_idempotency.py`): offline batch replay returns `"status": "processed"` and `"message": "idempotent_replay"` with same `server_id`; conflict returns `"status": "conflict"` with `"error_code": "idempotency_key_reused"`; DB confirms single `DeliveryProof`.
- Idempotency is also verified inline in many other tests (vehicles, fuel, document renewals, billing issue, waivers, dispute).

### Multitenancy Isolation
- Vehicle plate uniqueness is **tenant-scoped**: same plate allowed in different tenant (`test_vehicle_driver_api.py`).
- Driver phone uniqueness is tenant-scoped.
- Vehicle/driver history returns 404 for wrong tenant.
- File access is tenant-scoped (`test_files_api.py`).
- Tenant `me` and user management are tenant-scoped (`test_tenant_user_alert_api.py`).

### Audit Log Assertions
Tests directly query `AuditLog` after API calls to assert:
- Correct `action` values are recorded (using `set(audit_rows.scalars())` pattern).
- `correlation_id` matches the `X-Request-Id` header (`test_request_context_audit.py`).
- `new_values` contains correct field values (e.g., `permit_audit.new_values["client_name"]`).
- Exactly one audit entry for idempotent replays.

### Compliance and Waivers
`test_vehicle_driver_api.py` tests:
- Expired vehicle/driver documents block trip creation with `vehicle_compliance_blocked` / `driver_compliance_blocked`.
- Tenant compliance policy (`vehicle_required_documents`, `driver_required_documents`) enforces missing documents.
- `POST /api/v1/operations/waivers` unblocks compliance-blocked assignments.
- Availability summaries (`/vehicles/{id}/availability`) return correct `blockers`, `warnings`, `compliance_violations`, `active_waivers`.
- Document renewal (`/vehicles/{id}/documents/{type}/renew`) links file, updates document dates, and unblocks assignment.

### Billing Domain (Unit Tests)
`test_billing_domain.py` tests pure functions without a DB:
- `belongs_to_billing_period`: uses delivery date, not loading date; trip loaded in May but delivered in June falls in June period.
- `billing_status_for_delivery`: undelivered trip = `BILLING_PENDING_DELIVERY`.
- `can_create_billing_item`: requires both `contract_id` and `delivery_proof_status == "validated"`.
- `belongs_to_billing_period` raises `ValueError` for invalid period (start == end).

### Full Cargo-to-Billing Pipeline
`test_cargo_billing_flow.py` tests the complete lifecycle:
1. Create trip (no contract) → `billing_status == "pending_delivery_proof"`
2. Associate contract
3. Create load permit + cargo manifest
4. Start trip
5. Create delivery proof → `status == "pending"`
6. Validate proof → `billing_status == "billable"`
7. Check billable candidates appear in billing API
8. Create billing document (draft)
9. Verify blocked on negative margin → waiver unblocks
10. Issue billing document → `status == "issued"`, trip → `billing_status == "billed"`
11. Export to PDF and XLSX (asserts file headers `%PDF-1.4` and `PK`)
12. Dispute flow: dispute blocks validation → resolve dispute → becomes billable again → `OperationalException` lifecycle audited

### Auth Flow
`test_auth_api.py` tests:
- Login → access + refresh tokens
- Use access token to get tenant
- `X-Tenant-Id` mismatch returns 403
- Refresh token rotation (old token rejected after rotation)
- Logout invalidates token
- Driver pairing code: generate → pair → code consumed on replay → bootstrap endpoint accessible → refresh rotates

### Fuel
`test_fuel_api.py` tests:
- First refuel: `km_since_last == null`, `consumption == null`, `flagged == false`
- Second refuel with high consumption: `consumption_l_per_100km == 40`, `flagged == true`
- Anomalies endpoint returns only flagged logs
- Verify action sets `is_verified=True`, `flagged=False`
- Odometer regression rejected with `odometer_regression` (409)
- Sync fuel log creation is idempotent
- Audit: `fuel_log.created`, `fuel_log.verified`, `vehicle.odometer_updated_from_fuel`

### Request Context
`test_request_context_audit.py` tests:
- Client-supplied `X-Request-Id` is echoed in response and stored in `AuditLog.correlation_id`
- Missing `X-Request-Id`: error response generates one; `error.request_id` matches `x-request-id` header

---

## What Is NOT Tested

### No Frontend Tests
Neither `apps/driver/` nor `apps/manager/` has any test files or test framework configured. `package.json` scripts contain only `dev`, `build`, `typecheck`, and `lint`. No Vitest, Jest, Playwright, or Cypress setup exists.

### No Unit Tests for Services
No tests call service functions in isolation with mocked repositories. All service-level tests go through the HTTP layer (ASGI transport). The exception is `test_cargo_billing_flow.py`, which calls service functions directly with a real DB session.

### No Load/Concurrency Tests
`ENGINEERING_STANDARDS.md` explicitly requires testing two simultaneous submissions to the same vehicle/trip/idempotency key, and a peak sync burst from multiple returning vehicles. No such tests exist yet.

### No Tests for These Areas
- `alerts` — alert delivery, WhatsApp/SMS adapters
- `sync` bootstrap endpoint (beyond the auth test)
- `known_routes_router` endpoints
- `control_tower` queue configuration per tenant
- Password reset / MFA flows (noted as gap in `MODULE_CLOSURE_MATRIX.md`)
- Storage adapter (R2) — only local filesystem storage is tested
- Token revocation admin endpoint
- Alembic migrations (no migration tests)
- CORS middleware behaviour
- Concurrent writes to the same entity (race condition / double-booking)
- `operations` module waiver expiry enforcement

### Incomplete Module Coverage (per MODULE_CLOSURE_MATRIX.md)
Per the closure matrix, the following modules are not fully closed and may lack coverage on their open items:
- `audit`: transversal residual coverage
- `billing`: reconciliation and advanced margin policies
- `fuel`: additional stock policies, deviation handling, segregation rules
- `workshop`: preventive scheduling, board visual
- `checklists`: additional policies
- `control_tower`: per-tenant queue configuration
- `alerts`: external adapters (WhatsApp, SMS)
- `users`/`auth`: password recovery, MFA, administrative revocation

---

## Coverage Configuration

No coverage tooling is configured. To run with coverage:
```bash
pip install pytest-cov
pytest --cov=app --cov-report=html tests/
```
No coverage targets are enforced in CI (no CI pipeline detected).

---

## Fixtures and Seed Pattern

No shared fixtures in `conftest.py`. Each test file defines local seed helpers.

**Canonical seed pattern:**
```python
async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Fuel {suffix}", slug=f"fuel-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(tenant_id=tenant.id, plate=f"FUEL-{suffix}", category="pesado", fuel_type="gasoleo")
        driver = Driver(tenant_id=tenant.id, full_name=f"Driver Fuel {suffix}", phone=f"25886{suffix[:7]}")
        db.add_all([vehicle, driver])
        await db.commit()
        ...
        return tenant, vehicle, driver
```

Using `uuid4().hex[:8]` suffix on all names and plates prevents unique constraint collisions between test runs.

---

## Gaps / Unknowns

- No `conftest.py` means the `dispose_engine_between_tests` fixture is copy-pasted across all 17 DB-backed test files — a refactoring opportunity.
- Tests that skip on `OperationalError` will silently pass in CI if Postgres is unavailable — there is no enforcement that a DB must be present.
- No test environment `.env` documented; tests rely on the default `DATABASE_URL` in `app/config.py` pointing to `postgresql+asyncpg://rotas:rotas@localhost:55432/rotas`.
- The `import_all_models()` call at module level in each test file is a workaround for SQLAlchemy model registration; unclear if this is necessary with all current alembic migrations applied.
- No mutation testing, property-based testing (Hypothesis), or snapshot testing in use.
