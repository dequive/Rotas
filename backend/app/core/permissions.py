from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, status

from app.core.auth import Principal, get_current_principal
from app.core.errors import ApiError

OWNER = "owner"
ADMIN = "admin"
MANAGER = "manager"
VIEWER = "viewer"
DASHBOARD_ROLES = {OWNER, ADMIN, MANAGER, VIEWER}
WRITE_ROLES = {OWNER, ADMIN, MANAGER}
ADMIN_ROLES = {OWNER, ADMIN}


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if principal.role not in allowed:
            raise ApiError(
                "forbidden",
                "Insufficient permissions for this operation.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={"required_roles": sorted(allowed)},
            )
        return principal

    return dependency
