from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import DriverPrincipal
from app.core.errors import ApiError
from app.core.idempotency import IDEMPOTENCY_TTL_DAYS, canonical_request_hash, ttl_for
from app.core.performance_diagnostics import measure_request_phase
from app.database import defer_session_commits
from app.modules.cargo import schemas as cargo_schemas
from app.modules.cargo import service as cargo_service
from app.modules.checklists import schemas as checklist_schemas
from app.modules.checklists import service as checklist_service
from app.modules.fuel import schemas as fuel_schemas
from app.modules.fuel import service as fuel_service
from app.modules.sync.models import IdempotencyKey, SyncEvent
from app.modules.sync.schemas import SyncBatchRequest, SyncOperation
from app.modules.trips import schemas as trip_schemas
from app.modules.trips import service as trip_service
from app.modules.trips.models import Trip

DRIVER_SYNC_POLICY: dict[str, frozenset[str]] = {
    "create": frozenset(
        {
            "checklist",
            "fuel_log",
            "trip_stop",
            "delivery_proof",
            "trip_cost",
        }
    ),
    "update": frozenset({"checklist", "fuel_log", "trip_stop", "delivery_proof"}),
}
ACTIVE_ASSIGNED_TRIP_STATUSES = frozenset(
    {"planned", "dispatch_pending", "dispatched", "in_progress", "delayed", "incident"}
)
DRIVER_TRIP_BOUND_CREATE_TYPES = frozenset({"trip_stop", "delivery_proof", "trip_cost"})
DRIVER_ASSET_BOUND_CREATE_TYPES = frozenset({"checklist", "fuel_log"})


def _snake_case(value: str) -> str:
    value = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        target_key = _snake_case(key)
        if isinstance(value, dict):
            normalized[target_key] = _normalize_payload(value)
        else:
            normalized[target_key] = value
    return normalized


def _payload_uuid(payload: dict[str, Any], key: str) -> UUID | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


async def _authorize_driver_trip_create(
    db: AsyncSession,
    principal: DriverPrincipal,
    operation: SyncOperation,
) -> dict | None:
    if (
        operation.operation != "create"
        or operation.entity_type not in DRIVER_TRIP_BOUND_CREATE_TYPES
    ):
        return None

    trip_id = _payload_uuid(_normalize_payload(operation.payload), "trip_id")
    trip_status = (
        await db.scalar(
            select(Trip.status).where(
                Trip.id == trip_id,
                Trip.tenant_id == principal.tenant_id,
                Trip.driver_id == principal.driver_id,
            )
        )
        if trip_id is not None
        else None
    )
    if trip_status is None:
        return _result(
            operation,
            status="failed",
            error_code="driver_trip_forbidden",
            message="Trip is not assigned to the authenticated driver.",
        )
    if trip_status not in ACTIVE_ASSIGNED_TRIP_STATUSES:
        return _result(
            operation,
            status="failed",
            error_code="driver_trip_not_active",
            message="Driver operations require an active assigned trip.",
        )
    return None


async def _authorize_driver_asset_create(
    db: AsyncSession,
    principal: DriverPrincipal,
    operation: SyncOperation,
) -> dict | None:
    if (
        operation.operation != "create"
        or operation.entity_type not in DRIVER_ASSET_BOUND_CREATE_TYPES
    ):
        return None

    payload = _normalize_payload(operation.payload)
    if str(payload.get("driver_id")) != str(principal.driver_id):
        return _result(
            operation,
            status="failed",
            error_code="driver_identity_mismatch",
            message="Operation driver does not match the authenticated driver.",
        )

    vehicle_id = _payload_uuid(payload, "vehicle_id")
    assigned_trip_id = (
        await db.scalar(
            select(Trip.id).where(
                Trip.tenant_id == principal.tenant_id,
                Trip.driver_id == principal.driver_id,
                Trip.vehicle_id == vehicle_id,
                Trip.status.in_(ACTIVE_ASSIGNED_TRIP_STATUSES),
            )
        )
        if vehicle_id is not None
        else None
    )
    if assigned_trip_id is None:
        return _result(
            operation,
            status="failed",
            error_code="driver_vehicle_forbidden",
            message="Vehicle is not assigned to the authenticated driver.",
        )
    return None


def _request_hash(operation: SyncOperation) -> str:
    raw = {
        "operation": operation.operation,
        "entity_type": operation.entity_type,
        "payload": operation.payload,
    }
    return canonical_request_hash(raw)


def _result(
    operation: SyncOperation,
    *,
    status: str,
    server_id: UUID | str | None = None,
    error_code: str | None = None,
    message: str | None = None,
) -> dict:
    return {
        "local_id": operation.local_id,
        "server_id": str(server_id) if server_id else None,
        "status": status,
        "entity_type": operation.entity_type,
        "error_code": error_code,
        "message": message,
    }


async def _dispatch_create(
    db: AsyncSession,
    tenant_id: UUID,
    operation: SyncOperation,
) -> dict:
    payload = _normalize_payload(operation.payload)
    entity_type = operation.entity_type

    if entity_type == "trip":
        created = await trip_service.create_trip(db, tenant_id, trip_schemas.TripCreate(**payload))
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "checklist":
        created = await checklist_service.create_checklist(
            db,
            tenant_id,
            checklist_schemas.ChecklistCreate(**payload),
        )
        if payload.get("complete") is True:
            completed = await checklist_service.complete_checklist(
                db,
                tenant_id,
                created["id"],
                checklist_schemas.CompleteChecklistRequest(),
            )
            return _result(operation, status="processed", server_id=completed["id"])
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "fuel_log":
        created = await fuel_service.create_fuel_log(
            db,
            tenant_id,
            fuel_schemas.FuelLogCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    trip_id = payload.pop("trip_id", None)
    if trip_id is None:
        return _result(
            operation,
            status="failed",
            error_code="trip_id_required",
            message="Sync operation requires trip_id.",
        )

    if entity_type == "trip_stop":
        created = await trip_service.create_stop(
            db,
            tenant_id,
            UUID(str(trip_id)),
            trip_schemas.TripStopCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "trip_cost":
        # `request_reference` is the domain dedup key for a cost: unique per
        # tenant, with its own reuse conflict. That is the same guarantee the
        # operation's idempotency key already carries, and the device generates
        # it once per queued record — so derive it rather than demand a second
        # key the driver app would have to invent.
        payload.setdefault("request_reference", f"sync:{operation.idempotency_key}")
        created = await trip_service.create_cost(
            db,
            tenant_id,
            UUID(str(trip_id)),
            trip_schemas.TripCostCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "load_permit":
        created = await cargo_service.create_load_permit(
            db,
            tenant_id,
            UUID(str(trip_id)),
            cargo_schemas.LoadPermitCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "cargo_manifest":
        created = await cargo_service.create_cargo_manifest(
            db,
            tenant_id,
            UUID(str(trip_id)),
            cargo_schemas.CargoManifestCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "transport_document":
        created = await cargo_service.create_transport_document(
            db,
            tenant_id,
            UUID(str(trip_id)),
            cargo_schemas.TransportDocumentCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    if entity_type == "delivery_proof":
        created = await cargo_service.create_delivery_proof(
            db,
            tenant_id,
            UUID(str(trip_id)),
            cargo_schemas.DeliveryProofCreate(**payload),
        )
        return _result(operation, status="processed", server_id=created["id"])

    return _result(
        operation,
        status="failed",
        error_code="unsupported_entity_type",
        message=f"Sync create is not implemented for {entity_type}.",
    )


async def _dispatch_update(
    db: AsyncSession,
    tenant_id: UUID,
    operation: SyncOperation,
) -> dict:
    payload = _normalize_payload(operation.payload)
    entity_type = operation.entity_type
    server_id = payload.pop("server_id", None) or payload.pop("id", None)

    if not server_id:
        return _result(
            operation,
            status="failed",
            error_code="server_id_required",
            message="Update operation requires server_id in payload.",
        )

    entity_uuid = UUID(str(server_id))

    try:
        if entity_type == "checklist":
            patch = checklist_schemas.ChecklistPatch(
                **{
                    k: v
                    for k, v in payload.items()
                    if k in checklist_schemas.ChecklistPatch.model_fields
                }
            )
            updated = await checklist_service.patch_checklist(db, tenant_id, entity_uuid, patch)
            return _result(operation, status="processed", server_id=updated["id"])

        if entity_type == "trip":
            patch = trip_schemas.TripPatch(
                **{k: v for k, v in payload.items() if k in trip_schemas.TripPatch.model_fields}
            )
            updated = await trip_service.patch_trip(db, tenant_id, entity_uuid, patch)
            return _result(operation, status="processed", server_id=updated["id"])

        if entity_type == "fuel_log":
            patch = fuel_schemas.FuelLogPatch(
                **{k: v for k, v in payload.items() if k in fuel_schemas.FuelLogPatch.model_fields}
            )
            updated = await fuel_service.patch_fuel_log(db, tenant_id, entity_uuid, patch)
            return _result(operation, status="processed", server_id=updated["id"])

        if entity_type == "trip_stop":
            patch = trip_schemas.TripStopPatch(
                **{k: v for k, v in payload.items() if k in trip_schemas.TripStopPatch.model_fields}
            )
            updated = await trip_service.patch_stop(db, tenant_id, entity_uuid, patch)
            return _result(operation, status="processed", server_id=updated["id"])

        if entity_type == "delivery_proof":
            updated = await cargo_service.patch_delivery_proof(db, tenant_id, entity_uuid, payload)
            return _result(operation, status="processed", server_id=updated["id"])

    except Exception as exc:
        error_code = getattr(exc, "error_code", "update_failed")
        message = getattr(exc, "message", str(exc))
        return _result(
            operation,
            status="failed",
            error_code=error_code,
            message=message,
        )

    return _result(
        operation,
        status="failed",
        error_code="unsupported_entity_type_for_update",
        message=f"Sync update is not implemented for {entity_type}.",
    )


async def _dispatch_operation(
    db: AsyncSession,
    tenant_id: UUID,
    operation: SyncOperation,
) -> dict:
    if operation.operation == "create":
        return await _dispatch_create(db, tenant_id, operation)
    if operation.operation == "update":
        return await _dispatch_update(db, tenant_id, operation)
    return _result(
        operation,
        status="failed",
        error_code="unsupported_operation",
        message=f"Sync operation {operation.operation} is not implemented.",
    )


async def _record_event(
    db: AsyncSession,
    principal: DriverPrincipal,
    payload: SyncBatchRequest,
    operation: SyncOperation,
    result: dict,
) -> None:
    db.add(
        SyncEvent(
            tenant_id=principal.tenant_id,
            driver_id=principal.driver_id,
            device_id=payload.device_id,
            idempotency_key=operation.idempotency_key,
            operation=operation.operation,
            entity_type=operation.entity_type,
            local_id=operation.local_id,
            server_id=UUID(result["server_id"]) if result.get("server_id") else None,
            payload=operation.payload,
            status=result["status"],
            error_code=result.get("error_code"),
            error_message=result.get("message"),
            processed_at=datetime.now(UTC),
        )
    )


logger = logging.getLogger(__name__)


async def _dispatch_failed_safe(
    db: AsyncSession,
    principal: DriverPrincipal,
    operation: SyncOperation,
    *,
    defer_commit: bool,
) -> dict:
    """Dispatch one operation so that its failure cannot take the batch with it.

    A driver's queue is built offline over hours. If one operation the server
    cannot accept — a field an older installed client does not send, an entity
    that no longer exists, a schema that moved on — aborted the request, every
    record captured that day would be stuck behind it and retried forever. That
    is the precise situation the offline guarantee exists for, so the failure is
    reported per operation instead.

    Isolation differs by mode, because the transaction does:

    - batch: every operation shares one transaction and the domain services'
      commits are deferred to flushes, so a SAVEPOINT contains a half-applied
      write without discarding the operations already processed.
    - single: the operation owns the transaction, so a plain rollback is both
      sufficient and correct. A SAVEPOINT would not survive here — the services
      commit internally, which closes it.

    The driver PWA already models this: `apps/driver/src/sync.ts` types the
    result status as processed | conflict | failed and routes failures to the
    dead-letter queue.
    """
    if (
        principal.scope == "driver_app"
        and operation.entity_type
        not in DRIVER_SYNC_POLICY.get(operation.operation, frozenset())
    ):
        return _result(
            operation,
            status="failed",
            error_code="driver_operation_forbidden",
            message="This operation is managed by fleet dispatch.",
        )

    if principal.scope == "driver_app":
        authorization_error = await _authorize_driver_trip_create(db, principal, operation)
        if authorization_error is not None:
            return authorization_error
        authorization_error = await _authorize_driver_asset_create(db, principal, operation)
        if authorization_error is not None:
            return authorization_error

    savepoint = await db.begin_nested() if defer_commit else None

    try:
        result = await _dispatch_operation(db, principal.tenant_id, operation)
    except Exception as exc:  # noqa: BLE001 - one operation must never abort the batch
        if savepoint is not None and savepoint.is_active:
            await savepoint.rollback()
        elif savepoint is None:
            await db.rollback()

        if isinstance(exc, ValidationError):
            first = exc.errors()[0] if exc.errors() else {}
            field = ".".join(str(part) for part in first.get("loc", ())) or "payload"
            return _result(
                operation,
                status="failed",
                error_code="payload_validation_failed",
                message=f"{field}: {first.get('msg', 'invalid payload')}",
            )
        if isinstance(exc, ApiError):
            return _result(
                operation,
                status="failed",
                error_code=exc.code,
                message=exc.message,
            )
        logger.exception(
            "sync_operation_failed entity_type=%s local_id=%s",
            operation.entity_type,
            operation.local_id,
        )
        return _result(
            operation,
            status="failed",
            error_code="sync_operation_failed",
            message="The server could not process this operation.",
        )

    if savepoint is not None and savepoint.is_active:
        await savepoint.commit()
    return result


async def _process_operation(
    db: AsyncSession,
    principal: DriverPrincipal,
    payload: SyncBatchRequest,
    operation: SyncOperation,
    *,
    defer_commit: bool = False,
    existing_by_key: dict[str, IdempotencyKey] | None = None,
) -> dict:
    request_hash = _request_hash(operation)
    if existing_by_key is None:
        with measure_request_phase("sync_idempotency"):
            existing = await db.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.tenant_id == principal.tenant_id,
                    IdempotencyKey.idempotency_key == operation.idempotency_key,
                )
            )
    else:
        existing = existing_by_key.get(operation.idempotency_key)
    if existing:
        if existing.request_hash != request_hash:
            result = _result(
                operation,
                status="conflict",
                error_code="idempotency_key_reused",
                message="Idempotency key was reused with a different payload.",
            )
            await _record_event(db, principal, payload, operation, result)
            return result
        cached = existing.response_body or {}
        return {
            **cached,
            "message": cached.get("message") or "idempotent_replay",
        }

    with measure_request_phase("sync_dispatch"):
        result = await _dispatch_failed_safe(
            db, principal, operation, defer_commit=defer_commit
        )
    response_body = jsonable_encoder(result)
    idempotency = IdempotencyKey(
        tenant_id=principal.tenant_id,
        driver_id=principal.driver_id,
        device_id=payload.device_id,
        idempotency_key=operation.idempotency_key,
        operation=operation.operation,
        entity_type=operation.entity_type,
        entity_id=UUID(result["server_id"]) if result.get("server_id") else None,
        request_hash=request_hash,
        response_body=response_body,
        status_code=200 if result["status"] == "processed" else 422,
        expires_at=datetime.now(UTC) + timedelta(days=ttl_for(operation.entity_type)),
    )
    db.add(idempotency)
    if existing_by_key is not None:
        existing_by_key[operation.idempotency_key] = idempotency
    await _record_event(db, principal, payload, operation, result)

    if defer_commit:
        with measure_request_phase("sync_flush"):
            await db.flush()
        return result

    try:
        with measure_request_phase("sync_commit"):
            await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == principal.tenant_id,
                IdempotencyKey.idempotency_key == operation.idempotency_key,
            )
        )
        if existing and existing.request_hash == request_hash:
            return {
                **(existing.response_body or {}),
                "message": "idempotent_replay",
            }
        return _result(
            operation,
            status="conflict",
            error_code="idempotency_race_conflict",
            message="Idempotency key conflict detected during concurrent sync.",
        )

    return result


async def process_batch(
    db: AsyncSession,
    payload: SyncBatchRequest,
    principal: DriverPrincipal,
) -> dict:
    if len(payload.operations) <= 1:
        results = [
            await _process_operation(db, principal, payload, operation)
            for operation in payload.operations
        ]
        return {"results": results}

    try:
        operation_keys = {
            operation.idempotency_key for operation in payload.operations
        }
        with measure_request_phase("sync_idempotency"):
            existing_rows = (
                await db.scalars(
                    select(IdempotencyKey).where(
                        IdempotencyKey.tenant_id == principal.tenant_id,
                        IdempotencyKey.idempotency_key.in_(operation_keys),
                    )
                )
            ).all()
        existing_by_key = {
            row.idempotency_key: row for row in existing_rows
        }
        # Domain services historically call commit internally. During a batch,
        # those commits become flushes so all operations share one transaction.
        # This removes N commits without changing the services' standalone API.
        with defer_session_commits(db):
            results = [
                await _process_operation(
                    db,
                    principal,
                    payload,
                    operation,
                    defer_commit=True,
                    existing_by_key=existing_by_key,
                )
                for operation in payload.operations
            ]
        with measure_request_phase("sync_commit"):
            await db.commit()
        return {"results": results}
    except IntegrityError:
        # A competing batch may win an idempotency-key race during the single
        # outer commit. Roll back all local effects, then use the established
        # per-operation replay path to reconcile safely.
        await db.rollback()
        results = [
            await _process_operation(db, principal, payload, operation)
            for operation in payload.operations
        ]
        return {"results": results}


async def bootstrap(principal: DriverPrincipal) -> dict:
    return {
        "tenant_id": principal.tenant_id,
        "server_time": datetime.now(UTC),
        "supported_entity_types": sorted(set().union(*DRIVER_SYNC_POLICY.values())),
        "supported_operations": ["create", "update"],
        "supported_operations_by_entity": {
            entity_type: sorted(
                operation
                for operation, entity_types in DRIVER_SYNC_POLICY.items()
                if entity_type in entity_types
            )
            for entity_type in sorted(set().union(*DRIVER_SYNC_POLICY.values()))
        },
        "idempotency_ttl_days": IDEMPOTENCY_TTL_DAYS,
    }
