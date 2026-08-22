"""F7.4: replay and payload-conflict matrix over the critical HTTP mutations.

Every mutation the Manager can retry carries an `Idempotency-Key`. Two
properties must hold for each of them, and neither is provable by inspection:

1. **Replay** — same key + same payload returns the stored response and writes
   nothing new. A duplicate row here is a duplicate invoice, a duplicate trip
   or a double-paid advance.
2. **Conflict** — same key + a different payload is rejected with 409
   `idempotency_key_reused`, instead of silently returning the first response
   for a request the caller did not make.

Before this module only `trips.create` and the sync batch proved property 2,
against 54 registered idempotent operations. The cases below cover the
mutations reachable with cheap seeding; the remainder are tracked in the F7.4
row of `docs/FRONTEND_REFOUNDATION_PLAN.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.database import import_all_models
from app.modules.checklists.models import ChecklistTemplate
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelTank
from app.modules.trip_orders.models import TripOrder
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenanceRequest,
    SparePartInventory,
    WorkshopTool,
)

import_all_models()


def _suffix() -> str:
    return uuid4().hex[:8]


class Case:
    """One mutation under test.

    `payload` and `mutated` are callables so each parametrised run gets fresh
    unique values — a replayed plate or SKU would otherwise collide with the
    previous run rather than with the idempotency key.
    """

    def __init__(
        self,
        name: str,
        path: str | Callable[[dict], str],
        model: Any,
        payload: Callable[[dict], dict],
        mutated: Callable[[dict], dict],
        expected_status: tuple[int, ...] = (200, 201),
    ) -> None:
        self.name = name
        self._path = path
        self.model = model
        self.payload = payload
        self.mutated = mutated
        self.expected_status = expected_status

    def path(self, ctx: dict) -> str:
        """Financial mutations hang off a parent document, so the path is
        resolved from the context rather than being a constant."""
        return self._path(ctx) if callable(self._path) else self._path

    def __repr__(self) -> str:  # pragma: no cover - pytest id only
        return self.name


CASES: list[Case] = [
    Case(
        name="vehicles.create",
        path="/api/v1/vehicles",
        model=Vehicle,
        payload=lambda ctx: {
            "plate": f"IDM-{ctx['suffix'].upper()}",
            "category": "pesado",
            "fuel_type": "gasoleo",
        },
        mutated=lambda ctx: {
            "plate": f"IDM-{ctx['suffix'].upper()}",
            "category": "ligeiro",
            "fuel_type": "gasoleo",
        },
    ),
    Case(
        name="drivers.create",
        path="/api/v1/drivers",
        model=Driver,
        payload=lambda ctx: {"full_name": f"Motorista {ctx['suffix']}"},
        mutated=lambda ctx: {
            "full_name": f"Motorista {ctx['suffix']}",
            "phone": "+258840000001",
        },
    ),
    Case(
        name="users.create",
        path="/api/v1/users",
        model=User,
        payload=lambda ctx: {
            "email": f"idem-{ctx['suffix']}@test.local",
            "password": "Palavra-Passe-Forte-1",
            "full_name": f"Utilizador {ctx['suffix']}",
            "role": "viewer",
        },
        mutated=lambda ctx: {
            "email": f"idem-{ctx['suffix']}@test.local",
            "password": "Palavra-Passe-Forte-1",
            "full_name": f"Utilizador {ctx['suffix']}",
            "role": "manager",
        },
    ),
    Case(
        name="checklists.template.create",
        path="/api/v1/checklist-templates",
        model=ChecklistTemplate,
        payload=lambda ctx: {
            "name": f"Modelo {ctx['suffix']}",
            "type": "pre_trip",
            "items": [{"id": "pneus", "label": "Pneus", "blocking": True}],
        },
        mutated=lambda ctx: {
            "name": f"Modelo {ctx['suffix']}",
            "type": "post_trip",
            "items": [{"id": "pneus", "label": "Pneus", "blocking": True}],
        },
    ),
    Case(
        name="fuel_operations.tank.create",
        path="/api/v1/fuel-operations/tanks",
        model=FuelTank,
        payload=lambda ctx: {
            "code": f"TQ-{ctx['suffix'].upper()}",
            "name": f"Tanque {ctx['suffix']}",
            "capacity_liters": 10000,
            "minimum_stock_liters": 1000,
        },
        mutated=lambda ctx: {
            "code": f"TQ-{ctx['suffix'].upper()}",
            "name": f"Tanque {ctx['suffix']}",
            "capacity_liters": 20000,
            "minimum_stock_liters": 1000,
        },
    ),
    Case(
        name="workshop.spare_part.create",
        path="/api/v1/workshop/spare-parts",
        model=SparePartInventory,
        payload=lambda ctx: {
            "sku": f"SKU-{ctx['suffix'].upper()}",
            "name": f"Peca {ctx['suffix']}",
            "unit": "unit",
            "minimum_quantity": 5,
        },
        mutated=lambda ctx: {
            "sku": f"SKU-{ctx['suffix'].upper()}",
            "name": f"Peca {ctx['suffix']}",
            "unit": "unit",
            "minimum_quantity": 10,
        },
    ),
    Case(
        name="workshop.tool.create",
        path="/api/v1/workshop/tools",
        model=WorkshopTool,
        payload=lambda ctx: {
            "code": f"FER-{ctx['suffix'].upper()}",
            "name": f"Ferramenta {ctx['suffix']}",
            "is_critical": False,
        },
        mutated=lambda ctx: {
            "code": f"FER-{ctx['suffix'].upper()}",
            "name": f"Ferramenta {ctx['suffix']}",
            "is_critical": True,
        },
    ),
    Case(
        name="workshop.maintenance_request.create",
        path="/api/v1/workshop/maintenance-requests",
        model=MaintenanceRequest,
        payload=lambda ctx: {
            "vehicle_id": str(ctx["vehicle_id"]),
            "request_type": "corrective",
            "priority": "normal",
            "description": f"Revisao {ctx['suffix']}",
        },
        mutated=lambda ctx: {
            "vehicle_id": str(ctx["vehicle_id"]),
            "request_type": "corrective",
            "priority": "high",
            "description": f"Revisao {ctx['suffix']}",
        },
    ),
    Case(
        name="contracts.create",
        path="/api/v1/contracts/",
        model=Contract,
        payload=lambda ctx: {
            "client_name": f"Cliente {ctx['suffix']}",
            "contract_reference": f"CTR-{ctx['suffix'].upper()}",
            "service_type": "cargo_transport",
            "billing_cycle": "monthly",
            "billing_basis": "trip",
            "currency": "MZN",
        },
        mutated=lambda ctx: {
            "client_name": f"Cliente {ctx['suffix']}",
            "contract_reference": f"CTR-{ctx['suffix'].upper()}",
            "service_type": "cargo_transport",
            "billing_cycle": "weekly",
            "billing_basis": "trip",
            "currency": "MZN",
        },
    ),
    Case(
        name="trip_orders.create",
        path="/api/v1/trip-orders",
        model=TripOrder,
        payload=lambda ctx: {
            "origin": "Maputo",
            "destination": "Beira",
            "requested_pickup_date": ctx["pickup_date"],
            "customer_reference": f"REF-{ctx['suffix'].upper()}",
        },
        mutated=lambda ctx: {
            "origin": "Maputo",
            "destination": "Nampula",
            "requested_pickup_date": ctx["pickup_date"],
            "customer_reference": f"REF-{ctx['suffix'].upper()}",
        },
    ),
]


async def build_context(db, owner_tenant_id: UUID) -> dict:
    """Minimal prerequisites for one tenant: a vehicle for the cases that need it.

    Built per tenant on purpose. A payload that points at another tenant's
    vehicle is correctly rejected with 404 `vehicle_not_found`, which would
    mask what the idempotency tests are trying to observe.
    """
    suffix = _suffix()
    vehicle = Vehicle(tenant_id=owner_tenant_id, plate=f"CTX-{suffix.upper()}", category="pesado")
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return {
        "suffix": suffix,
        "vehicle_id": vehicle.id,
        "pickup_date": (date.today() + timedelta(days=3)).isoformat(),
    }


@pytest.fixture
async def matrix_context(db, tenant_id) -> dict:
    return await build_context(db, tenant_id)


async def _count(db, model: Any, tenant_id: UUID) -> int:
    return await db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_replay_returns_stored_response_without_writing_again(
    case: Case, async_client, auth_headers, db, tenant_id, matrix_context
) -> None:
    """Same key + same payload: one row, one response, twice."""
    key = f"{case.name}:{uuid4().hex}"
    headers = {**auth_headers, "Idempotency-Key": key}
    body = case.payload(matrix_context)

    before = await _count(db, case.model, tenant_id)

    first = await async_client.post(case.path(matrix_context), json=body, headers=headers)
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    replay = await async_client.post(case.path(matrix_context), json=body, headers=headers)
    assert replay.status_code in case.expected_status, f"{case.name}: {replay.text}"

    first_id = first.json().get("id")
    assert first_id is not None, f"{case.name}: resposta sem id"
    assert replay.json().get("id") == first_id, f"{case.name}: replay devolveu outra entidade"

    after = await _count(db, case.model, tenant_id)
    assert after == before + 1, f"{case.name}: replay escreveu de novo — {before} -> {after}, esperado {before + 1}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_same_key_with_different_payload_is_rejected(
    case: Case, async_client, auth_headers, db, tenant_id, matrix_context
) -> None:
    """Same key + different payload: 409 idempotency_key_reused, no second row."""
    key = f"{case.name}:{uuid4().hex}"
    headers = {**auth_headers, "Idempotency-Key": key}

    first = await async_client.post(case.path(matrix_context), json=case.payload(matrix_context), headers=headers)
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    after_first = await _count(db, case.model, tenant_id)

    conflict = await async_client.post(case.path(matrix_context), json=case.mutated(matrix_context), headers=headers)
    assert conflict.status_code == 409, (
        f"{case.name}: payload divergente aceite com {conflict.status_code} — {conflict.text}"
    )
    assert conflict.json()["error"]["code"] == "idempotency_key_reused", conflict.text

    after_conflict = await _count(db, case.model, tenant_id)
    assert after_conflict == after_first, f"{case.name}: conflito escreveu na base — {after_first} -> {after_conflict}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_same_key_is_scoped_per_tenant(
    case: Case, async_client, auth_headers, db, tenant_id, matrix_context
) -> None:
    """A key burnt in tenant A must not shadow the same key in tenant B.

    Idempotency keys are stored per tenant. If they were global, one tenant
    could replay another tenant's response, or block their writes by guessing
    a key.
    """
    from app.modules.tenants.models import Tenant

    suffix = _suffix()
    other = Tenant(name=f"Tenant Idem B {suffix}", slug=f"idem-b-{suffix}")
    db.add(other)
    await db.commit()
    await db.refresh(other)

    key = f"{case.name}:shared:{uuid4().hex}"
    body = case.payload(matrix_context)

    first = await async_client.post(
        case.path(matrix_context), json=body, headers={**auth_headers, "Idempotency-Key": key}
    )
    assert first.status_code in case.expected_status, f"{case.name}: {first.text}"

    other_headers = {
        "Authorization": auth_headers["Authorization"],
        "X-Tenant-Id": str(other.id),
        "Idempotency-Key": key,
    }
    other_context = await build_context(db, other.id)
    # build_context may itself have seeded a row of this model (the vehicle),
    # so the assertion is on the delta, not on an absolute count.
    before_other = await _count(db, case.model, other.id)

    second = await async_client.post(case.path(matrix_context), json=case.payload(other_context), headers=other_headers)
    assert second.status_code in case.expected_status, (
        f"{case.name}: chave do tenant A bloqueou o tenant B — {second.status_code} {second.text}"
    )

    after_other = await _count(db, case.model, other.id)
    assert after_other == before_other + 1, (
        f"{case.name}: o tenant B nao gravou a sua propria entidade — {before_other} -> {after_other}"
    )
