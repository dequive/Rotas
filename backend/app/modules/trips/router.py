import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import TRIPS_CLOSE, TRIPS_DISPATCH, TRIPS_READ, require_permission
from app.modules.drivers.models import Driver
from app.modules.tenants.models import TenantDocumentProfile
from app.modules.trips import schemas, service
from app.modules.trips.exporters import render_trip_report
from app.modules.trips.models import Trip, TripStop
from app.modules.vehicles.models import Vehicle

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("")
async def list_trips(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    redis = getattr(request.app.state, "redis", None)
    use_cache = (
        status == "active"
        and vehicle_id is None
        and driver_id is None
        and date_from is None
        and date_to is None
    )
    cache_key = f"tenant:{principal.tenant_id}:trips:active:limit={limit}:offset={offset}"
    if use_cache and redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    result = await service.list_trips(
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

    if use_cache and redis is not None:
        await redis.setex(cache_key, 30, json.dumps(result, default=str))

    return result


@router.post("")
async def create_trip(
    request: Request,
    payload: schemas.TripCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/sla/evaluate")
async def evaluate_delivery_sla(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.evaluate_delivery_sla(
        db,
        principal.tenant_id,
        actor_id=principal.user_id,
    )


@router.post("/{trip_id}/start")
async def start_trip(
    request: Request,
    trip_id: UUID,
    payload: schemas.StartTripRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/dispatch-clearance/request")
async def request_dispatch_clearance(
    request: Request,
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.request_dispatch_clearance(
        db,
        principal.tenant_id,
        trip_id,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/dispatch-clearances")
async def list_dispatch_clearances(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
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
    request: Request,
    trip_id: UUID,
    payload: schemas.DispatchClearanceApproveRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/dispatch")
async def dispatch_trip(
    request: Request,
    trip_id: UUID,
    payload: schemas.TripDispatchRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/events")
async def list_execution_events(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
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
    request: Request,
    trip_id: UUID,
    payload: schemas.TripExecutionEventCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/incidents")
async def list_incidents(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
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
    request: Request,
    trip_id: UUID,
    payload: schemas.TripIncidentCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/incidents/{incident_id}/resolve")
async def resolve_incident(
    request: Request,
    trip_id: UUID,
    incident_id: UUID,
    payload: schemas.TripIncidentResolveRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.resolve_incident(
        db,
        principal.tenant_id,
        trip_id,
        incident_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/stops")
async def create_stop(
    request: Request,
    trip_id: UUID,
    payload: schemas.TripStopCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/associate-contract")
async def associate_contract(
    request: Request,
    trip_id: UUID,
    payload: schemas.AssociateContractRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.associate_contract(
        db,
        principal.tenant_id,
        trip_id,
        payload,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/costs")
async def create_cost(
    request: Request,
    trip_id: UUID,
    payload: schemas.TripCostCreate,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.create_cost(
        db, principal.tenant_id, trip_id, payload, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/driver-despacho")
async def record_driver_travel_allowance(
    request: Request,
    trip_id: UUID,
    payload: schemas.TripDriverAllowanceRecordRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{trip_id}/costs")
async def list_costs(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_costs(db, principal.tenant_id, trip_id)


@router.post("/{trip_id}/complete")
async def complete_trip(
    request: Request,
    trip_id: UUID,
    payload: schemas.CompleteTripRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{trip_id}/close")
async def operational_close_trip(
    request: Request,
    trip_id: UUID,
    payload: schemas.OperationalCloseTripRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    res = await execute_http_idempotent(
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
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{trip_id}/report/pdf")
async def download_trip_report_pdf(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    trip_row = await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.tenant_id == principal.tenant_id)
    )
    trip = trip_row.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    vehicle = None
    if trip.vehicle_id:
        v_row = await db.execute(select(Vehicle).where(Vehicle.id == trip.vehicle_id))
        vehicle = v_row.scalar_one_or_none()

    driver = None
    if trip.driver_id:
        d_row = await db.execute(select(Driver).where(Driver.id == trip.driver_id))
        driver = d_row.scalar_one_or_none()

    stops_row = await db.execute(
        select(TripStop).where(TripStop.trip_id == trip_id).order_by(TripStop.stopped_at)
    )
    stops = list(stops_row.scalars().all())

    prof_row = await db.execute(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id)
    )
    prof_obj = prof_row.scalar_one_or_none()
    profile = (
        {
            "legal_name": prof_obj.legal_name,
            "address_line1": prof_obj.address_line1,
            "address_line2": prof_obj.address_line2,
            "city": prof_obj.city,
            "phone": prof_obj.phone,
            "email": prof_obj.email,
        }
        if prof_obj
        else None
    )

    pdf_bytes = render_trip_report(
        trip, vehicle=vehicle, driver=driver, stops=stops, profile=profile
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio-viagem-{trip_id}.pdf"},
    )


@router.patch("/{trip_id}")
async def patch_trip(
    request: Request,
    trip_id: UUID,
    payload: schemas.TripPatch,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_trip(db, principal.tenant_id, trip_id, payload)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res
