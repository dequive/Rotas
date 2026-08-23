from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.alerts.models import Alert
from app.modules.audit.service import record_audit_log
from app.modules.governance.events import operational_exception_event
from app.modules.operational_exceptions.models import OperationalException
from app.modules.outbox.service import enqueue as enqueue_outbox

ACTIVE_STATUSES = {"open", "acknowledged"}
SEVERITIES = {"low", "medium", "high", "critical"}
DRIVER_DOCUMENT_REQUEST_PREFIX = "driver_doc_request:"


def driver_document_request_type(document_type: str) -> str:
    digest = sha256(document_type.encode("utf-8")).hexdigest()[:24]
    return f"{DRIVER_DOCUMENT_REQUEST_PREFIX}{digest}"


def serialize_exception(item: OperationalException) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "exception_type": item.exception_type,
        "severity": item.severity,
        "status": item.status,
        "title": item.title,
        "message": item.message,
        "context": item.context,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "acknowledged_by": item.acknowledged_by,
        "acknowledged_at": item.acknowledged_at,
        "resolved_by": item.resolved_by,
        "resolved_at": item.resolved_at,
        "resolution_notes": item.resolution_notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def ensure_exception(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str,
    entity_id: UUID,
    exception_type: str,
    severity: str,
    title: str,
    message: str,
    actor_id: UUID | None = None,
    driver_id: UUID | None = None,
    context: dict | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> OperationalException:
    if severity not in SEVERITIES:
        raise ApiError("invalid_exception_severity", "Invalid exception severity.", status_code=422)
    query = select(OperationalException).where(
        OperationalException.tenant_id == tenant_id,
        OperationalException.entity_type == entity_type,
        OperationalException.entity_id == entity_id,
        OperationalException.exception_type == exception_type,
        OperationalException.status.in_(ACTIVE_STATUSES),
    )
    if source_type:
        query = query.where(OperationalException.source_type == source_type)
    if source_id:
        query = query.where(OperationalException.source_id == source_id)
    existing = await db.scalar(query.order_by(OperationalException.created_at.desc()).limit(1))
    if existing:
        return existing

    item = OperationalException(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        exception_type=exception_type,
        severity=severity,
        title=title,
        message=message,
        context=context,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_id,
        action="operational_exception.created",
        entity_type=entity_type,
        entity_id=entity_id,
        new_values={
            "exception_id": str(item.id),
            "exception_type": exception_type,
            "severity": severity,
        },
    )
    alert = Alert(
        tenant_id=tenant_id,
        request_reference=f"exception:{item.id}",
        alert_type=exception_type,
        priority=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title[:160],
        message=message,
        channel="dashboard",
        status="pending",
    )
    db.add(alert)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_id,
        action="alert.created_from_exception",
        entity_type="alert",
        entity_id=alert.id,
        new_values={"exception_id": str(item.id), "alert_type": alert.alert_type},
    )

    # Persist high/critical events in the same transaction as the exception.
    # The outbox worker performs the network delivery after commit.
    if severity in {"high", "critical"}:
        payload = operational_exception_event(
            exception_id=item.id,
            exception_type=exception_type,
            severity=severity,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_display_name=str(entity_id),
            entity_attributes=context or {},
            tenant_id=tenant_id,
        )
        await enqueue_outbox(
            db,
            tenant_id=tenant_id,
            event_type=payload["event_type"],
            aggregate_type="operational_exception",
            aggregate_id=item.id,
            payload=payload,
        )

    return item


async def list_exceptions(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    exception_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = select(OperationalException).where(OperationalException.tenant_id == tenant_id)
    if status_filter:
        query = query.where(OperationalException.status == status_filter)
    if exception_type:
        query = query.where(OperationalException.exception_type == exception_type)
    result = await db.execute(query.order_by(OperationalException.created_at.desc()).limit(limit))
    return [serialize_exception(item) for item in result.scalars()]


async def acknowledge_exception(
    db: AsyncSession,
    tenant_id: UUID,
    exception_id: UUID,
    *,
    actor_id: UUID | None,
) -> dict:
    item = await _require_exception(db, tenant_id, exception_id)
    if item.status == "resolved":
        raise ApiError(
            "exception_already_resolved",
            "Exception is already resolved.",
            status_code=409,
        )
    if item.status == "acknowledged":
        return serialize_exception(item)
    item.status = "acknowledged"
    item.acknowledged_by = actor_id
    item.acknowledged_at = datetime.now(UTC)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_exception.acknowledged",
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        old_values={"status": "open"},
        new_values={"status": item.status, "exception_id": str(item.id)},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_exception(item)


async def resolve_exception(
    db: AsyncSession,
    tenant_id: UUID,
    exception_id: UUID,
    *,
    resolution_notes: str,
    actor_id: UUID | None,
) -> dict:
    item = await _require_exception(db, tenant_id, exception_id)
    if item.status == "resolved":
        return serialize_exception(item)
    old_status = item.status
    item.status = "resolved"
    item.resolved_by = actor_id
    item.resolved_at = datetime.now(UTC)
    item.resolution_notes = resolution_notes
    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.request_reference == f"exception:{item.id}",
        )
    )
    if alert and alert.status != "dismissed":
        old_alert_status = alert.status
        alert.status = "dismissed"
        alert.dismissed_at = item.resolved_at
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="alert.dismissed_from_exception",
            entity_type="alert",
            entity_id=alert.id,
            old_values={"status": old_alert_status},
            new_values={"status": alert.status, "exception_id": str(item.id)},
        )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_exception.resolved",
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        old_values={"status": old_status},
        new_values={
            "status": item.status,
            "exception_id": str(item.id),
            "resolution_notes": resolution_notes,
        },
    )
    await db.commit()
    await db.refresh(item)
    return serialize_exception(item)


async def resolve_active_exceptions(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str,
    entity_id: UUID,
    exception_type: str,
    resolution_notes: str,
    actor_id: UUID | None,
) -> list[OperationalException]:
    result = await db.execute(
        select(OperationalException).where(
            OperationalException.tenant_id == tenant_id,
            OperationalException.entity_type == entity_type,
            OperationalException.entity_id == entity_id,
            OperationalException.exception_type == exception_type,
            OperationalException.status.in_(ACTIVE_STATUSES),
        )
    )
    resolved: list[OperationalException] = []
    for item in result.scalars():
        old_status = item.status
        item.status = "resolved"
        item.resolved_by = actor_id
        item.resolved_at = datetime.now(UTC)
        item.resolution_notes = resolution_notes
        alert = await db.scalar(
            select(Alert).where(
                Alert.tenant_id == tenant_id,
                Alert.request_reference == f"exception:{item.id}",
            )
        )
        if alert and alert.status != "dismissed":
            old_alert_status = alert.status
            alert.status = "dismissed"
            alert.dismissed_at = item.resolved_at
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                user_id=actor_id,
                action="alert.dismissed_from_exception",
                entity_type="alert",
                entity_id=alert.id,
                old_values={"status": old_alert_status},
                new_values={"status": alert.status, "exception_id": str(item.id)},
            )
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="operational_exception.resolved",
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            old_values={"status": old_status},
            new_values={
                "status": item.status,
                "exception_id": str(item.id),
                "resolution_notes": resolution_notes,
            },
        )
        resolved.append(item)
    return resolved


async def _require_exception(
    db: AsyncSession,
    tenant_id: UUID,
    exception_id: UUID,
) -> OperationalException:
    item = await db.get(OperationalException, exception_id)
    if not item or item.tenant_id != tenant_id:
        raise ApiError("operational_exception_not_found", "Exception not found.", status_code=404)
    return item
