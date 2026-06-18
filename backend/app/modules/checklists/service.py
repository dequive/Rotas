from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.checklists.schemas import (
    ChecklistCreate,
    ChecklistPatch,
    ChecklistTemplateCreate,
    CompleteChecklistRequest,
    ResolveChecklistFailureRequest,
)
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.service import ensure_exception, resolve_active_exceptions
from app.modules.vehicles.models import Vehicle


def serialize_template(template: ChecklistTemplate) -> dict:
    return {
        "id": template.id,
        "tenant_id": template.tenant_id,
        "name": template.name,
        "type": template.type,
        "category": template.category,
        "is_active": template.is_active,
        "items": template.items,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def serialize_checklist(checklist: Checklist, blocking_failures: list[dict] | None = None) -> dict:
    return {
        "id": checklist.id,
        "tenant_id": checklist.tenant_id,
        "vehicle_id": checklist.vehicle_id,
        "driver_id": checklist.driver_id,
        "template_id": checklist.template_id,
        "type": checklist.type,
        "status": checklist.status,
        "responses": checklist.responses,
        "location": checklist.location,
        "gps_accuracy_m": checklist.gps_accuracy_m,
        "gps_source": checklist.gps_source,
        "client_captured_at": checklist.client_captured_at,
        "server_received_at": checklist.server_received_at,
        "signature_file_id": checklist.signature_file_id,
        "started_at": checklist.started_at,
        "completed_at": checklist.completed_at,
        "duration_seconds": checklist.duration_seconds,
        "created_at": checklist.created_at,
        "blocking_failures": blocking_failures or [],
    }


async def _require_template(
    db: AsyncSession,
    tenant_id: UUID,
    template_id: UUID,
) -> ChecklistTemplate:
    template = await db.get(ChecklistTemplate, template_id)
    if not template or template.tenant_id != tenant_id:
        raise ApiError(
            "checklist_template_not_found",
            "Checklist template not found.",
            status_code=404,
        )
    return template


async def _require_checklist(db: AsyncSession, tenant_id: UUID, checklist_id: UUID) -> Checklist:
    checklist = await db.get(Checklist, checklist_id)
    if not checklist or checklist.tenant_id != tenant_id:
        raise ApiError("checklist_not_found", "Checklist not found.", status_code=404)
    return checklist


def _response_value(response):
    if isinstance(response, dict):
        if "value" in response:
            return response["value"]
        if "status" in response:
            return response["status"]
    return response


def _is_failure(response) -> bool:
    value = _response_value(response)
    if value is None:
        return True
    if isinstance(value, bool):
        return value is False
    if isinstance(value, str):
        return value.lower() in {"false", "fail", "failed", "nok", "missing", "em_falta"}
    return False


def _has_photo(response) -> bool:
    if not isinstance(response, dict):
        return False
    return bool(
        response.get("photo_file_id")
        or response.get("photoFileId")
        or response.get("photo_url")
        or response.get("photoUrl")
    )


def evaluate_blocking_failures(template: ChecklistTemplate, responses: dict) -> list[dict]:
    failures = []
    for item in template.items or []:
        item_id = item.get("id")
        if not item_id:
            continue

        response = responses.get(item_id)
        is_blocking = bool(item.get("is_blocking"))
        requires_photo = bool(item.get("requires_photo"))

        if is_blocking and _is_failure(response):
            failures.append(
                {
                    "item_id": item_id,
                    "label": item.get("label"),
                    "reason": "blocking_item_failed",
                }
            )
            continue

        if requires_photo and not _has_photo(response):
            failures.append(
                {
                    "item_id": item_id,
                    "label": item.get("label"),
                    "reason": "required_photo_missing",
                }
            )

    return failures


async def list_templates(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    type_filter: str | None = None,
    is_active: bool | None = True,
) -> list[dict]:
    query = select(ChecklistTemplate).where(ChecklistTemplate.tenant_id == tenant_id)
    if type_filter:
        query = query.where(ChecklistTemplate.type == type_filter)
    if is_active is not None:
        query = query.where(ChecklistTemplate.is_active == is_active)

    result = await db.execute(
        query.order_by(ChecklistTemplate.type.asc(), ChecklistTemplate.name.asc())
    )
    return [serialize_template(template) for template in result.scalars()]


async def create_template(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ChecklistTemplateCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    template = ChecklistTemplate(tenant_id=tenant_id, **payload.model_dump())
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="checklist_template.created",
        entity_type="checklist_template",
        entity_id=template.id,
        new_values=serialize_template(template),
    )
    await db.commit()
    await db.refresh(template)
    return serialize_template(template)


async def list_checklists(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Checklist).where(Checklist.tenant_id == tenant_id)
    if status_filter:
        query = query.where(Checklist.status == status_filter)
    if vehicle_id:
        query = query.where(Checklist.vehicle_id == vehicle_id)
    if driver_id:
        query = query.where(Checklist.driver_id == driver_id)

    result = await db.execute(
        query.order_by(Checklist.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_checklist(checklist) for checklist in result.scalars()]


async def create_checklist(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ChecklistCreate,
    *,
    actor_id: UUID | None = None,
    driver_actor_id: UUID | None = None,
) -> dict:
    template = await _require_template(db, tenant_id, payload.template_id)
    if not template.is_active:
        raise ApiError(
            "checklist_template_inactive",
            "Checklist template is inactive.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if template.type != payload.type:
        raise ApiError(
            "checklist_type_mismatch",
            "Checklist type does not match template type.",
            status_code=status.HTTP_409_CONFLICT,
            details={"template_type": template.type, "payload_type": payload.type},
        )

    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if (
        not vehicle
        or vehicle.tenant_id != tenant_id
        or vehicle.status not in {"active", "maintenance"}
    ):
        raise ApiError("vehicle_not_found", "Vehicle not found or inactive.", status_code=404)

    driver = await db.get(Driver, payload.driver_id)
    if not driver or driver.tenant_id != tenant_id or driver.status != "active":
        raise ApiError("driver_not_found", "Driver not found or inactive.", status_code=404)

    checklist = Checklist(
        tenant_id=tenant_id,
        status="in_progress",
        started_at=payload.started_at or payload.client_captured_at or datetime.now(UTC),
        **payload.model_dump(exclude={"started_at"}),
    )
    db.add(checklist)
    await db.flush()
    await db.refresh(checklist)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_actor_id,
        action="checklist.created",
        entity_type="checklist",
        entity_id=checklist.id,
        new_values=serialize_checklist(checklist),
    )
    await db.commit()
    await db.refresh(checklist)
    return serialize_checklist(checklist)


async def patch_checklist(
    db: AsyncSession,
    tenant_id: UUID,
    checklist_id: UUID,
    payload: ChecklistPatch,
    *,
    actor_id: UUID | None = None,
    driver_actor_id: UUID | None = None,
) -> dict:
    checklist = await _require_checklist(db, tenant_id, checklist_id)
    if checklist.status in {"completed", "failed"}:
        raise ApiError(
            "checklist_closed",
            "Completed or failed checklists cannot be patched.",
            status_code=status.HTTP_409_CONFLICT,
            details={"status": checklist.status},
        )

    old_values = serialize_checklist(checklist)
    values = payload.model_dump(exclude_unset=True)
    for field, value in values.items():
        setattr(checklist, field, value)

    await db.flush()
    await db.refresh(checklist)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_actor_id,
        action="checklist.updated",
        entity_type="checklist",
        entity_id=checklist.id,
        old_values=old_values,
        new_values=serialize_checklist(checklist),
    )
    await db.commit()
    await db.refresh(checklist)
    return serialize_checklist(checklist)


async def complete_checklist(
    db: AsyncSession,
    tenant_id: UUID,
    checklist_id: UUID,
    payload: CompleteChecklistRequest,
    *,
    actor_id: UUID | None = None,
    driver_actor_id: UUID | None = None,
) -> dict:
    checklist = await _require_checklist(db, tenant_id, checklist_id)
    if checklist.status in {"completed", "failed"}:
        return serialize_checklist(checklist)

    template = await _require_template(db, tenant_id, checklist.template_id)
    completed_at = payload.completed_at or datetime.now(UTC)
    failures = evaluate_blocking_failures(template, checklist.responses or {})

    checklist.completed_at = completed_at
    checklist.signature_file_id = payload.signature_file_id
    checklist.status = "failed" if failures else "completed"
    if checklist.started_at:
        checklist.duration_seconds = max(
            0,
            int((completed_at - checklist.started_at).total_seconds()),
        )

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_actor_id,
        action="checklist.completed",
        entity_type="checklist",
        entity_id=checklist.id,
        new_values={
            "status": checklist.status,
            "completed_at": checklist.completed_at,
            "duration_seconds": checklist.duration_seconds,
            "blocking_failures": failures,
        },
    )
    if failures:
        await ensure_exception(
            db,
            tenant_id,
            entity_type="checklist",
            entity_id=checklist.id,
            exception_type="checklist_failed",
            severity="high",
            title="Checklist operacional falhou",
            message="Checklist concluido com falhas bloqueantes ou fotos obrigatorias em falta.",
            actor_id=actor_id,
            context={
                "vehicle_id": str(checklist.vehicle_id),
                "driver_id": str(checklist.driver_id),
                "template_id": str(checklist.template_id),
                "failures": failures,
            },
            source_type="checklist",
            source_id=checklist.id,
        )
    await db.commit()
    await db.refresh(checklist)
    return serialize_checklist(checklist, failures)


async def resolve_checklist_failure(
    db: AsyncSession,
    tenant_id: UUID,
    checklist_id: UUID,
    payload: ResolveChecklistFailureRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    checklist = await _require_checklist(db, tenant_id, checklist_id)
    if checklist.status == "resolved":
        return serialize_checklist(checklist)
    if checklist.status != "failed":
        raise ApiError(
            "checklist_not_failed",
            "Only failed checklists can be resolved through this endpoint.",
            status_code=status.HTTP_409_CONFLICT,
            details={"status": checklist.status},
        )

    old_values = serialize_checklist(checklist)
    checklist.status = "resolved"
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="checklist.failure_resolved",
        entity_type="checklist",
        entity_id=checklist.id,
        old_values=old_values,
        new_values={
            "status": checklist.status,
            "resolution_notes": payload.resolution_notes,
            "resolved_at": payload.resolved_at or datetime.now(UTC),
        },
    )
    await resolve_active_exceptions(
        db,
        tenant_id,
        entity_type="checklist",
        entity_id=checklist.id,
        exception_type="checklist_failed",
        resolution_notes=payload.resolution_notes,
        actor_id=actor_id,
    )
    await db.commit()
    await db.refresh(checklist)
    return serialize_checklist(checklist)
