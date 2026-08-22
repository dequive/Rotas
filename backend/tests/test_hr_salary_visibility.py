"""Payroll, bank details and advances require HR_SALARY_VIEW, not merely HR_READ.

`rbac.py` states the intent plainly in the viewer block — "read-only ERP, no
salary visibility" — and grants `hr.salary.view` only to admin and owner. The
HR endpoints did not honour it: every salary surface was gated by `HR_READ`,
which viewer and manager both hold.

That exposed, to any viewer of the tenant:

- `GET /hr/payroll` — gross and net salary per employee
- `GET /hr/payroll/export-ps2` — a CSV of name, bank account (NIB) and net pay
- `GET /hr/advances` — advance amounts per employee
- `GET /hr/employees` — `base_salary` and `bank_account_nib`

The employee directory itself stays open to `HR_READ`: a dispatcher needs to
know who works here. Pay and bank details are not part of "who works here", so
those two fields are redacted rather than the whole list being withheld.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

from app.core.rbac import HR_READ, HR_SALARY_VIEW, ROLE_PERMISSIONS
from app.database import import_all_models
from app.modules.hr.models import Employee
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from tests.test_rbac_matrix import role_headers

import_all_models()

# Roles that can read HR but must not see pay.
HR_READERS_WITHOUT_SALARY = sorted(
    role
    for role, perms in ROLE_PERMISSIONS.items()
    if HR_READ in perms and HR_SALARY_VIEW not in perms
)
HR_SALARY_ROLES = sorted(
    role for role, perms in ROLE_PERMISSIONS.items() if HR_SALARY_VIEW in perms
)

SALARY_ENDPOINTS = [
    "/api/v1/hr/payroll?month=1&year=2026",
    "/api/v1/hr/advances",
    "/api/v1/hr/payroll/export-ps2?month=1&year=2026",
]


@pytest.fixture
async def hr_context(db, tenant_id) -> dict:
    suffix = uuid4().hex[:8]

    tenant = await db.get(Tenant, tenant_id)
    tenant.max_users = 100
    await db.flush()

    users: dict[str, UUID] = {}
    for role in sorted(ROLE_PERMISSIONS):
        user = User(
            tenant_id=tenant_id,
            email=f"hr-{role}-{suffix}@test.local",
            password_hash="$argon2id$test",
            full_name=f"Utilizador {role}",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        users[role] = user.id

    employee = Employee(
        tenant_id=tenant_id,
        first_name="Aurora",
        last_name=f"Machava {suffix}",
        role="Motorista de pesados",
        department="Operacoes",
        base_salary=48000.0,
        bank_account_nib="000300001234567890123",
        hire_date=date(2025, 3, 1),
        status="active",
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    return {"users": users, "employee_id": employee.id}


def test_salary_readers_are_a_strict_subset() -> None:
    """Sanity: the split this module tests must actually exist in the policy."""
    assert HR_READERS_WITHOUT_SALARY, "nenhum papel le RH sem ver salarios — teste sem sentido"
    assert HR_SALARY_ROLES, "nenhum papel tem hr.salary.view"
    assert set(HR_READERS_WITHOUT_SALARY).isdisjoint(HR_SALARY_ROLES)


@pytest.mark.parametrize("path", SALARY_ENDPOINTS)
@pytest.mark.parametrize("role", HR_READERS_WITHOUT_SALARY)
async def test_hr_reader_without_salary_permission_is_refused(
    role: str, path: str, async_client, tenant_id, hr_context
) -> None:
    response = await async_client.get(
        path, headers=role_headers(tenant_id, hr_context["users"][role], role)
    )

    assert response.status_code == 403, (
        f"{role} leu {path} com {response.status_code}. Este papel nao tem "
        f"hr.salary.view — {response.text[:300]}"
    )
    assert response.json()["error"]["code"] == "forbidden", response.text


@pytest.mark.parametrize("path", SALARY_ENDPOINTS)
@pytest.mark.parametrize("role", HR_SALARY_ROLES)
async def test_salary_permission_still_grants_access(
    role: str, path: str, async_client, tenant_id, hr_context
) -> None:
    response = await async_client.get(
        path, headers=role_headers(tenant_id, hr_context["users"][role], role)
    )

    assert response.status_code != 403, (
        f"{role} tem hr.salary.view mas foi recusado em {path} — {response.text[:300]}"
    )


@pytest.mark.parametrize("role", HR_READERS_WITHOUT_SALARY)
async def test_employee_directory_stays_readable_but_redacted(
    role: str, async_client, tenant_id, hr_context
) -> None:
    """The list is still useful without leaking pay or bank details."""
    response = await async_client.get(
        "/api/v1/hr/employees", headers=role_headers(tenant_id, hr_context["users"][role], role)
    )

    assert response.status_code == 200, f"{role}: {response.text[:300]}"
    employees = response.json()
    assert employees, "a directoria de empregados ficou vazia para quem tem hr.read"

    for employee in employees:
        assert employee["base_salary"] is None, (
            f"{role} viu base_salary na directoria de empregados: {employee}"
        )
        assert employee["bank_account_nib"] is None, (
            f"{role} viu bank_account_nib na directoria de empregados: {employee}"
        )
        # The directory must still identify people, otherwise redaction went too far.
        assert employee["first_name"], "a redaccao apagou a identificacao do empregado"


@pytest.mark.parametrize("role", HR_SALARY_ROLES)
async def test_salary_roles_see_the_unredacted_directory(
    role: str, async_client, tenant_id, hr_context
) -> None:
    response = await async_client.get(
        "/api/v1/hr/employees", headers=role_headers(tenant_id, hr_context["users"][role], role)
    )

    assert response.status_code == 200, f"{role}: {response.text[:300]}"
    seeded = [e for e in response.json() if e["id"] == str(hr_context["employee_id"])]
    assert seeded, "o empregado semeado nao apareceu na directoria"
    assert seeded[0]["base_salary"] == 48000.0
    assert seeded[0]["bank_account_nib"] == "000300001234567890123"
