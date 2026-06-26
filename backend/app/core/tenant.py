from typing import Annotated
from uuid import UUID

from fastapi import Depends, status
from sqlalchemy import select

from app.core.auth import Principal, get_current_principal
from app.core.errors import ApiError
from app.database import AsyncSessionLocal
from app.modules.tenants.models import Tenant


async def get_current_tenant_id(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> UUID:
    return principal.tenant_id


async def validate_active_tenant(tenant_id: UUID) -> Tenant:
    """Raise ApiError if tenant is not active."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise ApiError(
                "tenant_inactive",
                "Tenant not found or inactive.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return tenant
