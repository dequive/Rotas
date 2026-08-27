from uuid import uuid4

import pytest

from app.core.auth import Principal
from app.core.errors import ApiError
from app.core.tenant import get_current_tenant_id


@pytest.mark.asyncio
async def test_tenant_dependency_returns_bound_tenant():
    tenant_id = uuid4()
    principal = Principal(
        subject="test:user",
        tenant_id=tenant_id,
        scope="dashboard",
    )

    assert await get_current_tenant_id(principal) == tenant_id


@pytest.mark.asyncio
async def test_tenant_dependency_rejects_platform_principal():
    principal = Principal(
        subject="test:platform",
        tenant_id=None,
        scope="platform",
    )

    with pytest.raises(ApiError) as captured:
        await get_current_tenant_id(principal)

    assert captured.value.code == "tenant_context_required"
    assert captured.value.status_code == 403
