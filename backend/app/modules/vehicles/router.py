from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.availability import service as availability_service
from app.modules.vehicles import schemas, service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("")
async def list_vehicles(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_vehicles(
        db,
        principal.tenant_id,
        status_filter=status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_vehicle(
    request: Request,
    payload: schemas.VehicleCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    return await execute_http_idempotent(
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


@router.get("/{vehicle_id}")
async def get_vehicle(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_vehicle(db, principal.tenant_id, vehicle_id)


@router.get("/{vehicle_id}/history")
async def list_vehicle_history(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
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
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
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
    vehicle_id: UUID,
    payload: schemas.VehiclePatch,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_vehicle(
        db,
        principal.tenant_id,
        vehicle_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/{vehicle_id}/qr-code")
async def get_vehicle_qr_code(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_vehicle_qr_code(db, principal.tenant_id, vehicle_id)


@router.post("/{vehicle_id}/documents/{document_type}/renew")
async def renew_vehicle_document(
    vehicle_id: UUID,
    document_type: str,
    payload: schemas.VehicleDocumentRenewalRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
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
