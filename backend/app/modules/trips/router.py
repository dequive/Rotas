from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.modules.trips import schemas, service

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("")
async def list_trips(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_trips(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_trip(
    payload: schemas.TripCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.create",
        entity_type="trip",
        payload=payload,
        handler=lambda: service.create_trip(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/sla/evaluate")
async def evaluate_delivery_sla(
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.evaluate_delivery_sla(
        db,
        principal.tenant_id,
        actor_id=principal.user_id,
    )


@router.post("/{trip_id}/start")
async def start_trip(
    trip_id: UUID,
    payload: schemas.StartTripRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.start",
        entity_type="trip",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.start_trip(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{trip_id}/dispatch-clearance/request")
async def request_dispatch_clearance(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.request_dispatch_clearance(
        db,
        principal.tenant_id,
        trip_id,
        actor_id=principal.user_id,
    )


@router.get("/dispatch-clearances")
async def list_dispatch_clearances(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    trip_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_dispatch_clearances(
        db,
        principal.tenant_id,
        trip_id=trip_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.post("/{trip_id}/dispatch-clearance/approve")
async def approve_dispatch_clearance(
    trip_id: UUID,
    payload: schemas.DispatchClearanceApproveRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.dispatch_clearance.approve",
        entity_type="dispatch_clearance",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.approve_dispatch_clearance(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{trip_id}/dispatch")
async def dispatch_trip(
    trip_id: UUID,
    payload: schemas.TripDispatchRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.dispatch",
        entity_type="trip",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.dispatch_trip(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/events")
async def list_execution_events(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    trip_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_execution_events(
        db,
        principal.tenant_id,
        trip_id=trip_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )


@router.post("/{trip_id}/events")
async def create_execution_event(
    trip_id: UUID,
    payload: schemas.TripExecutionEventCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.event.create",
        entity_type="trip_execution_event",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_execution_event(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/incidents")
async def list_incidents(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    trip_id: UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_incidents(
        db,
        principal.tenant_id,
        trip_id=trip_id,
        status_filter=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@router.post("/{trip_id}/incidents")
async def create_incident(
    trip_id: UUID,
    payload: schemas.TripIncidentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.incident.create",
        entity_type="trip_incident",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_incident(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{trip_id}/incidents/{incident_id}/resolve")
async def resolve_incident(
    trip_id: UUID,
    incident_id: UUID,
    payload: schemas.TripIncidentResolveRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.resolve_incident(
        db,
        principal.tenant_id,
        trip_id,
        incident_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/{trip_id}/stops")
async def create_stop(
    trip_id: UUID,
    payload: schemas.TripStopCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.stop.create",
        entity_type="trip_stop",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.create_stop(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{trip_id}/associate-contract")
async def associate_contract(
    trip_id: UUID,
    payload: schemas.AssociateContractRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.associate_contract(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/{trip_id}/costs")
async def create_cost(
    trip_id: UUID,
    payload: schemas.TripCostCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_cost(
        db, principal.tenant_id, trip_id, payload, actor_id=principal.user_id
    )


@router.post("/{trip_id}/driver-despacho")
async def record_driver_travel_allowance(
    trip_id: UUID,
    payload: schemas.TripDriverAllowanceRecordRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.driver_despacho.record",
        entity_type="trip",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.record_driver_travel_allowance(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/{trip_id}/costs")
async def list_costs(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_costs(db, principal.tenant_id, trip_id)


@router.post("/{trip_id}/complete")
async def complete_trip(
    trip_id: UUID,
    payload: schemas.CompleteTripRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.complete",
        entity_type="trip",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.complete_trip(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.post("/{trip_id}/close")
async def operational_close_trip(
    trip_id: UUID,
    payload: schemas.OperationalCloseTripRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="trips.close",
        entity_type="trip",
        payload={"trip_id": trip_id, **payload.model_dump()},
        handler=lambda: service.operational_close_trip(
            db,
            principal.tenant_id,
            trip_id,
            payload,
            actor_id=principal.user_id,
        ),
    )
