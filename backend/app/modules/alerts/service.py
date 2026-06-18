from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.alerts.models import Alert
from app.modules.alerts.schemas import AlertCreate, AlertStatusPatch
from app.modules.audit.service import record_audit_log

ALERT_PRIORITIES = {"low", "medium", "high", "critical"}
ALERT_CHANNELS = {"dashboard", "whatsapp", "email", "sms"}
ALERT_STATUSES = {"pending", "sent", "read", "dismissed"}


def serialize_alert(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "tenant_id": alert.tenant_id,
        "request_reference": alert.request_reference,
        "alert_type": alert.alert_type,
        "priority": alert.priority,
        "entity_type": alert.entity_type,
        "entity_id": alert.entity_id,
        "title": alert.title,
        "message": alert.message,
        "channel": alert.channel,
        "status": alert.status,
        "sent_at": alert.sent_at,
        "read_at": alert.read_at,
        "dismissed_at": alert.dismissed_at,
        "created_at": alert.created_at,
    }


def _validate_choice(value: str, allowed: set[str], code: str, field: str) -> None:
    if value not in allowed:
        raise ApiError(
            code,
            f"Alert {field} is not supported.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={f"allowed_{field}s": sorted(allowed)},
        )


async def _require_alert(db: AsyncSession, tenant_id: UUID, alert_id: UUID) -> Alert:
    alert = await db.get(Alert, alert_id)
    if not alert or alert.tenant_id != tenant_id:
        raise ApiError("alert_not_found", "Alert not found.", status_code=status.HTTP_404_NOT_FOUND)
    return alert


async def list_alerts(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    priority: str | None = None,
    alert_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Alert).where(Alert.tenant_id == tenant_id)
    if status_filter:
        query = query.where(Alert.status == status_filter)
    if priority:
        query = query.where(Alert.priority == priority)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    result = await db.execute(
        query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_alert(alert) for alert in result.scalars()]


async def create_alert(
    db: AsyncSession,
    tenant_id: UUID,
    payload: AlertCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    _validate_choice(payload.priority, ALERT_PRIORITIES, "invalid_alert_priority", "priority")
    _validate_choice(payload.channel, ALERT_CHANNELS, "invalid_alert_channel", "channel")
    existing = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.request_reference == payload.request_reference,
        )
    )
    payload_values = payload.model_dump()
    if existing:
        if all(getattr(existing, key) == value for key, value in payload_values.items()):
            return serialize_alert(existing)
        raise ApiError(
            "alert_request_reference_reused",
            "Alert request reference was already used with different values.",
            status_code=status.HTTP_409_CONFLICT,
            details={"request_reference": payload.request_reference},
        )

    alert = Alert(tenant_id=tenant_id, **payload_values)
    db.add(alert)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="alert.created",
        entity_type="alert",
        entity_id=alert.id,
        new_values=serialize_alert(alert),
    )
    await db.commit()
    await db.refresh(alert)
    return serialize_alert(alert)


async def patch_alert_status(
    db: AsyncSession,
    tenant_id: UUID,
    alert_id: UUID,
    payload: AlertStatusPatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    _validate_choice(payload.status, ALERT_STATUSES, "invalid_alert_status", "status")
    alert = await _require_alert(db, tenant_id, alert_id)
    if alert.status == payload.status:
        return serialize_alert(alert)
    old_values = serialize_alert(alert)
    alert.status = payload.status
    now = datetime.now(UTC)
    if payload.status == "sent":
        alert.sent_at = alert.sent_at or now
    elif payload.status == "read":
        alert.read_at = alert.read_at or now
    elif payload.status == "dismissed":
        alert.dismissed_at = alert.dismissed_at or now
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="alert.status_updated",
        entity_type="alert",
        entity_id=alert.id,
        old_values=old_values,
        new_values=serialize_alert(alert),
    )
    await db.commit()
    await db.refresh(alert)
    return serialize_alert(alert)
