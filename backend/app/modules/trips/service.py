import uuid
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.availability.service import require_vehicle_and_driver_available
from app.modules.cargo.models import CargoManifest, DeliveryProof, LoadPermit, TransportDocument
from app.modules.contracts.models import Contract
from app.modules.drivers.hos_service import calculate_driving_hours
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.operations.service import has_active_waiver
from app.modules.tenants.models import Tenant
from app.modules.trip_orders.models import TripOrder
from app.modules.trips.costs import reconcile_trip_costs, record_trip_cost, serialize_trip_cost
from app.modules.trips.models import (
    DispatchClearance,
    Trip,
    TripCost,
    TripExecutionEvent,
    TripIncident,
    TripStop,
)
from app.modules.trips.schemas import (
    AssociateContractRequest,
    CompleteTripRequest,
    DispatchClearanceApproveRequest,
    OperationalCloseTripRequest,
    StartTripRequest,
    TripCostCreate,
    TripCreate,
    TripDispatchRequest,
    TripDriverAllowanceRecordRequest,
    TripExecutionEventCreate,
    TripIncidentCreate,
    TripIncidentResolveRequest,
    TripPatch,
    TripStopCreate,
    TripStopPatch,
)
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.service import create_breakdown_maintenance_request

TRIP_EVENT_TYPES = {
    "dispatched",
    "departed_origin",
    "arrived_loading_point",
    "loading_started",
    "loading_completed",
    "departed_loading_point",
    "arrived_checkpoint",
    "delayed",
    "incident_reported",
    "arrived_destination",
    "unloading_started",
    "unloading_completed",
    "proof_of_delivery_uploaded",
    "completed",
}

TRIP_EVENT_SOURCES = {"manual", "driver_app", "gps", "integration", "system"}
INCIDENT_TYPES = {
    "accident",
    "breakdown",
    "police_stop",
    "border_delay",
    "client_delay",
    "loading_delay",
    "unloading_delay",
    "theft",
    "cargo_damage",
    "route_blocked",
    "fuel_issue",
    "document_issue",
    "other",
}
INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}
SLA_MONITORED_STATUSES = {"dispatched", "in_progress", "delayed"}
POLICY_CARGO_DOCUMENTS_KEY = "cargo_required_documents_by_type"
POLICY_DEFAULT_CARGO_DOCUMENTS_KEY = "cargo_required_documents"
POLICY_TRIP_STOPS_KEY = "trip_required_stops_by_cargo_type"
POLICY_DEFAULT_TRIP_STOPS_KEY = "trip_required_stops"
POLICY_DEFAULT_ALIASES = {"*", "default", "__default__"}
DRIVER_ALLOWANCE_POLICY_KEY = "driver_travel_allowance_policy"
DEFAULT_DRIVER_ALLOWANCE_POLICY = {
    "enabled": True,
    "table_name": "Tabela padrao de despacho",
    "table_reference": "system-default",
    "currency": "MZN",
    "min_long_course_km": 100,
    "tiers": [
        {"min_km": 100, "max_km": 250, "amount": 500, "label": "100-249 km"},
        {"min_km": 250, "max_km": 500, "amount": 1000, "label": "250-499 km"},
        {"min_km": 500, "amount": 1500, "label": "500+ km"},
    ],
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def _normalize_policy_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _normalize_required_document(value: str) -> str:
    return value.strip().casefold()


def _driver_allowance_policy(policy: dict) -> dict:
    value = policy.get(DRIVER_ALLOWANCE_POLICY_KEY)
    if not isinstance(value, dict):
        return {**DEFAULT_DRIVER_ALLOWANCE_POLICY, "source": "system_default"}
    return {
        "enabled": value.get("enabled", DEFAULT_DRIVER_ALLOWANCE_POLICY["enabled"]),
        "table_name": value.get("table_name")
        or value.get("name")
        or DEFAULT_DRIVER_ALLOWANCE_POLICY["table_name"],
        "table_reference": value.get("table_reference")
        or value.get("reference")
        or DEFAULT_DRIVER_ALLOWANCE_POLICY["table_reference"],
        "effective_from": value.get("effective_from"),
        "entry_mode": value.get("entry_mode"),
        "currency": (value.get("currency") or DEFAULT_DRIVER_ALLOWANCE_POLICY["currency"]).upper(),
        "min_long_course_km": value.get(
            "min_long_course_km",
            DEFAULT_DRIVER_ALLOWANCE_POLICY["min_long_course_km"],
        ),
        "tiers": value.get("tiers", DEFAULT_DRIVER_ALLOWANCE_POLICY["tiers"]),
        "source": "tenant_policy",
    }


def _driver_allowance_match(policy: dict, distance_km: float) -> dict:
    allowance_policy = _driver_allowance_policy(policy)
    if allowance_policy.get("enabled") is False:
        return {
            "amount": 0.0,
            "currency": allowance_policy["currency"],
            "policy": allowance_policy,
            "tier": None,
            "reason": "disabled",
        }

    min_long_course_km = float(allowance_policy.get("min_long_course_km") or 0)
    if distance_km < min_long_course_km:
        return {
            "amount": 0.0,
            "currency": allowance_policy["currency"],
            "policy": allowance_policy,
            "tier": None,
            "reason": "below_min_long_course_km",
        }

    tiers = allowance_policy.get("tiers")
    if not isinstance(tiers, list):
        tiers = DEFAULT_DRIVER_ALLOWANCE_POLICY["tiers"]
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        min_km = float(tier.get("min_km") or 0)
        max_km = tier.get("max_km")
        if distance_km < min_km:
            continue
        if max_km is not None and distance_km >= float(max_km):
            continue
        return {
            "amount": float(tier.get("amount") or 0),
            "currency": allowance_policy["currency"],
            "policy": allowance_policy,
            "tier": {
                "min_km": min_km,
                "max_km": float(max_km) if max_km is not None else None,
                "amount": float(tier.get("amount") or 0),
                "label": tier.get("label") or tier.get("description"),
                "code": tier.get("code"),
            },
            "reason": "matched",
        }
    return {
        "amount": 0.0,
        "currency": allowance_policy["currency"],
        "policy": allowance_policy,
        "tier": None,
        "reason": "no_matching_tier",
    }


def serialize_trip(trip: Trip) -> dict:
    return {
        "id": trip.id,
        "tenant_id": trip.tenant_id,
        "trip_order_id": trip.trip_order_id,
        "contract_id": trip.contract_id,
        "vehicle_id": trip.vehicle_id,
        "driver_id": trip.driver_id,
        "origin": trip.origin,
        "destination": trip.destination,
        "cargo_type": trip.cargo_type,
        "cargo_class": trip.cargo_class,
        "cargo_weight": float(trip.cargo_weight) if trip.cargo_weight is not None else None,
        "payload_override_reason": trip.payload_override_reason,
        "load_state": trip.load_state,
        "requires_load_permit": trip.requires_load_permit,
        "requires_cargo_manifest": trip.requires_cargo_manifest,
        "waybill_number": trip.waybill_number,
        "km_start": trip.km_start,
        "km_end": trip.km_end,
        "status": trip.status,
        "planned_departure": trip.planned_departure,
        "actual_departure": trip.actual_departure,
        "planned_arrival": trip.planned_arrival,
        "actual_arrival": trip.actual_arrival,
        "recipient_name": trip.recipient_name,
        "cargo_status": trip.cargo_status,
        "contract_reference": trip.contract_reference,
        "billing_status": trip.billing_status,
        "billable_at": trip.billable_at,
        "billed_at": trip.billed_at,
        "billing_document_id": trip.billing_document_id,
        "closed_at": trip.closed_at,
        "closed_by": trip.closed_by,
        "operational_close_notes": trip.operational_close_notes,
        "total_fuel_cost": trip.total_fuel_cost,
        "total_expense_cost": trip.total_expense_cost,
        "total_transport_cost": trip.total_transport_cost,
        "actual_revenue": trip.actual_revenue,
        "actual_margin": trip.actual_margin,
        "costs_reconciled_at": trip.costs_reconciled_at,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def serialize_dispatch_clearance(clearance: DispatchClearance) -> dict:
    return {
        "id": clearance.id,
        "tenant_id": clearance.tenant_id,
        "trip_order_id": clearance.trip_order_id,
        "trip_id": clearance.trip_id,
        "vehicle_checked": clearance.vehicle_checked,
        "driver_checked": clearance.driver_checked,
        "documents_checked": clearance.documents_checked,
        "load_permit_checked": clearance.load_permit_checked,
        "cargo_checked": clearance.cargo_checked,
        "fuel_advance_checked": clearance.fuel_advance_checked,
        "route_risk_checked": clearance.route_risk_checked,
        "clearance_status": clearance.clearance_status,
        "blocked_reason": clearance.blocked_reason,
        "approved_by": clearance.approved_by,
        "approved_at": clearance.approved_at,
        "created_at": clearance.created_at,
        "updated_at": clearance.updated_at,
    }


def serialize_execution_event(event: TripExecutionEvent) -> dict:
    return {
        "id": event.id,
        "tenant_id": event.tenant_id,
        "trip_id": event.trip_id,
        "event_type": event.event_type,
        "event_time": event.event_time,
        "location": event.location,
        "odometer_reading": event.odometer_reading,
        "fuel_level": event.fuel_level,
        "notes": event.notes,
        "reported_by": event.reported_by,
        "source": event.source,
        "created_at": event.created_at,
    }


def serialize_incident(incident: TripIncident) -> dict:
    return {
        "id": incident.id,
        "tenant_id": incident.tenant_id,
        "trip_id": incident.trip_id,
        "vehicle_id": incident.vehicle_id,
        "driver_id": incident.driver_id,
        "incident_type": incident.incident_type,
        "severity": incident.severity,
        "status": incident.status,
        "occurred_at": incident.occurred_at,
        "reported_at": incident.reported_at,
        "location": incident.location,
        "description": incident.description,
        "immediate_action": incident.immediate_action,
        "resolution_notes": incident.resolution_notes,
        "financial_impact_estimate": incident.financial_impact_estimate,
        "delay_minutes": incident.delay_minutes,
        "reported_by": incident.reported_by,
        "resolved_by": incident.resolved_by,
        "resolved_at": incident.resolved_at,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }


async def _require_trip(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Trip:
    trip = await db.get(Trip, trip_id)
    if not trip or trip.tenant_id != tenant_id:
        raise ApiError("trip_not_found", "Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
    return trip


async def list_trips(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Trip).where(Trip.tenant_id == tenant_id)

    if status_filter:
        query = query.where(Trip.status == status_filter)
    if vehicle_id:
        query = query.where(Trip.vehicle_id == vehicle_id)
    if driver_id:
        query = query.where(Trip.driver_id == driver_id)
    if date_from:
        query = query.where(Trip.created_at >= date_from)
    if date_to:
        query = query.where(Trip.created_at < date_to)

    result = await db.execute(query.order_by(Trip.created_at.desc()).limit(limit).offset(offset))
    return [serialize_trip(trip) for trip in result.scalars()]


async def list_dispatch_clearances(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(DispatchClearance).where(DispatchClearance.tenant_id == tenant_id)
    if trip_id:
        query = query.where(DispatchClearance.trip_id == trip_id)
    if status_filter:
        query = query.where(DispatchClearance.clearance_status == status_filter)
    result = await db.execute(
        query.order_by(DispatchClearance.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_dispatch_clearance(clearance) for clearance in result.scalars()]


async def list_execution_events(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(TripExecutionEvent).where(TripExecutionEvent.tenant_id == tenant_id)
    if trip_id:
        query = query.where(TripExecutionEvent.trip_id == trip_id)
    if event_type:
        query = query.where(TripExecutionEvent.event_type == event_type)
    result = await db.execute(
        query.order_by(TripExecutionEvent.event_time.desc()).limit(limit).offset(offset)
    )
    return [serialize_execution_event(event) for event in result.scalars()]


async def list_incidents(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID | None = None,
    status_filter: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(TripIncident).where(TripIncident.tenant_id == tenant_id)
    if trip_id:
        query = query.where(TripIncident.trip_id == trip_id)
    if status_filter:
        query = query.where(TripIncident.status == status_filter)
    if severity:
        query = query.where(TripIncident.severity == severity)
    result = await db.execute(
        query.order_by(TripIncident.occurred_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_incident(incident) for incident in result.scalars()]


async def evaluate_delivery_sla(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> list[dict]:
    evaluated_at = now_utc()
    result = await db.execute(
        select(Trip).where(
            Trip.tenant_id == tenant_id,
            Trip.status.in_(SLA_MONITORED_STATUSES),
            Trip.planned_arrival.is_not(None),
            Trip.actual_arrival.is_(None),
            Trip.planned_arrival < evaluated_at,
        )
    )
    delayed: list[Trip] = []
    for trip in result.scalars():
        old_status = trip.status
        if trip.status != "delayed":
            trip.status = "delayed"
            event = TripExecutionEvent(
                tenant_id=tenant_id,
                trip_id=trip.id,
                event_type="delayed",
                event_time=evaluated_at,
                notes="Entrega ultrapassou o SLA planejado.",
                reported_by=actor_id,
                source="system",
            )
            db.add(event)
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                user_id=actor_id,
                action="trip.sla_breached",
                entity_type="trip",
                entity_id=trip.id,
                old_values={"status": old_status},
                new_values={
                    "status": trip.status,
                    "planned_arrival": trip.planned_arrival,
                    "evaluated_at": evaluated_at,
                },
            )
        delay_minutes = (
            int((evaluated_at - trip.planned_arrival).total_seconds() // 60)
            if trip.planned_arrival is not None
            else 0
        )
        await ensure_exception(
            db,
            tenant_id,
            entity_type="trip",
            entity_id=trip.id,
            exception_type="trip_delivery_sla_breached",
            severity="high" if delay_minutes >= 240 else "medium",
            title=f"Entrega atrasada: {trip.origin} -> {trip.destination}",
            message="A viagem ultrapassou o horário planejado de chegada.",
            actor_id=actor_id,
            context={
                "trip_id": str(trip.id),
                "planned_arrival": trip.planned_arrival.isoformat() if trip.planned_arrival is not None else None,
                "delay_minutes": delay_minutes,
            },
            source_type="trip",
            source_id=trip.id,
        )
        delayed.append(trip)

    await db.commit()
    for trip in delayed:
        await db.refresh(trip)
    return [serialize_trip(trip) for trip in delayed]


async def create_trip(
    db: AsyncSession,
    tenant_id: UUID,
    payload: TripCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await require_vehicle_and_driver_available(
        db,
        tenant_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
    )

    # HOS guard — runs after vehicle/driver row locks are held
    if not payload.hos_override_reason:
        hos_data = await calculate_driving_hours(payload.driver_id, tenant_id, db)
        if hos_data["status"] == "violation":
            raise ApiError(
                "hos_violation_active",
                "Driver has exceeded Hours of Service limits and cannot be assigned.",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "override_required": True,
                    "hours_today": hos_data["hours_today"],
                    "hours_this_week": hos_data["hours_this_week"],
                    "violation_reason": hos_data["violation_reason"],
                },
            )

    contract_reference = payload.contract_reference
    if payload.contract_id:
        contract = await db.get(Contract, payload.contract_id)
        if not contract or contract.tenant_id != tenant_id:
            raise ApiError("contract_not_found", "Contract not found.", status_code=404)
        contract_reference = contract.contract_reference

    # LOAD-01: Payload weight guard
    _vehicle = await db.get(Vehicle, payload.vehicle_id)
    if _vehicle is not None and getattr(_vehicle, "ownership_type", "fleet") != "fleet":
        raise ApiError(
            "invalid_vehicle_ownership",
            "Customer vehicles cannot be assigned to cargo trips.",
            status_code=409,
        )
    if (
        _vehicle is not None
        and _vehicle.max_payload_kg is not None
        and payload.cargo_weight is not None
        and payload.cargo_weight > _vehicle.max_payload_kg
        and not payload.payload_override_reason
    ):
        excess = float(payload.cargo_weight - _vehicle.max_payload_kg)
        raise ApiError(
            "payload_exceeded",
            f"Cargo weight exceeds vehicle max payload capacity by {excess:.2f} kg.",
            status_code=409,
            details={
                "cargo_weight_kg": float(payload.cargo_weight),
                "max_payload_kg": float(_vehicle.max_payload_kg),
                "excess_kg": excess,
            },
        )

    waybill_num = f"GT-{datetime.now(UTC).year}/{str(uuid.uuid4()).split('-')[0].upper()}"

    trip = Trip(
        tenant_id=tenant_id,
        contract_id=payload.contract_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        origin=payload.origin,
        origin_location=None,
        destination=payload.destination,
        destination_location=None,
        cargo_type=payload.cargo_type,
        cargo_class=payload.cargo_class,
        cargo_weight=payload.cargo_weight,
        load_state=payload.load_state,
        requires_load_permit=payload.requires_load_permit,
        requires_cargo_manifest=payload.requires_cargo_manifest,
        waybill_number=waybill_num,
        planned_departure=payload.planned_departure,
        planned_arrival=payload.planned_arrival,
        contract_reference=contract_reference,
        payload_override_reason=payload.payload_override_reason,
        is_hazmat=payload.is_hazmat,
        is_international=payload.is_international,
        hazmat_class=payload.hazmat_class,
        un_number=payload.un_number,
        hazmat_label=payload.hazmat_label,
        status="draft",
        billing_status="pending_delivery_proof",
    )
    db.add(trip)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            "assignment_conflict",
            "Vehicle or driver already has an active trip.",
            status_code=409,
        ) from exc
    audit_new_values: dict = {
        "status": trip.status,
        "origin": trip.origin,
        "destination": trip.destination,
        "vehicle_id": str(trip.vehicle_id),
        "driver_id": str(trip.driver_id),
        "contract_id": str(trip.contract_id) if trip.contract_id else None,
    }
    if payload.hos_override_reason:
        audit_new_values["hos_override_reason"] = payload.hos_override_reason
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.created",
        entity_type="trip",
        entity_id=trip.id,
        new_values=audit_new_values,
    )
    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)


async def start_trip(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: StartTripRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status != "dispatched":
        raise ApiError(
            "dispatch_required",
            "Trip must pass dispatch clearance and dispatch before it can be started.",
            status_code=409,
            details={"status": trip.status},
        )

    # LOAD-01: Payload weight guard at start time
    if trip.cargo_weight is not None:
        _start_vehicle = await db.get(Vehicle, trip.vehicle_id)
        if (
            _start_vehicle is not None
            and _start_vehicle.max_payload_kg is not None
            and trip.cargo_weight > _start_vehicle.max_payload_kg
            and not trip.payload_override_reason
        ):
            excess = float(trip.cargo_weight - _start_vehicle.max_payload_kg)
            raise ApiError(
                "payload_exceeded",
                f"Cannot start trip — cargo weight exceeds vehicle capacity by {excess:.2f} kg.",
                status_code=409,
                details={
                    "cargo_weight_kg": float(trip.cargo_weight),
                    "max_payload_kg": float(_start_vehicle.max_payload_kg),
                    "excess_kg": excess,
                },
            )

    old_values = {
        "status": trip.status,
        "km_start": trip.km_start,
        "actual_departure": trip.actual_departure,
    }
    trip.km_start = payload.km_start
    trip.km_start_file_id = payload.km_start_file_id
    trip.actual_departure = payload.actual_departure or now_utc()
    trip.status = "in_progress"

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.started",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_values,
        new_values={
            "status": trip.status,
            "km_start": trip.km_start,
            "actual_departure": trip.actual_departure,
        },
    )
    await db.commit()
    await db.refresh(trip)

    # LOAD-02: Create hazmat_active alert — best-effort, trip start must not fail on alert error
    if trip.is_hazmat:
        try:
            from app.modules.alerts.schemas import AlertCreate
            from app.modules.alerts.service import create_alert

            await create_alert(
                db,
                tenant_id=tenant_id,
                payload=AlertCreate(
                    request_reference=f"hazmat_active_{trip.id}",
                    alert_type="hazmat_active",
                    priority="high",
                    entity_type="trip",
                    entity_id=trip.id,
                    title=f"Viagem hazmat em curso: classe {trip.hazmat_class or 'N/D'}",
                    message=(
                        f"Trip {trip.id} started with hazmat cargo."
                        f" Class={trip.hazmat_class}, UN={trip.un_number}"
                    ),
                ),
                actor_id=actor_id,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to create hazmat_active alert for trip %s", trip.id, exc_info=True
            )

    return serialize_trip(trip)


async def request_dispatch_clearance(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status not in {"draft", "planned"}:
        raise ApiError(
            "invalid_trip_status",
            "Only draft or planned trips can request dispatch clearance.",
            status_code=409,
            details={"status": trip.status},
        )

    existing = await db.scalar(
        select(DispatchClearance).where(
            DispatchClearance.tenant_id == tenant_id,
            DispatchClearance.trip_id == trip_id,
            DispatchClearance.clearance_status.in_(("pending", "approved", "blocked")),
        )
    )
    if existing:
        return serialize_dispatch_clearance(existing)

    clearance = DispatchClearance(
        tenant_id=tenant_id,
        trip_order_id=trip.trip_order_id,
        trip_id=trip.id,
        clearance_status="pending",
    )
    db.add(clearance)
    old_trip_status = trip.status
    trip.status = "dispatch_pending"
    if trip.trip_order_id:
        order = await db.get(TripOrder, trip.trip_order_id)
        if order and order.tenant_id == tenant_id:
            order.status = "dispatch_pending"

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="dispatch.clearance_requested",
        entity_type="trip",
        entity_id=trip.id,
        old_values={"status": old_trip_status},
        new_values={"status": trip.status, "clearance_status": clearance.clearance_status},
    )
    await db.commit()
    await db.refresh(clearance)
    return serialize_dispatch_clearance(clearance)


async def _tenant_compliance_policy(db: AsyncSession, tenant_id: UUID) -> dict:
    tenant = await db.get(Tenant, tenant_id)
    return tenant.compliance_policy if tenant and tenant.compliance_policy else {}


def _required_cargo_documents_for_trip(policy: dict, trip: Trip) -> set[str]:
    required = {
        _normalize_required_document(item)
        for item in policy.get(POLICY_DEFAULT_CARGO_DOCUMENTS_KEY, [])
        if isinstance(item, str) and item.strip()
    }
    by_type = policy.get(POLICY_CARGO_DOCUMENTS_KEY, {})
    if not isinstance(by_type, dict):
        return required

    cargo_type = _normalize_policy_key(trip.cargo_type)
    for raw_key, raw_documents in by_type.items():
        if not isinstance(raw_key, str) or not isinstance(raw_documents, list):
            continue
        normalized_key = _normalize_policy_key(raw_key)
        if normalized_key != cargo_type and normalized_key not in POLICY_DEFAULT_ALIASES:
            continue
        required.update(
            _normalize_required_document(item)
            for item in raw_documents
            if isinstance(item, str) and item.strip()
        )
    return required


def _required_trip_stops_for_trip(policy: dict, trip: Trip) -> set[str]:
    required = {
        _normalize_required_document(item)
        for item in policy.get(POLICY_DEFAULT_TRIP_STOPS_KEY, [])
        if isinstance(item, str) and item.strip()
    }
    by_type = policy.get(POLICY_TRIP_STOPS_KEY, {})
    if not isinstance(by_type, dict):
        return required

    cargo_type = _normalize_policy_key(trip.cargo_type)
    for raw_key, raw_stops in by_type.items():
        if not isinstance(raw_key, str) or not isinstance(raw_stops, list):
            continue
        normalized_key = _normalize_policy_key(raw_key)
        if normalized_key != cargo_type and normalized_key not in POLICY_DEFAULT_ALIASES:
            continue
        required.update(
            _normalize_required_document(item)
            for item in raw_stops
            if isinstance(item, str) and item.strip()
        )
    return required


async def _has_transport_document(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    document_type: str | None = None,
) -> bool:
    query = select(TransportDocument.id).where(
        TransportDocument.tenant_id == tenant_id,
        TransportDocument.trip_id == trip_id,
        TransportDocument.status != "cancelled",
    )
    if document_type:
        query = query.where(func.lower(TransportDocument.document_type) == document_type.casefold())
    return (await db.scalar(query)) is not None


async def _missing_required_cargo_documents(
    db: AsyncSession,
    tenant_id: UUID,
    trip: Trip,
) -> list[str]:
    status_payload = await get_trip_document_requirements(db, tenant_id, trip)
    return [
        item["document_type"]
        for item in status_payload["requirements"]
        if not item["present"]
    ]


async def get_trip_document_requirements(
    db: AsyncSession,
    tenant_id: UUID,
    trip: Trip,
) -> dict:
    """Return the canonical dispatch document requirements for one trip."""

    policy = await _tenant_compliance_policy(db, tenant_id)
    required = _required_cargo_documents_for_trip(policy, trip)
    if trip.requires_load_permit:
        required.add("load_permit")
    if trip.requires_cargo_manifest:
        required.add("cargo_manifest")

    transport_document_types = set(
        await db.scalars(
            select(func.lower(TransportDocument.document_type)).where(
                TransportDocument.tenant_id == tenant_id,
                TransportDocument.trip_id == trip.id,
                TransportDocument.status != "cancelled",
            )
        )
    )
    has_load_permit = (
        await db.scalar(
            select(LoadPermit.id).where(
                LoadPermit.tenant_id == tenant_id,
                LoadPermit.trip_id == trip.id,
                LoadPermit.status != "cancelled",
            )
        )
    ) is not None
    has_cargo_manifest = (
        await db.scalar(
            select(CargoManifest.id).where(
                CargoManifest.tenant_id == tenant_id,
                CargoManifest.trip_id == trip.id,
                CargoManifest.status != "cancelled",
            )
        )
    ) is not None

    requirements: list[dict] = []
    for document in sorted(required):
        if document == "load_permit":
            present = has_load_permit
        elif document == "cargo_manifest":
            present = has_cargo_manifest
        elif document == "transport_document":
            present = bool(transport_document_types)
        elif document.startswith("transport_document:"):
            document_type = document.split(":", 1)[1].strip()
            present = bool(document_type) and document_type.casefold() in (
                transport_document_types
            )
        else:
            present = False
        requirements.append({"document_type": document, "present": present})

    missing_required = [
        item["document_type"] for item in requirements if not item["present"]
    ]
    return {
        "requirements": requirements,
        "missing_required": missing_required,
        "complete": not missing_required,
    }


async def _missing_required_trip_stops(
    db: AsyncSession,
    tenant_id: UUID,
    trip: Trip,
) -> list[str]:
    policy = await _tenant_compliance_policy(db, tenant_id)
    required = _required_trip_stops_for_trip(policy, trip)
    if not required:
        return []

    existing_stops = set(
        await db.scalars(
            select(func.lower(TripStop.stop_type)).where(
                TripStop.tenant_id == tenant_id,
                TripStop.trip_id == trip.id,
            )
        )
    )
    return sorted(required - existing_stops)


async def approve_dispatch_clearance(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: DispatchClearanceApproveRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    clearance = await db.scalar(
        select(DispatchClearance).where(
            DispatchClearance.tenant_id == tenant_id,
            DispatchClearance.trip_id == trip_id,
        )
    )
    if not clearance:
        raise ApiError(
            "dispatch_clearance_not_found",
            "Dispatch clearance has not been requested.",
            status_code=404,
        )
    if clearance.clearance_status == "approved":
        return serialize_dispatch_clearance(clearance)

    missing_cargo_documents = await _missing_required_cargo_documents(db, tenant_id, trip)
    has_load_permit = "load_permit" not in missing_cargo_documents
    required_checks = {
        "vehicle_checked": payload.vehicle_checked,
        "driver_checked": payload.driver_checked,
        "documents_checked": payload.documents_checked and not missing_cargo_documents,
        "load_permit_checked": (payload.load_permit_checked or not trip.requires_load_permit)
        and has_load_permit,
        "cargo_checked": payload.cargo_checked and not missing_cargo_documents,
        "fuel_advance_checked": payload.fuel_advance_checked,
        "route_risk_checked": payload.route_risk_checked,
    }
    missing = [name for name, checked in required_checks.items() if not checked]
    missing.extend(
        f"missing_document:{document}"
        for document in missing_cargo_documents
        if f"missing_document:{document}" not in missing
    )

    clearance.vehicle_checked = payload.vehicle_checked
    clearance.driver_checked = payload.driver_checked
    clearance.documents_checked = required_checks["documents_checked"]
    clearance.load_permit_checked = required_checks["load_permit_checked"]
    clearance.cargo_checked = required_checks["cargo_checked"]
    clearance.fuel_advance_checked = payload.fuel_advance_checked
    clearance.route_risk_checked = payload.route_risk_checked

    if missing:
        clearance.clearance_status = "blocked"
        clearance.blocked_reason = payload.blocked_reason or f"Missing checks: {', '.join(missing)}"
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="dispatch.blocked",
            entity_type="dispatch_clearance",
            entity_id=clearance.id,
            new_values={"blocked_reason": clearance.blocked_reason, "missing": missing},
        )
        await db.commit()
        await db.refresh(clearance)
        return serialize_dispatch_clearance(clearance)

    await require_vehicle_and_driver_available(
        db,
        tenant_id,
        vehicle_id=trip.vehicle_id,
        driver_id=trip.driver_id,
        exclude_trip_id=trip.id,
    )

    clearance.clearance_status = "approved"
    clearance.blocked_reason = None
    clearance.approved_by = actor_id
    clearance.approved_at = now_utc()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="dispatch.approved",
        entity_type="dispatch_clearance",
        entity_id=clearance.id,
        new_values={"clearance_status": clearance.clearance_status},
    )
    await db.commit()
    await db.refresh(clearance)
    return serialize_dispatch_clearance(clearance)


async def dispatch_trip(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripDispatchRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = (
        await db.execute(
            select(Trip)
            .where(
                Trip.id == trip_id,
                Trip.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not trip:
        raise ApiError("trip_not_found", "Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
    clearance = await db.scalar(
        select(DispatchClearance).where(
            DispatchClearance.tenant_id == tenant_id,
            DispatchClearance.trip_id == trip_id,
            DispatchClearance.clearance_status == "approved",
        )
    )
    if not clearance:
        raise ApiError(
            "dispatch_clearance_required",
            "Trip cannot be dispatched without approved clearance.",
            status_code=409,
        )
    if trip.status not in {"planned", "dispatch_pending"}:
        raise ApiError(
            "invalid_trip_status",
            "Only planned or dispatch-pending trips can be dispatched.",
            status_code=409,
            details={"status": trip.status},
        )

    await require_vehicle_and_driver_available(
        db,
        tenant_id,
        vehicle_id=trip.vehicle_id,
        driver_id=trip.driver_id,
        exclude_trip_id=trip.id,
    )
    old_status = trip.status
    trip.status = "dispatched"
    trip.actual_departure = payload.dispatched_at or now_utc()
    if trip.trip_order_id:
        order = await db.get(TripOrder, trip.trip_order_id)
        if order and order.tenant_id == tenant_id:
            order.status = "dispatched"

    event = TripExecutionEvent(
        tenant_id=tenant_id,
        trip_id=trip.id,
        event_type="dispatched",
        event_time=trip.actual_departure,
        notes=payload.notes,
        reported_by=actor_id,
        source="system",
    )
    db.add(event)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.dispatched",
        entity_type="trip",
        entity_id=trip.id,
        old_values={"status": old_status},
        new_values={"status": trip.status, "event_id": str(event.id)},
    )
    await db.commit()
    await db.refresh(trip)
    await db.refresh(event)
    return {"trip": serialize_trip(trip), "event": serialize_execution_event(event)}


async def create_execution_event(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripExecutionEventCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_trip(db, tenant_id, trip_id)
    if payload.event_type not in TRIP_EVENT_TYPES:
        raise ApiError(
            "invalid_trip_event_type",
            "Invalid trip execution event type.",
            status_code=422,
            details={"allowed": sorted(TRIP_EVENT_TYPES), "value": payload.event_type},
        )
    if payload.source not in TRIP_EVENT_SOURCES:
        raise ApiError(
            "invalid_trip_event_source",
            "Invalid trip execution event source.",
            status_code=422,
            details={"allowed": sorted(TRIP_EVENT_SOURCES), "value": payload.source},
        )
    event = TripExecutionEvent(
        tenant_id=tenant_id,
        trip_id=trip_id,
        event_time=payload.event_time or now_utc(),
        reported_by=actor_id,
        **payload.model_dump(exclude={"event_time"}),
    )
    db.add(event)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action=f"trip.event.{payload.event_type}",
        entity_type="trip",
        entity_id=trip_id,
        new_values={"event_type": payload.event_type},
    )
    await db.commit()
    await db.refresh(event)
    return serialize_execution_event(event)


async def create_incident(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripIncidentCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    if payload.incident_type not in INCIDENT_TYPES:
        raise ApiError(
            "invalid_incident_type",
            "Invalid incident type.",
            status_code=422,
            details={"allowed": sorted(INCIDENT_TYPES), "value": payload.incident_type},
        )
    if payload.severity not in INCIDENT_SEVERITIES:
        raise ApiError(
            "invalid_incident_severity",
            "Invalid incident severity.",
            status_code=422,
            details={"allowed": sorted(INCIDENT_SEVERITIES), "value": payload.severity},
        )
    old_status = trip.status
    if payload.severity in {"high", "critical"} and trip.status in {
        "dispatched",
        "in_progress",
        "delayed",
    }:
        trip.status = "incident"

    incident = TripIncident(
        tenant_id=tenant_id,
        trip_id=trip.id,
        vehicle_id=trip.vehicle_id,
        driver_id=trip.driver_id,
        occurred_at=payload.occurred_at or now_utc(),
        reported_by=actor_id,
        **payload.model_dump(exclude={"occurred_at"}),
    )
    event = TripExecutionEvent(
        tenant_id=tenant_id,
        trip_id=trip.id,
        event_type="incident_reported",
        event_time=incident.occurred_at,
        location=incident.location,
        notes=incident.description,
        reported_by=actor_id,
        source="manual",
    )
    db.add_all([incident, event])
    await db.flush()
    if incident.incident_type == "breakdown":
        await create_breakdown_maintenance_request(
            db,
            tenant_id,
            trip=trip,
            incident=incident,
            actor_id=actor_id,
        )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.incident_reported",
        entity_type="trip_incident",
        entity_id=incident.id,
        old_values={"trip_status": old_status},
        new_values={
            "trip_status": trip.status,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
        },
    )
    await db.commit()
    await db.refresh(incident)
    return serialize_incident(incident)


async def resolve_incident(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    incident_id: UUID,
    payload: TripIncidentResolveRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_trip(db, tenant_id, trip_id)
    incident = await db.get(TripIncident, incident_id)
    if not incident or incident.tenant_id != tenant_id or incident.trip_id != trip_id:
        raise ApiError("incident_not_found", "Incident not found.", status_code=404)
    if incident.status in {"resolved", "closed"}:
        return serialize_incident(incident)

    old_values = {"status": incident.status}
    incident.status = "resolved"
    incident.resolution_notes = payload.resolution_notes
    incident.resolved_by = actor_id
    incident.resolved_at = payload.resolved_at or now_utc()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.incident_resolved",
        entity_type="trip_incident",
        entity_id=incident.id,
        old_values=old_values,
        new_values={"status": incident.status},
    )
    await db.commit()
    await db.refresh(incident)
    return serialize_incident(incident)


async def associate_contract(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: AssociateContractRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    contract = await db.get(Contract, payload.contract_id)
    if not contract or contract.tenant_id != tenant_id:
        raise ApiError("contract_not_found", "Contract not found.", status_code=404)

    old_values = {
        "contract_id": str(trip.contract_id) if trip.contract_id else None,
        "contract_reference": trip.contract_reference,
        "billing_status": trip.billing_status,
        "billable_at": trip.billable_at,
    }
    trip.contract_id = contract.id
    trip.contract_reference = contract.contract_reference
    if trip.billing_status == "uncontracted":
        trip.billing_status = "billable"
        trip.billable_at = now_utc()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.contract_associated",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_values,
        new_values={
            "contract_id": str(trip.contract_id),
            "contract_reference": trip.contract_reference,
            "billing_status": trip.billing_status,
            "billable_at": trip.billable_at,
        },
    )
    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)


async def create_stop(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripStopCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_trip(db, tenant_id, trip_id)
    stop = TripStop(
        tenant_id=tenant_id,
        trip_id=trip_id,
        stopped_at=payload.stopped_at or now_utc(),
        **payload.model_dump(exclude={"stopped_at"}),
    )
    db.add(stop)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.stop_created",
        entity_type="trip_stop",
        entity_id=stop.id,
        new_values={
            "trip_id": str(stop.trip_id),
            "stop_type": stop.stop_type,
            "stopped_at": stop.stopped_at,
            "cost": stop.cost,
        },
    )
    await db.commit()
    await db.refresh(stop)
    return {"id": stop.id, "trip_id": stop.trip_id, "stop_type": stop.stop_type}


async def complete_trip(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: CompleteTripRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status != "in_progress":
        raise ApiError(
            "invalid_trip_status",
            "Only in-progress trips can be completed.",
            status_code=409,
        )

    old_values = {
        "status": trip.status,
        "km_end": trip.km_end,
        "actual_arrival": trip.actual_arrival,
        "recipient_name": trip.recipient_name,
    }
    trip.km_end = payload.km_end
    trip.km_end_file_id = payload.km_end_file_id
    trip.actual_arrival = payload.actual_arrival or now_utc()
    trip.recipient_name = payload.recipient_name
    trip.status = "arrived"

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.completed",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_values,
        new_values={
            "status": trip.status,
            "km_end": trip.km_end,
            "actual_arrival": trip.actual_arrival,
            "recipient_name": trip.recipient_name,
        },
    )
    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)


async def operational_close_trip(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: OperationalCloseTripRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status == "closed":
        return serialize_trip(trip)
    if trip.status not in {"arrived", "delivered", "incident"}:
        raise ApiError(
            "invalid_trip_status",
            "Only arrived, delivered or incident trips can be operationally closed.",
            status_code=409,
            details={"status": trip.status},
        )

    open_blocking_incident = await db.scalar(
        select(TripIncident.id).where(
            TripIncident.tenant_id == tenant_id,
            TripIncident.trip_id == trip_id,
            TripIncident.status.in_(("open", "investigating")),
            TripIncident.severity.in_(("high", "critical")),
        )
    )
    if open_blocking_incident:
        raise ApiError(
            "open_blocking_incident",
            "Trip cannot be closed while high or critical incidents are open.",
            status_code=409,
            details={"incident_id": str(open_blocking_incident)},
        )

    validated_proof = await db.scalar(
        select(DeliveryProof.id).where(
            DeliveryProof.tenant_id == tenant_id,
            DeliveryProof.trip_id == trip_id,
            DeliveryProof.status == "validated",
        )
    )
    if not validated_proof:
        no_pod_waiver = await has_active_waiver(
            db,
            tenant_id,
            entity_type="trip",
            entity_id=trip_id,
            waiver_type="no_pod",
        )
        if not no_pod_waiver:
            raise ApiError(
                "validated_pod_required",
                "Trip cannot be closed without validated POD or active no_pod waiver.",
                status_code=409,
            )

    missing_required_stops = await _missing_required_trip_stops(db, tenant_id, trip)
    if missing_required_stops:
        raise ApiError(
            "required_trip_stops_missing",
            "Trip cannot be closed while mandatory stops are missing.",
            status_code=409,
            details={"missing_stops": missing_required_stops},
        )

    old_status = trip.status
    await reconcile_trip_costs(db, tenant_id, trip)
    trip.status = "closed"
    trip.billing_status = "billable" # Mark as ready for billing
    trip.closed_at = payload.closed_at or now_utc()
    trip.closed_by = actor_id
    trip.operational_close_notes = payload.notes
    if trip.trip_order_id:
        order = await db.get(TripOrder, trip.trip_order_id)
        if order and order.tenant_id == tenant_id:
            order.status = "closed"

    event = TripExecutionEvent(
        tenant_id=tenant_id,
        trip_id=trip.id,
        event_type="completed",
        event_time=trip.closed_at,
        notes=payload.notes,
        reported_by=actor_id,
        source="system",
    )
    db.add(event)
    closed_at = trip.closed_at
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.closed",
        entity_type="trip",
        entity_id=trip.id,
        old_values={"status": old_status},
        new_values={
            "status": trip.status,
            "closed_at": closed_at.isoformat() if closed_at is not None else None,
            "validated_proof_id": str(validated_proof) if validated_proof else None,
            "total_transport_cost": str(trip.total_transport_cost),
            "actual_margin": str(trip.actual_margin),
        },
    )
    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)


async def create_cost(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripCostCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    cost = await record_trip_cost(
        db,
        tenant_id,
        trip_id=trip_id,
        actor_id=actor_id,
        **payload.model_dump(),
    )
    await db.commit()
    await db.refresh(cost)
    return serialize_trip_cost(cost)


async def _trip_allowance_distance(
    db: AsyncSession,
    tenant_id: UUID,
    trip: Trip,
    override_distance_km: float | None,
) -> float:
    if override_distance_km is not None:
        if override_distance_km < 0:
            raise ApiError(
                "invalid_trip_distance",
                "Trip allowance distance cannot be negative.",
                status_code=422,
            )
        return override_distance_km

    if trip.trip_order_id:
        order = await db.get(TripOrder, trip.trip_order_id)
        if order and order.tenant_id == tenant_id and order.estimated_distance_km is not None:
            return float(order.estimated_distance_km)

    if trip.km_start is not None and trip.km_end is not None and trip.km_end >= trip.km_start:
        return float(trip.km_end - trip.km_start)

    raise ApiError(
        "trip_distance_required",
        "Trip distance is required to calculate driver despacho allowance.",
        status_code=422,
    )


async def record_driver_travel_allowance(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    payload: TripDriverAllowanceRecordRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    distance_km = await _trip_allowance_distance(db, tenant_id, trip, payload.distance_km)
    policy = await _tenant_compliance_policy(db, tenant_id)
    allowance_match = _driver_allowance_match(policy, distance_km)
    amount = allowance_match["amount"]
    if amount <= 0:
        raise ApiError(
            "driver_allowance_not_applicable",
            "Trip distance does not qualify for driver despacho allowance.",
            status_code=409,
            details={"distance_km": distance_km, "reason": allowance_match["reason"]},
        )
    allowance_policy = allowance_match["policy"]
    allowance_tier = allowance_match["tier"]

    cost = await record_trip_cost(
        db,
        tenant_id,
        trip_id=trip_id,
        actor_id=actor_id,
        cost_type="driver_despacho",
        description=payload.notes
        or (
            f"Despacho do motorista para viagem de {distance_km:g} km "
            f"pela {allowance_policy['table_name']}."
        ),
        amount=amount,
        currency=allowance_match["currency"],
        paid_by="company",
        payment_method="driver_allowance",
        request_reference=payload.request_reference
        or f"driver-despacho:{trip_id}:{round(distance_km, 2)}",
        incurred_at=payload.incurred_at or now_utc(),
        source_type="driver_despacho",
        source_id=trip_id,
    )
    await db.commit()
    await db.refresh(cost)
    return {
        **serialize_trip_cost(cost),
        "distance_km": distance_km,
        "allowance_amount": amount,
        "despacho_table": {
            "name": allowance_policy["table_name"],
            "reference": allowance_policy["table_reference"],
            "effective_from": allowance_policy.get("effective_from"),
            "currency": allowance_match["currency"],
            "source": allowance_policy["source"],
            "entry_mode": allowance_policy.get("entry_mode"),
        },
        "despacho_tier": allowance_tier,
    }


async def list_costs(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> list[dict]:
    await _require_trip(db, tenant_id, trip_id)
    result = await db.execute(
        select(TripCost).where(TripCost.tenant_id == tenant_id, TripCost.trip_id == trip_id)
    )
    return [serialize_trip_cost(cost) for cost in result.scalars()]


async def patch_trip(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    patch: TripPatch,
) -> dict:
    trip = await _require_trip(db, tenant_id, trip_id)
    patch_data = patch.model_dump(exclude_none=True)

    if "cargo_weight" in patch_data and patch_data["cargo_weight"] is not None:
        _vehicle = await db.get(Vehicle, trip.vehicle_id)
        override = patch_data.get("payload_override_reason") or trip.payload_override_reason
        if (
            _vehicle is not None
            and _vehicle.max_payload_kg is not None
            and patch_data["cargo_weight"] > _vehicle.max_payload_kg
            and not override
        ):
            excess = float(patch_data["cargo_weight"] - _vehicle.max_payload_kg)
            raise ApiError(
                "payload_exceeded",
                f"Cargo weight exceeds vehicle max payload capacity by {excess:.2f} kg.",
                status_code=409,
                details={
                    "cargo_weight_kg": float(patch_data["cargo_weight"]),
                    "max_payload_kg": float(_vehicle.max_payload_kg),
                    "excess_kg": excess,
                },
            )

    old_values = {f: getattr(trip, f, None) for f in patch_data}
    for field, value in patch_data.items():
        setattr(trip, field, value)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=None,
        action="trip.patched",
        entity_type="trip",
        entity_id=trip.id,
        old_values=old_values,
        new_values=patch_data,
    )
    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)


async def patch_stop(
    db: AsyncSession,
    tenant_id: UUID,
    stop_id: UUID,
    patch: TripStopPatch,
) -> dict:
    stop = await db.get(TripStop, stop_id)
    if not stop:
        raise ApiError("trip_stop_not_found", "Trip stop not found.", status_code=404)
    # Verify tenant isolation via the parent trip
    await _require_trip(db, tenant_id, stop.trip_id)
    patch_data = patch.model_dump(exclude_none=True)
    old_values = {f: getattr(stop, f, None) for f in patch_data}
    for field, value in patch_data.items():
        setattr(stop, field, value)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=None,
        action="trip_stop.patched",
        entity_type="trip_stop",
        entity_id=stop.id,
        old_values=old_values,
        new_values=patch_data,
    )
    await db.commit()
    await db.refresh(stop)
    return {
        "id": stop.id,
        "trip_id": stop.trip_id,
        "stop_type": stop.stop_type,
        "location": stop.location,
        "notes": stop.notes,
        "duration_minutes": getattr(stop, "duration_minutes", None),
        "arrived_at": getattr(stop, "arrived_at", None),
        "departed_at": getattr(stop, "departed_at", None),
    }


async def optimize_trip_route(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    from app.modules.trips import routing

    trip = await _require_trip(db, tenant_id, trip_id)

    # Fetch stops
    stmt = select(TripStop).where(TripStop.trip_id == trip.id, TripStop.tenant_id == tenant_id)
    res = await db.execute(stmt)
    stops = list(res.scalars().all())

    # Format stops for optimizer
    stops_payload = [{"id": s.id, "location": s.location, "instance": s} for s in stops]

    ordered_stops_payload = routing.optimize_waypoint_sequence(
        trip.origin_location,
        trip.destination_location,
        stops_payload,
    )

    # Update sequence numbers on stops
    for item in ordered_stops_payload:
        stop_obj = item["instance"]
        stop_obj.sequence_number = item["sequence_number"]

    # Build full list of waypoints for OSRM
    waypoints: list[dict[str, float]] = []
    if trip.origin_location and "lat" in trip.origin_location and "lon" in trip.origin_location:
        waypoints.append({"lat": float(trip.origin_location["lat"]), "lon": float(trip.origin_location["lon"])})

    for item in ordered_stops_payload:
        loc = item.get("location")
        if loc and "lat" in loc and "lon" in loc:
            waypoints.append({"lat": float(loc["lat"]), "lon": float(loc["lon"])})

    if trip.destination_location and "lat" in trip.destination_location and "lon" in trip.destination_location:
        waypoints.append(
            {
                "lat": float(trip.destination_location["lat"]),
                "lon": float(trip.destination_location["lon"]),
            }
        )

    route_data = await routing.fetch_osrm_route(waypoints)

    trip.route_geometry = route_data["geometry"]
    trip.route_polyline = route_data["polyline"]
    trip.route_distance_km = Decimal(str(route_data["distance_km"]))
    trip.route_duration_seconds = route_data["duration_seconds"]

    await db.commit()
    await db.refresh(trip)
    return serialize_trip(trip)
