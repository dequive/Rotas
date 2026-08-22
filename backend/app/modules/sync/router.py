from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# AUTH-03 / D-13: Both endpoints require driver_app scope — manager tokens rejected with 403.
# get_driver_principal wraps get_current_principal and raises 403 if scope != "driver_app".
from app.core.auth import DriverPrincipal, get_driver_principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.modules.sync import schemas, service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/batch", response_model=schemas.SyncBatchResponse)
async def process_batch(
    payload: schemas.SyncBatchRequest,
    principal: Annotated[DriverPrincipal, Depends(get_driver_principal)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    if principal.scope == "driver_app" and payload.device_id != principal.device_id:
        raise ApiError(
            "driver_device_mismatch",
            "Sync device does not match the authenticated driver device.",
            status_code=403,
        )
    return await service.process_batch(db, payload, principal)


@router.get("/bootstrap", response_model=schemas.SyncBootstrapResponse)
async def bootstrap(
    principal: Annotated[DriverPrincipal, Depends(get_driver_principal)],
):
    return await service.bootstrap(principal)
