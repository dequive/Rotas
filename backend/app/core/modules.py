"""Product module access control for ROTAS multi-product features (TMS / Oficina Auto).

Naming convention: tms | oficina

Usage:
    from app.core.modules import require_module, MODULE_OFICINA, MODULE_TMS

    @router.get("/quotes")
    async def list_quotes(
        principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
        _: Annotated[None, Depends(require_module(MODULE_OFICINA))],
        ...
    ):
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.modules.tenants.models import Tenant

MODULE_TMS = "tms"
MODULE_OFICINA = "oficina"

ALLOWED_PRODUCT_MODULES = {MODULE_TMS, MODULE_OFICINA}


def require_module(*modules: str) -> Callable:
    """FastAPI dependency factory.

    Checks if the principal's tenant has AT LEAST ONE of the requested product_modules (OR semantics).
    If the tenant does not have any of the requested modules active, raises 403 Forbidden.
    """
    required_set = set(modules)

    async def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
        db: Annotated[AsyncSession, Depends(get_session)],
    ) -> None:
        tenant = await db.get(Tenant, principal.tenant_id)
        if not tenant:
            raise ApiError(
                "tenant_not_found",
                "Tenant not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        active_modules = set(tenant.product_modules or ["tms"])
        if not active_modules.intersection(required_set):
            raise ApiError(
                "module_not_subscribed",
                "This functionality is not enabled for your subscription.",
                status_code=status.HTTP_403_FORBIDDEN,
                details={
                    "required_modules": sorted(required_set),
                    "active_modules": sorted(active_modules),
                },
            )

    return dependency
