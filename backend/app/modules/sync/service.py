from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import IDEMPOTENCY_TTL_DAYS, canonical_request_hash, ttl_for
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
    principal: Principal,
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


async def _process_operation(
    db: AsyncSession,
    principal: Principal,
    payload: SyncBatchRequest,
    operation: SyncOperation,
) -> dict:
    request_hash = _request_hash(operation)
    existing = await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == principal.tenant_id,
            IdempotencyKey.idempotency_key == operation.idempotency_key,
        )
    )
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

    result = await _dispatch_operation(db, principal.tenant_id, operation)
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
    await _record_event(db, principal, payload, operation, result)

    try:
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
    principal: Principal,
) -> dict:
    results = []
    for operation in payload.operations:
        results.append(await _process_operation(db, principal, payload, operation))
    return {"results": results}


async def bootstrap(principal: Principal) -> dict:
    return {
        "tenant_id": principal.tenant_id,
        "server_time": datetime.now(UTC),
        "supported_entity_types": [
            "trip",
            "checklist",
            "fuel_log",
            "trip_stop",
            "load_permit",
            "cargo_manifest",
            "transport_document",
            "delivery_proof",
            "trip_cost",
        ],
        "supported_operations": ["create", "update"],
        "idempotency_ttl_days": IDEMPOTENCY_TTL_DAYS,
    }
