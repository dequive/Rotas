"""F7.4: prove the declared RBAC policy is the policy actually enforced over HTTP.

The expectation for every (mutation, role) pair is **derived from**
`app.core.rbac.ROLE_PERMISSIONS`, not copied into a table here. A hand-written
table drifts the moment someone grants a role a new permission: the table would
still pass while the API behaved differently. Deriving it means this module
fails exactly when the declared policy and the HTTP behaviour disagree.

What each pair asserts:

- role **lacks** the permission -> 403, and nothing is written. Not 404, not
  200 with an empty effect. A silent success is the dangerous outcome: the UI
  would navigate as if the write happened.
- role **holds** the permission -> the mutation succeeds.

The roles covered are every role in `ROLE_PERMISSIONS`, so a newly added role
is exercised automatically rather than being forgotten.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt as _jwt
import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.core.rbac import (
    ADMIN_USERS,
    BILLING_WRITE,
    DRIVERS_WRITE,
    FLEET_WRITE,
    FUEL_WRITE,
    ROLE_PERMISSIONS,
    TRIPS_DISPATCH,
    WORKSHOP_WRITE,
)
from app.database import import_all_models
from app.modules.checklists.models import ChecklistTemplate
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelTank
from app.modules.tenants.models import Tenant
from app.modules.trip_orders.models import TripOrder
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import MaintenanceRequest, SparePartInventory, WorkshopTool

import_all_models()

ROLES = sorted(ROLE_PERMISSIONS)


def _suffix() -> str:
    return uuid4().hex[:8]


def role_headers(tenant_id: UUID, user_id: UUID, role: str) -> dict[str, str]:
    """Mint a real dashboard JWT for `role`.

    The token is signed with the application key rather than using the test
    bypass token, so the request travels the same authorisation path a browser
    session would.
    """
    settings = get_settings()
    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{user_id}",
            "role": role,
            "scope": "dashboard",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


class RbacCase:
    def __init__(
        self,
        name: str,
        path: str,
        permission: str,
        model: Any,
        payload: Callable[[dict], dict],
        expected_status: tuple[int, ...] = (200, 201),
    ) -> None:
        self.name = name
        self.path = path
        self.permission = permission
        self.model = model
        self.payload = payload
        self.expected_status = expected_status

    def allows(self, role: str) -> bool:
        return self.permission in ROLE_PERMISSIONS[role]

    def __repr__(self) -> str:  # pragma: no cover - pytest id only
        return self.name


CASES: list[RbacCase] = [
    RbacCase(
        name="vehicles.create",
        path="/api/v1/vehicles",
        permission=FLEET_WRITE,
        model=Vehicle,
        payload=lambda ctx: {"plate": f"RB-{ctx['suffix'].upper()}", "category": "pesado"},
    ),
    RbacCase(
        name="drivers.create",
        path="/api/v1/drivers",
        permission=DRIVERS_WRITE,
        model=Driver,
        payload=lambda ctx: {"full_name": f"Motorista {ctx['suffix']}"},
    ),
    RbacCase(
        name="users.create",
        path="/api/v1/users",
        permission=ADMIN_USERS,
        model=User,
        payload=lambda ctx: {
            "email": f"rbac-{ctx['suffix']}@test.local",
            "password": "Palavra-Passe-Forte-1",
            "full_name": f"Utilizador {ctx['suffix']}",
            "role": "viewer",
        },
    ),
    RbacCase(
        name="checklists.template.create",
        path="/api/v1/checklist-templates",
        permission=FLEET_WRITE,
        model=ChecklistTemplate,
        payload=lambda ctx: {
            "name": f"Modelo {ctx['suffix']}",
            "type": "pre_trip",
            "items": [{"id": "pneus", "label": "Pneus", "blocking": True}],
        },
    ),
    RbacCase(
        name="fuel_operations.tank.create",
        path="/api/v1/fuel-operations/tanks",
        permission=FUEL_WRITE,
        model=FuelTank,
        payload=lambda ctx: {
            "code": f"RB-{ctx['suffix'].upper()}",
            "name": f"Tanque {ctx['suffix']}",
            "capacity_liters": 10000,
        },
    ),
    RbacCase(
        name="workshop.spare_part.create",
        path="/api/v1/workshop/spare-parts",
        permission=WORKSHOP_WRITE,
        model=SparePartInventory,
        payload=lambda ctx: {
            "sku": f"RB-{ctx['suffix'].upper()}",
            "name": f"Peca {ctx['suffix']}",
        },
    ),
    RbacCase(
        name="workshop.tool.create",
        path="/api/v1/workshop/tools",
        permission=WORKSHOP_WRITE,
        model=WorkshopTool,
        payload=lambda ctx: {
            "code": f"RB-{ctx['suffix'].upper()}",
            "name": f"Ferramenta {ctx['suffix']}",
        },
    ),
    RbacCase(
        name="workshop.maintenance_request.create",
        path="/api/v1/workshop/maintenance-requests",
        permission=WORKSHOP_WRITE,
        model=MaintenanceRequest,
        payload=lambda ctx: {
            "vehicle_id": str(ctx["vehicle_id"]),
            "description": f"Revisao {ctx['suffix']}",
        },
    ),
    RbacCase(
        name="contracts.create",
        path="/api/v1/contracts/",
        permission=BILLING_WRITE,
        model=Contract,
        payload=lambda ctx: {
            "client_name": f"Cliente {ctx['suffix']}",
            "contract_reference": f"RB-{ctx['suffix'].upper()}",
        },
    ),
    RbacCase(
        name="trip_orders.create",
        path="/api/v1/trip-orders",
        permission=TRIPS_DISPATCH,
        model=TripOrder,
        payload=lambda ctx: {
            "origin": "Maputo",
            "destination": "Beira",
            "requested_pickup_date": ctx["pickup_date"],
        },
    ),
]


@pytest.fixture
async def rbac_context(db, tenant_id) -> dict:
    """One user per role, plus the vehicle the workshop case needs."""
    suffix = _suffix()

    # One user per role plus the users the cases create would otherwise blow past
    # the default plan ceiling, and a plan limit answers 403 exactly like an RBAC
    # denial does — see test_plan_limit_is_not_mistaken_for_an_rbac_denial.
    tenant = await db.get(Tenant, tenant_id)
    tenant.max_users = 100
    await db.flush()

    users: dict[str, UUID] = {}
    for role in ROLES:
        user = User(
            tenant_id=tenant_id,
            email=f"rbac-{role}-{suffix}@test.local",
            password_hash="$argon2id$test",
            full_name=f"Utilizador {role}",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        users[role] = user.id

    vehicle = Vehicle(tenant_id=tenant_id, plate=f"RBC-{suffix.upper()}", category="pesado")
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)

    return {
        "suffix": suffix,
        "users": users,
        "vehicle_id": vehicle.id,
        "pickup_date": (date.today() + timedelta(days=3)).isoformat(),
    }


async def _count(db, model: Any, tenant_id: UUID) -> int:
    return await db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id))


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_http_enforcement_matches_declared_role_policy(
    case: RbacCase, role: str, async_client, db, tenant_id, rbac_context
) -> None:
    headers = role_headers(tenant_id, rbac_context["users"][role], role)
    body = case.payload({**rbac_context, "suffix": _suffix()})

    before = await _count(db, case.model, tenant_id)
    response = await async_client.post(case.path, json=body, headers=headers)
    after = await _count(db, case.model, tenant_id)

    if case.allows(role):
        assert response.status_code in case.expected_status, (
            f"{case.name}: {role} tem {case.permission} na politica mas recebeu "
            f"{response.status_code} — {response.text}"
        )
        assert after == before + 1, f"{case.name}: {role} foi autorizado mas nada foi gravado"
    else:
        assert response.status_code == 403, (
            f"{case.name}: {role} nao tem {case.permission} mas recebeu "
            f"{response.status_code}. Um 2xx aqui faria a UI navegar como se tivesse "
            f"gravado; um 404 esconderia a causa do utilizador. — {response.text}"
        )
        assert response.json()["error"]["code"] == "forbidden", (
            f"{case.name}: {role} recebeu 403 por outro motivo que nao RBAC — {response.text}"
        )
        assert after == before, (
            f"{case.name}: {role} recebeu 403 mas a escrita aconteceu na mesma ({before} -> {after})"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
async def test_unauthenticated_request_is_rejected(case: RbacCase, async_client, db, tenant_id, rbac_context) -> None:
    """No token at all must be 401/403, never a write."""
    body = case.payload({**rbac_context, "suffix": _suffix()})
    before = await _count(db, case.model, tenant_id)

    response = await async_client.post(case.path, json=body, headers={"X-Tenant-Id": str(tenant_id)})

    assert response.status_code in (401, 403), (
        f"{case.name}: pedido sem token devolveu {response.status_code} — {response.text}"
    )
    assert await _count(db, case.model, tenant_id) == before, f"{case.name}: pedido sem token escreveu na base"


def test_every_declared_role_is_covered() -> None:
    """Guard: a role added to ROLE_PERMISSIONS must not silently escape the matrix."""
    assert set(ROLES) == set(ROLE_PERMISSIONS), "A matriz RBAC deixou de cobrir todos os papeis declarados."
    assert len(ROLES) >= 6, f"Esperavam-se pelo menos 6 papeis, encontrados {ROLES}"


async def test_plan_limit_is_not_mistaken_for_an_rbac_denial(async_client, db, tenant_id, rbac_context) -> None:
    """A tenant plan ceiling answers 403, the same status as a permission denial.

    Both are legitimate refusals, but they are different problems: one is fixed
    by granting a role, the other by upgrading a plan. Only the error code tells
    them apart, so the UI must branch on the code and not on the status. This
    test pins that distinction so a future refactor cannot collapse the two.
    """
    tenant = await db.get(Tenant, tenant_id)
    tenant.max_users = 1
    await db.commit()

    owner_headers = role_headers(tenant_id, rbac_context["users"]["owner"], "owner")
    response = await async_client.post(
        "/api/v1/users",
        json={
            "email": f"limite-{_suffix()}@test.local",
            "password": "Palavra-Passe-Forte-1",
            "full_name": "Utilizador Acima do Limite",
            "role": "viewer",
        },
        headers=owner_headers,
    )

    assert response.status_code == 403, response.text
    body = response.json()["error"]
    assert body["code"] == "plan_limit_reached", (
        f"o limite de plano deixou de ser distinguivel de uma negacao RBAC: {body}"
    )
    assert body["details"]["dimension"] == "users"
