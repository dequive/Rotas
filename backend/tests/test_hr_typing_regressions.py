from datetime import date
from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.modules.hr.schemas import EmployeeCreate
from app.modules.hr.service import create_employee, get_employee


@pytest.mark.asyncio
async def test_missing_employee_raises_typed_api_error(db, tenant_id):
    with pytest.raises(ApiError) as captured:
        await get_employee(tenant_id, uuid4(), db)

    assert captured.value.code == "EMPLOYEE_NOT_FOUND"
    assert captured.value.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_employee_nuit_raises_typed_api_error(db, tenant_id):
    payload = EmployeeCreate(
        first_name="Ana",
        last_name="Mabote",
        role="accountant",
        department="finance",
        base_salary=25_000,
        nif_nuit=f"NUIT-{uuid4().hex[:8]}",
        hire_date=date(2026, 1, 1),
    )
    await create_employee(tenant_id, payload, db)

    with pytest.raises(ApiError) as captured:
        await create_employee(tenant_id, payload, db)

    assert captured.value.code == "NUIT_EXISTS"
    assert captured.value.status_code == 400
