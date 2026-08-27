"""F7.4: RBAC over state transitions, where the wrong role is worse than on a create.

Creating an entity with the wrong role produces a spurious row someone can
delete. *Transitioning* one changes a fact the business already acted on: an
invoice becomes issued and enters the AT sequential series, a trip becomes
closed and billable, a work order becomes closed and invoiced, a stock
adjustment becomes approved and rewrites the fuel balance.

So the assertion here is different from `test_rbac_matrix.py`. A denied
transition must leave the entity's **state** exactly as it was — checking that
no new row appeared would prove nothing, because a transition creates no rows.

For roles that *do* hold the permission the assertion is deliberately narrow:
the response must not be an RBAC refusal. A business rule may still reject the
transition (wrong source state, missing delivery proof) and that is correct
behaviour — it is not what this module is measuring. Seeding every entity into
a perfectly transitionable state would make these tests brittle against domain
rules that are already covered elsewhere.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.rbac import (
    BILLING_ISSUE,
    BILLING_VOID,
    FUEL_APPROVE,
    ROLE_PERMISSIONS,
    TRIPS_CLOSE,
    WORKSHOP_CLOSE,
)
from app.database import import_all_models
from app.modules.billing.models import BillingDocument, BillingItem, ClientPayment
from app.modules.clients.models import Client
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelStockCount, FuelTank
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder
from tests.test_rbac_matrix import role_headers

import_all_models()

ROLES = sorted(ROLE_PERMISSIONS)


def _suffix() -> str:
    return uuid4().hex[:8]


class TransitionCase:
    def __init__(
        self,
        name: str,
        path: Callable[[dict], str],
        permission: str,
        payload: dict,
        read_state: Callable[[Any, dict], Awaitable[str | None]],
    ) -> None:
        self.name = name
        self._path = path
        self.permission = permission
        self.payload = payload
        self._read_state = read_state

    def path(self, ctx: dict) -> str:
        return self._path(ctx)

    async def state(self, db, ctx: dict) -> str | None:
        return await self._read_state(db, ctx)

    def allows(self, role: str) -> bool:
        return self.permission in ROLE_PERMISSIONS[role]

    def __repr__(self) -> str:  # pragma: no cover - pytest id only
        return self.name


async def _status_of(db, model: Any, entity_id: UUID) -> str | None:
    db.expire_all()
    return await db.scalar(select(model.status).where(model.id == entity_id))


CASES: list[TransitionCase] = [
    TransitionCase(
        name="billing.document.issue",
        path=lambda ctx: f"/api/v1/billing/documents/{ctx['document_id']}/issue",
        permission=BILLING_ISSUE,
        payload={},
        read_state=lambda db, ctx: _status_of(db, BillingDocument, ctx["document_id"]),
    ),
    TransitionCase(
        name="billing.payment.void",
        path=lambda ctx: f"/api/v1/billing/payments/{ctx['payment_id']}/void",
        permission=BILLING_VOID,
        payload={"void_reason": "Transferencia devolvida pelo banco"},
        read_state=lambda db, ctx: _status_of(db, ClientPayment, ctx["payment_id"]),
    ),
    TransitionCase(
        name="trips.complete",
        path=lambda ctx: f"/api/v1/trips/{ctx['trip_id']}/complete",
        permission=TRIPS_CLOSE,
        payload={"km_end": 1200, "recipient_name": "Armazem Central"},
        read_state=lambda db, ctx: _status_of(db, Trip, ctx["trip_id"]),
    ),
    TransitionCase(
        name="workshop.work_order.close",
        path=lambda ctx: f"/api/v1/workshop/work-orders/{ctx['work_order_id']}/close",
        permission=WORKSHOP_CLOSE,
        payload={"actual_cost": 4500.0, "notes": "Servico concluido e verificado"},
        read_state=lambda db, ctx: _status_of(db, WorkOrder, ctx["work_order_id"]),
    ),
    TransitionCase(
        name="fuel.stock_adjustment.approve",
        path=lambda ctx: f"/api/v1/fuel-operations/stock-counts/{ctx['stock_count_id']}/approve-adjustment",
        permission=FUEL_APPROVE,
        payload={"notes": "Diferenca confirmada na contagem fisica"},
        read_state=lambda db, ctx: db.scalar(
            select(FuelStockCount.adjustment_status).where(FuelStockCount.id == ctx["stock_count_id"])
        ),
    ),
]


@pytest.fixture
async def transition_context(db, tenant_id) -> dict:
    """Seed one entity per transition, plus a user for every role."""
    suffix = _suffix()
    now = datetime.now(UTC)

    tenant = await db.get(Tenant, tenant_id)
    tenant.max_users = 100
    await db.flush()

    users: dict[str, UUID] = {}
    for role in ROLES:
        user = User(
            tenant_id=tenant_id,
            email=f"trans-{role}-{suffix}@test.local",
            password_hash="$argon2id$test",
            full_name=f"Utilizador {role}",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        users[role] = user.id

    client = Client(
        tenant_id=tenant_id,
        trading_name=f"Cliente {suffix}",
        nuit=f"4005{uuid4().int % 100000:05d}",
    )
    contract = Contract(
        tenant_id=tenant_id,
        client_name=f"Cliente {suffix}",
        contract_reference=f"TR-{suffix.upper()}",
        status="active",
    )
    vehicle = Vehicle(tenant_id=tenant_id, plate=f"TR-{suffix.upper()}", status="active")
    driver = Driver(tenant_id=tenant_id, full_name=f"Motorista {suffix}", status="active")
    tank = FuelTank(
        tenant_id=tenant_id,
        code=f"TQ-{suffix.upper()}",
        name=f"Tanque {suffix}",
        capacity_liters=Decimal("10000.00"),
        current_stock_liters=Decimal("5000.00"),
    )
    db.add_all([client, contract, vehicle, driver, tank])
    await db.flush()

    document = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
        client_nuit="400123456",
    )
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id,
        origin="Maputo",
        destination="Beira",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add_all([document, trip])
    await db.flush()

    db.add(
        BillingItem(
            tenant_id=tenant_id,
            contract_id=contract.id,
            billing_document_id=document.id,
            trip_id=trip.id,
            origin="Maputo",
            destination="Beira",
            amount=Decimal("1000.00"),
            iva_rate=Decimal("0.1700"),
            iva_amount=Decimal("170.00"),
            delivered_at=now,
            status="pending",
        )
    )

    payment = ClientPayment(
        tenant_id=tenant_id,
        client_id=client.id,
        amount=Decimal("1000.00"),
        currency="MZN",
        value_date=now,
        payment_method="bank_transfer",
        status="active",
    )
    work_order = WorkOrder(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        work_order_number=f"OS-{suffix.upper()}",
        planned_work="Revisao de travoes e mudanca de oleo",
        status="completed",
    )
    stock_count = FuelStockCount(
        tenant_id=tenant_id,
        tank_id=tank.id,
        theoretical_liters=Decimal("5000.00"),
        measured_liters=Decimal("4800.00"),
        variance_liters=Decimal("-200.00"),
        counted_at=now,
        adjustment_status="pending",
    )
    db.add_all([payment, work_order, stock_count])
    await db.commit()

    return {
        "suffix": suffix,
        "users": users,
        "document_id": document.id,
        "payment_id": payment.id,
        "trip_id": trip.id,
        "work_order_id": work_order.id,
        "stock_count_id": stock_count.id,
    }


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_transition_is_gated_by_declared_permission(
    case: TransitionCase, role: str, async_client, db, tenant_id, transition_context
) -> None:
    headers = role_headers(tenant_id, transition_context["users"][role], role)
    state_before = await case.state(db, transition_context)

    response = await async_client.post(case.path(transition_context), json=case.payload, headers=headers)

    if case.allows(role):
        # A business rule may still refuse; an RBAC refusal may not.
        assert response.status_code != 403 or response.json()["error"]["code"] != "forbidden", (
            f"{case.name}: {role} tem {case.permission} na politica mas foi recusado pelo RBAC — {response.text}"
        )
    else:
        assert response.status_code == 403, (
            f"{case.name}: {role} nao tem {case.permission} mas recebeu {response.status_code} — {response.text}"
        )
        assert response.json()["error"]["code"] == "forbidden", response.text

        state_after = await case.state(db, transition_context)
        assert state_after == state_before, (
            f"{case.name}: {role} recebeu 403 mas o estado mudou na mesma "
            f"({state_before!r} -> {state_after!r}). Uma transicao recusada tem de "
            f"deixar a entidade exactamente como estava."
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_transition_without_token_changes_nothing(
    case: TransitionCase, async_client, db, tenant_id, transition_context
) -> None:
    state_before = await case.state(db, transition_context)

    response = await async_client.post(
        case.path(transition_context),
        json=case.payload,
        headers={"X-Tenant-Id": str(tenant_id)},
    )

    assert response.status_code in (401, 403), f"{case.name}: {response.text}"
    assert await case.state(db, transition_context) == state_before, (
        f"{case.name}: pedido sem token alterou o estado da entidade"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_transition_is_refused_across_tenants(
    case: TransitionCase, async_client, db, tenant_id, transition_context
) -> None:
    """An owner of tenant B must not transition tenant A's entity.

    The strongest role in the system is still powerless outside its own tenant,
    and the entity must come out untouched.
    """
    suffix = _suffix()
    other = Tenant(name=f"Tenant Trans B {suffix}", slug=f"trans-b-{suffix}")
    db.add(other)
    await db.flush()
    intruder = User(
        tenant_id=other.id,
        email=f"intruso-{suffix}@test.local",
        password_hash="$argon2id$test",
        full_name="Owner do outro tenant",
        role="owner",
        is_active=True,
    )
    db.add(intruder)
    await db.flush()
    # Capture the ids before committing: `case.state` expires the session, and
    # reading `other.id` afterwards would trigger a lazy refresh outside the
    # async context (MissingGreenlet).
    other_tenant_id, intruder_id = other.id, intruder.id
    await db.commit()

    state_before = await case.state(db, transition_context)

    response = await async_client.post(
        case.path(transition_context),
        json=case.payload,
        headers=role_headers(other_tenant_id, intruder_id, "owner"),
    )

    assert response.status_code in (403, 404), (
        f"{case.name}: owner do tenant B recebeu {response.status_code} sobre uma "
        f"entidade do tenant A — {response.text}"
    )
    assert await case.state(db, transition_context) == state_before, (
        f"{case.name}: o tenant B alterou o estado de uma entidade do tenant A"
    )
