import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import DRIVERS_PAIRING, DRIVERS_READ, DRIVERS_WRITE, require_permission
from app.modules.availability import service as availability_service
from app.modules.drivers import schemas, service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("")
async def list_drivers(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"tenant:{principal.tenant_id}:drivers:status={status}:search={search}:limit={limit}:offset={offset}"
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    result = await service.list_drivers(
        db,
        principal.tenant_id,
        status_filter=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    if redis is not None:
        await redis.setex(cache_key, 120, json.dumps(result, default=str))
    return result


@router.post("")
async def create_driver(
    request: Request,
    payload: schemas.DriverCreate,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="drivers.create",
        entity_type="driver",
        payload=payload,
        handler=lambda: service.create_driver(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
            redis=redis,
        ),
    )
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.get("/{driver_id}")
async def get_driver(
    driver_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_driver(db, principal.tenant_id, driver_id)


@router.get("/{driver_id}/scorecard")
async def get_driver_scorecard(
    driver_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    days: int = Query(30, ge=7, le=90),
):
    """D-11: Driver scorecard — composite 0-100 score for rolling window.

    Accessible to dashboard roles only (owner/admin/manager/viewer).
    Driver tokens are rejected by require_permission at the dependency level.
    """
    return await service.get_driver_scorecard(db, principal.tenant_id, driver_id, days=days)


@router.get("/{driver_id}/history")
async def list_driver_history(
    driver_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_driver_history(
        db,
        principal.tenant_id,
        driver_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{driver_id}/availability")
async def get_driver_availability(
    driver_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    exclude_trip_id: UUID | None = None,
):
    return await availability_service.driver_availability_summary(
        db,
        principal.tenant_id,
        driver_id,
        exclude_trip_id=exclude_trip_id,
    )


@router.patch("/{driver_id}")
async def patch_driver(
    request: Request,
    driver_id: UUID,
    payload: schemas.DriverPatch,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_driver(
        db,
        principal.tenant_id,
        driver_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{driver_id}/pairing-code")
async def issue_driver_pairing_code(
    request: Request,
    driver_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_PAIRING))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="drivers.pairing_code.issue",
        entity_type="driver",
        payload={"driver_id": driver_id},
        handler=lambda: service.issue_pairing_code(
            db,
            principal.tenant_id,
            driver_id,
            actor_id=principal.user_id,
        ),
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{driver_id}/documents/{document_type}/renew")
async def renew_driver_document(
    request: Request,
    driver_id: UUID,
    document_type: str,
    payload: schemas.DriverDocumentRenewalRequest,
    principal: Annotated[Principal, Depends(require_permission(DRIVERS_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="drivers.document.renew",
        entity_type="driver",
        payload={"driver_id": driver_id, "document_type": document_type, **payload.model_dump()},
        handler=lambda: service.renew_driver_document(
            db,
            principal.tenant_id,
            driver_id,
            document_type,
            payload,
            actor_id=principal.user_id,
        ),
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res
