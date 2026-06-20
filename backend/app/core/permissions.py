# DEPRECATED: This module is superseded by `app.core.rbac`.
# All router files now use `require_permission()` with named permission constants
# from `app.core.rbac`. This file is retained only for backward compatibility
# during the migration period and will be removed in a future cleanup phase.
# Do NOT add new imports from this module in router files.
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, status

from app.core.auth import Principal, get_current_principal
from app.core.errors import ApiError

OWNER = "owner"
ADMIN = "admin"
MANAGER = "manager"
VIEWER = "viewer"
MECHANIC = "mechanic"
DASHBOARD_ROLES = {OWNER, ADMIN, MANAGER, VIEWER, MECHANIC}
WRITE_ROLES = {OWNER, ADMIN, MANAGER}
ADMIN_ROLES = {OWNER, ADMIN}
# Workshop write: mechanic + standard write roles
WORKSHOP_WRITE_ROLES = {OWNER, ADMIN, MANAGER, MECHANIC}
# Workshop read: mechanic + standard dashboard roles
WORKSHOP_READ_ROLES = {OWNER, ADMIN, MANAGER, VIEWER, MECHANIC}


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
