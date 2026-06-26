import uuid

import pytest

from app.core.errors import ApiError
from app.core.tenant import validate_active_tenant
from app.modules.tenants.models import Tenant


@pytest.mark.asyncio
async def test_validate_active_tenant_success(db):
    # Create active tenant
    tenant = Tenant(
        name="Active Tenant Test", slug=f"active-tenant-{uuid.uuid4().hex[:6]}", is_active=True
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    validated = await validate_active_tenant(tenant.id)
    assert validated.id == tenant.id
    assert validated.name == "Active Tenant Test"


@pytest.mark.asyncio
async def test_validate_active_tenant_inactive(db):
    # Create inactive tenant
    tenant = Tenant(
        name="Inactive Tenant Test", slug=f"inactive-tenant-{uuid.uuid4().hex[:6]}", is_active=False
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    with pytest.raises(ApiError) as exc_info:
        await validate_active_tenant(tenant.id)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "tenant_inactive"


@pytest.mark.asyncio
async def test_validate_active_tenant_not_found(db):
    random_id = uuid.uuid4()
    with pytest.raises(ApiError) as exc_info:
        await validate_active_tenant(random_id)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "tenant_inactive"
