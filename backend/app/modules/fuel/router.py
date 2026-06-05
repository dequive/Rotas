from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.fuel import schemas, service

router = APIRouter(prefix="/fuel", tags=["fuel"])


@router.get("")
async def list_fuel_logs(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_fuel_logs(
        db,
        principal.tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_fuel_log(
    payload: schemas.FuelLogCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="fuel.log.create",
        entity_type="fuel_log",
        payload=payload,
        handler=lambda: service.create_fuel_log(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
            driver_actor_id=principal.driver_id,
        ),
    )


@router.get("/stats")
async def get_fuel_stats(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    vehicle_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    return await service.get_fuel_stats(
        db,
        principal.tenant_id,
        vehicle_id=vehicle_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/anomalies")
async def list_anomalies(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_anomalies(db, principal.tenant_id, limit=limit, offset=offset)


@router.patch("/{fuel_log_id}/verify")
async def verify_fuel_log(
    fuel_log_id: UUID,
    payload: schemas.VerifyFuelLogRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.verify_fuel_log(
        db,
        principal.tenant_id,
        fuel_log_id,
        payload,
        user_id=principal.user_id,
    )
