from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import ADMIN_USERS, TRIPS_DISPATCH, TRIPS_READ, require_permission
from app.modules.trip_orders import schemas, service
from app.modules.trip_orders.schemas import DispatchClearanceRejectRequest

router = APIRouter(prefix="/trip-orders", tags=["trip-orders"])


@router.get("")
async def list_trip_orders(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
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
    request: Request,
    payload: schemas.TripOrderCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.get("/{order_id}")
async def get_trip_order(
    order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_trip_order(db, principal.tenant_id, order_id)


@router.post("/{order_id}/confirm")
async def confirm_trip_order(
    request: Request,
    order_id: UUID,
    payload: schemas.TripOrderConfirmRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.post("/{order_id}/assign")
async def assign_trip_order(
    request: Request,
    order_id: UUID,
    payload: schemas.TripOrderAssignRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.post("/{order_id}/cancel")
async def cancel_trip_order(
    request: Request,
    order_id: UUID,
    payload: schemas.TripOrderCancelRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.patch("/{order_id}/reject", summary="Reject dispatch clearance (SM-04)")
async def reject_dispatch_endpoint(
    order_id: UUID,
    body: DispatchClearanceRejectRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    request: Request,
):
    from app.modules.trip_orders.service import reject_dispatch_clearance

    order = await reject_dispatch_clearance(
        db,
        order_id=order_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        rejection_reason=body.rejection_reason,
    )
    await db.commit()
    await db.refresh(order)
    # Enqueue notification (non-blocking)
    if request and hasattr(request.app.state, "arq_redis") and request.app.state.arq_redis:
        await request.app.state.arq_redis.enqueue_job(
            "task_notify_dispatch_rejected",
            order_id=str(order.id),
            tenant_id=str(principal.tenant_id),
        )
    redis = getattr(request.app.state, "redis", None) if request else None
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return order
