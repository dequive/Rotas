import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.availability import service as availability_service
from app.modules.vehicles import insurance_service, schemas, service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("")
async def list_vehicles(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"tenant:{principal.tenant_id}:vehicles:status={status}:search={search}:limit={limit}:offset={offset}"
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    result = await service.list_vehicles(
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
async def create_vehicle(
    request: Request,
    payload: schemas.VehicleCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="vehicles.create",
        entity_type="vehicle",
        payload=payload,
        handler=lambda: service.create_vehicle(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
            redis=redis,
        ),
    )
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.get("/{vehicle_id}")
async def get_vehicle(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_vehicle(db, principal.tenant_id, vehicle_id)


@router.get("/{vehicle_id}/history")
async def list_vehicle_history(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    # Cursor-based pagination params (new — Plan 13.5-03)
    cursor: str | None = Query(None),
    types: str | None = Query(None),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    """Vehicle history endpoint supporting both offset pagination (legacy) and cursor pagination.

    When `cursor`, `types`, `from`, or `to` query params are provided, the response uses the
    cursor-paginated format: {"events": [...], "next_cursor": str|null, "total_count": int}.

    Without those params, the legacy offset format is used:
    {"vehicle": {...}, "items": [...], "limit": ..., "offset": ..., "returned": ...}.
    """
    if cursor is not None or types is not None or from_date is not None or to_date is not None:
        parsed_types = [t.strip() for t in types.split(",")] if types else None
        from datetime import datetime as _dt

        from_dt = _dt.fromisoformat(from_date) if from_date else None
        to_dt = _dt.fromisoformat(to_date) if to_date else None
        return await service.get_vehicle_history(
            vehicle_id=vehicle_id,
            tenant_id=principal.tenant_id,
            from_date=from_dt,
            to_date=to_dt,
            types=parsed_types,
            cursor=cursor,
            limit=limit,
            db=db,
        )
    return await service.list_vehicle_history(
        db,
        principal.tenant_id,
        vehicle_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{vehicle_id}/availability")
async def get_vehicle_availability(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    exclude_trip_id: UUID | None = None,
):
    return await availability_service.vehicle_availability_summary(
        db,
        principal.tenant_id,
        vehicle_id,
        exclude_trip_id=exclude_trip_id,
    )


@router.patch("/{vehicle_id}")
async def patch_vehicle(
    request: Request,
    vehicle_id: UUID,
    payload: schemas.VehiclePatch,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_vehicle(
        db,
        principal.tenant_id,
        vehicle_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{vehicle_id}/qr-code")
async def get_vehicle_qr_code(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_vehicle_qr_code(db, principal.tenant_id, vehicle_id)


@router.post("/{vehicle_id}/documents/{document_type}/renew")
async def renew_vehicle_document(
    request: Request,
    vehicle_id: UUID,
    document_type: str,
    payload: schemas.VehicleDocumentRenewalRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="vehicles.document.renew",
        entity_type="vehicle",
        payload={"vehicle_id": vehicle_id, "document_type": document_type, **payload.model_dump()},
        handler=lambda: service.renew_vehicle_document(
            db,
            principal.tenant_id,
            vehicle_id,
            document_type,
            payload,
            actor_id=principal.user_id,
        ),
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


# ── INS-01: Insurance policy routes ──────────────────────────────────────────


@router.get("/{vehicle_id}/insurance")
async def list_vehicle_insurances(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await insurance_service.list_insurances(
        db, principal.tenant_id, vehicle_id, limit=limit, offset=offset
    )


@router.post("/{vehicle_id}/insurance", status_code=201)
async def create_vehicle_insurance(
    request: Request,
    vehicle_id: UUID,
    payload: schemas.VehicleInsuranceCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await insurance_service.create_insurance(
        db, principal.tenant_id, vehicle_id, payload, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{vehicle_id}/insurance/{insurance_id}")
async def get_vehicle_insurance(
    vehicle_id: UUID,
    insurance_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await insurance_service.get_insurance(
        db, principal.tenant_id, vehicle_id, insurance_id
    )


@router.patch("/{vehicle_id}/insurance/{insurance_id}")
async def update_vehicle_insurance(
    request: Request,
    vehicle_id: UUID,
    insurance_id: UUID,
    payload: schemas.VehicleInsuranceCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await insurance_service.update_insurance(
        db, principal.tenant_id, vehicle_id, insurance_id, payload, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.delete("/{vehicle_id}/insurance/{insurance_id}", status_code=204)
async def delete_vehicle_insurance(
    request: Request,
    vehicle_id: UUID,
    insurance_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await insurance_service.delete_insurance(
        db, principal.tenant_id, vehicle_id, insurance_id, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)


# ── INS-01: Insurance claims routes ──────────────────────────────────────────


@router.get("/{vehicle_id}/insurance/{insurance_id}/claims")
async def list_insurance_claims(
    vehicle_id: UUID,
    insurance_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await insurance_service.list_claims(
        db, principal.tenant_id, vehicle_id, insurance_id, limit=limit, offset=offset
    )


@router.post("/{vehicle_id}/insurance/{insurance_id}/claims", status_code=201)
async def create_insurance_claim(
    request: Request,
    vehicle_id: UUID,
    insurance_id: UUID,
    payload: schemas.InsuranceClaimCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await insurance_service.create_claim(
        db, principal.tenant_id, vehicle_id, insurance_id, payload, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.patch("/{vehicle_id}/insurance/{insurance_id}/claims/{claim_id}/status")
async def update_claim_status(
    request: Request,
    vehicle_id: UUID,
    insurance_id: UUID,
    claim_id: UUID,
    payload: schemas.InsuranceClaimStatusUpdate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await insurance_service.update_claim_status(
        db,
        principal.tenant_id,
        vehicle_id,
        insurance_id,
        claim_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res
