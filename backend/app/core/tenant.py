from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.auth import Principal, get_current_principal


async def get_current_tenant_id(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> UUID:
    return principal.tenant_id
