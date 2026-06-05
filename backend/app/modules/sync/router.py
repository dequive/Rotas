from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# AUTH-03 / D-13: Both endpoints require driver_app scope — manager tokens rejected with 403.
# get_driver_principal wraps get_current_principal and raises 403 if scope != "driver_app".
from app.core.auth import Principal, get_driver_principal
from app.core.deps import get_session
from app.modules.sync import schemas, service

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/batch")
async def process_batch(
    payload: schemas.SyncBatchRequest,
    principal: Annotated[Principal, Depends(get_driver_principal)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.process_batch(db, payload, principal)


@router.get("/bootstrap")
async def bootstrap(
    principal: Annotated[Principal, Depends(get_driver_principal)],
):
    return await service.bootstrap(principal)
