from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.cargo.models import CargoManifest, LoadPermit, TransportDocument
from app.modules.checklists import service as checklists_service
from app.modules.checklists.models import Checklist
from app.modules.driver_app.schemas import DriverDocumentRequestCreate
from app.modules.drivers.models import DriverAdvance
from app.modules.files import service as files_service
from app.modules.fuel.models import FuelLog
from app.modules.operational_exceptions import service as exceptions_service
from app.modules.operational_exceptions.models import OperationalException
from app.modules.trips import service as trips_service
from app.modules.trips.models import Trip, TripCost

ACTIVE_DRIVER_TRIP_STATUSES = (
    "planned",
    "dispatch_pending",
    "dispatched",
    "in_progress",
    "delayed",
    "incident",
)

ASSIGNED_DRIVER_TRIP_STATUSES = (
    *ACTIVE_DRIVER_TRIP_STATUSES,
    "arrived",
    "delivered",
)

DRIVER_TRIP_HISTORY_STATUSES = ("closed", "cancelled")
DRIVER_TRIP_TERMINAL_STATUSES = frozenset(DRIVER_TRIP_HISTORY_STATUSES)
DRIVER_DOCUMENT_REQUEST_PREFIX = exceptions_service.DRIVER_DOCUMENT_REQUEST_PREFIX


def _serialize_driver_trip(trip: Trip) -> dict:
    return {
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "driver_id": trip.driver_id,
        "origin": trip.origin,
        "destination": trip.destination,
        "cargo_type": trip.cargo_type,
        "cargo_class": trip.cargo_class,
        "cargo_weight": float(trip.cargo_weight) if trip.cargo_weight is not None else None,
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
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def _serialize_driver_template(template: dict) -> dict:
    return {
        key: template[key]
        for key in (
            "id",
            "name",
            "type",
            "category",
            "is_active",
            "items",
            "created_at",
            "updated_at",
        )
    }


async def list_driver_checklist_templates(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    templates = await checklists_service.list_templates(
        db,
        tenant_id,
        type_filter="pre_partida",
        is_active=True,
    )
    return [_serialize_driver_template(template) for template in templates]


async def get_active_driver_trip(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
) -> dict | None:
    trip = await db.scalar(
        select(Trip)
        .where(
            Trip.tenant_id == tenant_id,
            Trip.driver_id == driver_id,
            Trip.status.in_(ACTIVE_DRIVER_TRIP_STATUSES),
        )
        .order_by(Trip.created_at.desc())
        .limit(1)
    )
    if trip is None:
        return None
    return _serialize_driver_trip(trip)


async def _list_driver_trips_by_status(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    statuses: tuple[str, ...],
    limit: int,
    offset: int,
) -> dict:
    ownership_filter = (
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
        Trip.status.in_(statuses),
    )
    total = await db.scalar(select(func.count(Trip.id)).where(*ownership_filter))
    trips = (
        await db.scalars(
            select(Trip)
            .where(*ownership_filter)
            .order_by(Trip.updated_at.desc(), Trip.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_serialize_driver_trip(trip) for trip in trips],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


async def list_assigned_driver_trips(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    limit: int,
    offset: int,
) -> dict:
    return await _list_driver_trips_by_status(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        statuses=ASSIGNED_DRIVER_TRIP_STATUSES,
        limit=limit,
        offset=offset,
    )


async def list_driver_trip_history(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    limit: int,
    offset: int,
) -> dict:
    return await _list_driver_trips_by_status(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        statuses=DRIVER_TRIP_HISTORY_STATUSES,
        limit=limit,
        offset=offset,
    )


def _serialize_driver_checklist_record(record: Checklist) -> dict:
    return {
        "id": record.id,
        "trip_id": record.trip_id,
        "vehicle_id": record.vehicle_id,
        "checklist_type": record.type,
        "status": record.status,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "created_at": record.created_at,
    }


async def list_driver_checklist_records(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID | None,
    limit: int,
    offset: int,
) -> dict:
    if trip_id is not None:
        await _require_owned_driver_trip(
            db,
            tenant_id=tenant_id,
            driver_id=driver_id,
            trip_id=trip_id,
        )

    trip_join = and_(
        Trip.tenant_id == Checklist.tenant_id,
        Trip.id == Checklist.trip_id,
    )
    ownership_filter = [
        Checklist.tenant_id == tenant_id,
        Checklist.driver_id == driver_id,
        or_(Checklist.trip_id.is_(None), Trip.driver_id == driver_id),
    ]
    if trip_id is not None:
        ownership_filter.append(Checklist.trip_id == trip_id)

    total = await db.scalar(
        select(func.count(Checklist.id))
        .select_from(Checklist)
        .outerjoin(Trip, trip_join)
        .where(*ownership_filter)
    )
    records = (
        await db.scalars(
            select(Checklist)
            .outerjoin(Trip, trip_join)
            .where(*ownership_filter)
            .order_by(
                func.coalesce(
                    Checklist.completed_at,
                    Checklist.started_at,
                    Checklist.created_at,
                ).desc(),
                Checklist.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_serialize_driver_checklist_record(record) for record in records],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


def _serialize_driver_fuel_record(record: FuelLog) -> dict:
    return {
        "id": record.id,
        "trip_id": record.trip_id,
        "vehicle_id": record.vehicle_id,
        "fuel_date": record.fuel_date,
        "station_name": record.station_name,
        "fuel_type": record.fuel_type,
        "liters": record.liters,
        "total_cost": record.total_cost,
        "km_at_refuel": record.km_at_refuel,
        "has_receipt": record.receipt_file_id is not None,
        "is_verified": record.is_verified,
        "is_flagged": record.flagged,
        "created_at": record.created_at,
    }


async def list_driver_fuel_records(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID | None,
    limit: int,
    offset: int,
) -> dict:
    if trip_id is not None:
        await _require_owned_driver_trip(
            db,
            tenant_id=tenant_id,
            driver_id=driver_id,
            trip_id=trip_id,
        )

    trip_join = and_(
        Trip.tenant_id == FuelLog.tenant_id,
        Trip.id == FuelLog.trip_id,
    )
    ownership_filter = [
        FuelLog.tenant_id == tenant_id,
        FuelLog.driver_id == driver_id,
        or_(FuelLog.trip_id.is_(None), Trip.driver_id == driver_id),
    ]
    if trip_id is not None:
        ownership_filter.append(FuelLog.trip_id == trip_id)

    total = await db.scalar(
        select(func.count(FuelLog.id))
        .select_from(FuelLog)
        .outerjoin(Trip, trip_join)
        .where(*ownership_filter)
    )
    records = (
        await db.scalars(
            select(FuelLog)
            .outerjoin(Trip, trip_join)
            .where(*ownership_filter)
            .order_by(FuelLog.fuel_date.desc(), FuelLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_serialize_driver_fuel_record(record) for record in records],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


def _serialize_driver_expense_record(record: TripCost) -> dict:
    return {
        "id": record.id,
        "trip_id": record.trip_id,
        "expense_type": record.cost_type,
        "description": record.description,
        "amount": record.amount,
        "currency": record.currency,
        "payment_method": record.payment_method,
        "has_receipt": record.receipt_file_id is not None,
        "entry_type": record.entry_type,
        "corrects_id": record.corrects_id,
        "correction_reason": record.correction_reason,
        "recorded_by_type": record.recorded_by_type,
        "incurred_at": record.incurred_at,
        "created_at": record.created_at,
    }


async def list_driver_expense_records(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID | None,
    limit: int,
    offset: int,
) -> dict:
    if trip_id is not None:
        await _require_owned_driver_trip(
            db,
            tenant_id=tenant_id,
            driver_id=driver_id,
            trip_id=trip_id,
        )

    ownership_filter = [
        TripCost.tenant_id == tenant_id,
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
        TripCost.driver_id == driver_id,
        TripCost.driver_visibility == "visible",
    ]
    if trip_id is not None:
        ownership_filter.append(TripCost.trip_id == trip_id)

    total = await db.scalar(
        select(func.count(TripCost.id))
        .select_from(TripCost)
        .join(Trip, Trip.id == TripCost.trip_id)
        .where(*ownership_filter)
    )
    records = (
        await db.scalars(
            select(TripCost)
            .join(Trip, Trip.id == TripCost.trip_id)
            .where(*ownership_filter)
            .order_by(TripCost.incurred_at.desc(), TripCost.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_serialize_driver_expense_record(record) for record in records],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


def _serialize_driver_advance_record(record: DriverAdvance) -> dict:
    return {
        "id": record.id,
        "trip_id": record.trip_id,
        "total_amount": record.amount_mzn,
        "allowance_amount": record.allowance_mzn,
        "expense_amount": record.expenses_mzn,
        "currency": record.currency,
        "status": record.status,
        "issued_at": record.issued_at,
    }


async def list_driver_advance_records(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID | None,
    limit: int,
    offset: int,
) -> dict:
    if trip_id is not None:
        await _require_owned_driver_trip(
            db,
            tenant_id=tenant_id,
            driver_id=driver_id,
            trip_id=trip_id,
        )

    ownership_filter = [
        DriverAdvance.tenant_id == tenant_id,
        DriverAdvance.driver_id == driver_id,
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
    ]
    if trip_id is not None:
        ownership_filter.append(DriverAdvance.trip_id == trip_id)

    total = await db.scalar(
        select(func.count(DriverAdvance.id))
        .select_from(DriverAdvance)
        .join(Trip, Trip.id == DriverAdvance.trip_id)
        .where(*ownership_filter)
    )
    records = (
        await db.scalars(
            select(DriverAdvance)
            .join(Trip, Trip.id == DriverAdvance.trip_id)
            .where(*ownership_filter)
            .order_by(DriverAdvance.issued_at.desc(), DriverAdvance.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_serialize_driver_advance_record(record) for record in records],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


async def _require_owned_driver_trip(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID,
    for_update: bool = False,
) -> Trip:
    query = select(Trip).where(
        Trip.id == trip_id,
        Trip.tenant_id == tenant_id,
        Trip.driver_id == driver_id,
    )
    if for_update:
        query = query.with_for_update()
    trip = await db.scalar(query)
    if trip is None:
        raise ApiError("driver_trip_not_found", "Viagem não encontrada.", status_code=404)
    return trip


def _serialize_driver_document(
    document: LoadPermit | CargoManifest | TransportDocument,
) -> dict:
    if isinstance(document, LoadPermit):
        document_type = "load_permit"
        document_number = document.permit_number
        issued_at = document.created_at
    elif isinstance(document, CargoManifest):
        document_type = "cargo_manifest"
        document_number = document.manifest_number
        issued_at = document.issued_at or document.created_at
    else:
        document_type = document.document_type
        document_number = document.document_number
        issued_at = document.issued_at or document.created_at
    return {
        "id": document.id,
        "document_type": document_type,
        "document_number": document_number,
        "status": document.status,
        "file_id": document.file_id,
        "issued_at": issued_at,
    }


def _serialize_driver_document_request(item: OperationalException) -> dict:
    context = item.context or {}
    return {
        "id": item.id,
        "trip_id": item.entity_id,
        "document_type": context.get("document_type")
        or item.exception_type.removeprefix(DRIVER_DOCUMENT_REQUEST_PREFIX),
        "status": item.status,
        "note": context.get("note"),
        "created_at": item.created_at,
    }


async def get_driver_trip_documents(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID,
) -> dict:
    trip = await _require_owned_driver_trip(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        trip_id=trip_id,
    )
    requirement_status = await trips_service.get_trip_document_requirements(
        db, tenant_id, trip
    )
    load_permits = (
        await db.scalars(
            select(LoadPermit).where(
                LoadPermit.tenant_id == tenant_id,
                LoadPermit.trip_id == trip.id,
                LoadPermit.status != "cancelled",
            )
        )
    ).all()
    manifests = (
        await db.scalars(
            select(CargoManifest).where(
                CargoManifest.tenant_id == tenant_id,
                CargoManifest.trip_id == trip.id,
                CargoManifest.status != "cancelled",
            )
        )
    ).all()
    transport_documents = (
        await db.scalars(
            select(TransportDocument).where(
                TransportDocument.tenant_id == tenant_id,
                TransportDocument.trip_id == trip.id,
                TransportDocument.status != "cancelled",
            )
        )
    ).all()
    requests = (
        await db.scalars(
            select(OperationalException)
            .where(
                OperationalException.tenant_id == tenant_id,
                OperationalException.entity_type == "trip",
                OperationalException.entity_id == trip.id,
                OperationalException.exception_type.like(
                    f"{DRIVER_DOCUMENT_REQUEST_PREFIX}%"
                ),
                OperationalException.source_type == "driver_app",
                OperationalException.source_id == driver_id,
            )
            .order_by(OperationalException.created_at.desc())
            .limit(100)
        )
    ).all()
    documents = [
        _serialize_driver_document(document)
        for document in (*load_permits, *manifests, *transport_documents)
    ]
    return {
        "trip_id": trip.id,
        **requirement_status,
        "can_request": trip.status not in DRIVER_TRIP_TERMINAL_STATUSES,
        "documents": documents,
        "requests": [_serialize_driver_document_request(item) for item in requests],
    }


async def get_driver_trip_document_file(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID,
    file_id: UUID,
):
    trip = await _require_owned_driver_trip(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        trip_id=trip_id,
    )
    attached = False
    for model in (LoadPermit, CargoManifest, TransportDocument):
        document_id = await db.scalar(
            select(model.id).where(
                model.tenant_id == tenant_id,
                model.trip_id == trip.id,
                model.file_id == file_id,
                model.status != "cancelled",
            )
        )
        if document_id is not None:
            attached = True
            break
    if not attached:
        raise ApiError(
            "driver_document_file_not_found",
            "Ficheiro do documento não encontrado.",
            status_code=404,
        )
    return await files_service.get_file_download_target(db, tenant_id, file_id)


async def request_driver_trip_document(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    trip_id: UUID,
    payload: DriverDocumentRequestCreate,
) -> dict:
    trip = await _require_owned_driver_trip(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        trip_id=trip_id,
        for_update=True,
    )
    if trip.status in DRIVER_TRIP_TERMINAL_STATUSES:
        raise ApiError(
            "driver_trip_read_only",
            "A viagem fechada ou cancelada é somente leitura.",
            status_code=409,
        )
    document_type = payload.document_type.strip().casefold()
    requirement_status = await trips_service.get_trip_document_requirements(
        db, tenant_id, trip
    )
    requirements = {
        item["document_type"]: item["present"]
        for item in requirement_status["requirements"]
    }
    if document_type not in requirements:
        raise ApiError(
            "driver_document_not_required",
            "O documento não é requisito desta viagem.",
            status_code=422,
        )
    if requirements[document_type]:
        raise ApiError(
            "driver_document_already_available",
            "O documento solicitado já está disponível.",
            status_code=409,
        )
    item = await exceptions_service.ensure_exception(
        db,
        tenant_id,
        entity_type="trip",
        entity_id=trip.id,
        exception_type=exceptions_service.driver_document_request_type(document_type),
        severity="medium",
        title="Documento solicitado pelo motorista",
        message=f"O motorista solicitou o documento em falta: {document_type}.",
        driver_id=driver_id,
        context={
            "document_type": document_type,
            "note": payload.note,
            "driver_id": str(driver_id),
        },
        source_type="driver_app",
        source_id=driver_id,
    )
    await db.commit()
    await db.refresh(item)
    return _serialize_driver_document_request(item)


async def get_bootstrap_payload(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    device_id: str | None,
) -> dict:
    return {
        "profile": {
            "tenant_id": tenant_id,
            "driver_id": driver_id,
            "device_id": device_id,
        },
        "checklistTemplates": await list_driver_checklist_templates(db, tenant_id),
        "activeTrip": await get_active_driver_trip(db, tenant_id, driver_id),
        # Transitional field for old clients. The assigned trip, not a fleet
        # selector, is the Driver app's source of vehicle identity.
        "vehicles": [],
    }
