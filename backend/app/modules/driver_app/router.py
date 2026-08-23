from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import DriverPrincipal, get_driver_principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.modules.driver_app import schemas, service

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


@router.get("/bootstrap", response_model=schemas.DriverBootstrapRead)
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


@router.get(
    "/checklist-templates",
    response_model=list[schemas.DriverChecklistTemplateRead],
)
async def list_checklist_templates(
    principal: DriverPrincipalDependency,
    db: RlsSession,
):
    _require_driver_id(principal)
    return await service.list_driver_checklist_templates(db, principal.tenant_id)


@router.get(
    "/vehicles",
    status_code=403,
    deprecated=True,
    responses={
        403: {
            "model": schemas.ApiErrorResponse,
            "description": "Fleet selection is restricted to dispatch.",
        }
    },
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


@router.get("/active-trip", response_model=schemas.DriverTripRead | None)
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


@router.get("/trips/history", response_model=schemas.DriverTripPageRead)
async def list_trip_history(
    principal: DriverPrincipalDependency,
    db: RlsSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    driver_id = _require_driver_id(principal)
    return await service.list_driver_trip_history(
        db,
        tenant_id=principal.tenant_id,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@router.get("/trips", response_model=schemas.DriverTripPageRead)
async def list_assigned_trips(
    principal: DriverPrincipalDependency,
    db: RlsSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    driver_id = _require_driver_id(principal)
    return await service.list_assigned_driver_trips(
        db,
        tenant_id=principal.tenant_id,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/trips/{trip_id}/documents",
    response_model=schemas.DriverTripDocumentsRead,
)
async def get_trip_documents(
    trip_id: UUID,
    principal: DriverPrincipalDependency,
    db: RlsSession,
):
    driver_id = _require_driver_id(principal)
    return await service.get_driver_trip_documents(
        db,
        tenant_id=principal.tenant_id,
        driver_id=driver_id,
        trip_id=trip_id,
    )


@router.post(
    "/trips/{trip_id}/document-requests",
    response_model=schemas.DriverDocumentRequestRead,
    status_code=201,
)
async def request_trip_document(
    trip_id: UUID,
    payload: schemas.DriverDocumentRequestCreate,
    principal: DriverPrincipalDependency,
    db: RlsSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    driver_id = _require_driver_id(principal)
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        driver_id=driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="driver.document_request.create",
        entity_type="operational_exception",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.request_driver_trip_document(
            db,
            tenant_id=principal.tenant_id,
            driver_id=driver_id,
            trip_id=trip_id,
            payload=payload,
        ),
    )


@router.post(
    "/trips",
    status_code=403,
    deprecated=True,
    responses={
        403: {
            "model": schemas.ApiErrorResponse,
            "description": "Trip creation is restricted to dispatch.",
        }
    },
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
