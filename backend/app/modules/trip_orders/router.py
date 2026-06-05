from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.trip_orders import schemas, service

router = APIRouter(prefix="/trip-orders", tags=["trip-orders"])


@router.get("")
async def list_trip_orders(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_trip_orders(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_trip_order(
    payload: schemas.TripOrderCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trip_orders.create",
        entity_type="trip_order",
        payload=payload,
        handler=lambda: service.create_trip_order(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/{order_id}")
async def get_trip_order(
    order_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_trip_order(db, principal.tenant_id, order_id)


@router.post("/{order_id}/confirm")
async def confirm_trip_order(
    order_id: UUID,
    payload: schemas.TripOrderConfirmRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trip_orders.confirm",
        entity_type="trip_order",
        payload={"order_id": order_id, **payload.model_dump()},
        handler=lambda: service.confirm_trip_order(
            db,
            principal.tenant_id,
            order_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{order_id}/assign")
async def assign_trip_order(
    order_id: UUID,
    payload: schemas.TripOrderAssignRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trip_orders.assign",
        entity_type="trip_order",
        payload={"order_id": order_id, **payload.model_dump()},
        handler=lambda: service.assign_trip_order(
            db,
            principal.tenant_id,
            order_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{order_id}/cancel")
async def cancel_trip_order(
    order_id: UUID,
    payload: schemas.TripOrderCancelRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trip_orders.cancel",
        entity_type="trip_order",
        payload={"order_id": order_id, **payload.model_dump()},
        handler=lambda: service.cancel_trip_order(
            db,
            principal.tenant_id,
            order_id,
            payload,
            actor_id=principal.user_id,
        ),
    )
