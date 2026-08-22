from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import DriverPrincipal, get_driver_principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.modules.driver_app import service

router = APIRouter(prefix="/driver", tags=["driver-app"])

DriverPrincipalDependency = Annotated[DriverPrincipal, Depends(get_driver_principal)]
RlsSession = Annotated[AsyncSession, Depends(get_session)]


def _require_driver_id(principal: DriverPrincipal) -> UUID:
    if principal.driver_id is None:
        raise ApiError(
            "driver_required",
            "Driver identity is required.",
            status_code=403,
        )
    return principal.driver_id


@router.get("/bootstrap")
async def bootstrap_driver_app(
    principal: DriverPrincipalDependency,
    db: RlsSession,
):
    driver_id = _require_driver_id(principal)
    return await service.get_bootstrap_payload(
        db,
        tenant_id=principal.tenant_id,
        driver_id=driver_id,
        device_id=principal.device_id,
    )


@router.get("/checklist-templates")
async def list_checklist_templates(
    principal: DriverPrincipalDependency,
    db: RlsSession,
):
    _require_driver_id(principal)
    return await service.list_driver_checklist_templates(db, principal.tenant_id)


@router.get(
    "/vehicles",
    deprecated=True,
    responses={403: {"description": "Fleet selection is restricted to dispatch."}},
)
async def list_vehicles(
    principal: DriverPrincipalDependency,
):
    _require_driver_id(principal)
    raise ApiError(
        "driver_operation_forbidden",
        "Fleet vehicle selection is managed by dispatch.",
        status_code=403,
    )


@router.get("/active-trip")
async def get_active_trip(
    principal: DriverPrincipalDependency,
    db: RlsSession,
):
    driver_id = _require_driver_id(principal)
    return await service.get_active_driver_trip(
        db,
        principal.tenant_id,
        driver_id,
    )


@router.post(
    "/trips",
    deprecated=True,
    responses={403: {"description": "Trip creation is restricted to dispatch."}},
)
async def create_trip(
    principal: DriverPrincipalDependency,
):
    _require_driver_id(principal)
    raise ApiError(
        "driver_operation_forbidden",
        "Trip creation and assignment are managed by dispatch.",
        status_code=403,
    )
