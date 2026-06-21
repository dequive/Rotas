from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.schemas import EmailNotificationCreate

NOTIFICATION_STATUSES = {"queued", "sent", "failed", "cancelled"}


def serialize_notification(item: NotificationOutbox) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "request_reference": item.request_reference,
        "channel": item.channel,
        "recipient": item.recipient,
        "subject": item.subject,
        "body_text": item.body_text,
        "body_html": item.body_html,
        "template": item.template,
        "payload": item.payload,
        "status": item.status,
        "attempts": item.attempts,
        "last_error": item.last_error,
        "scheduled_at": item.scheduled_at,
        "sent_at": item.sent_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def enqueue_email(
    db: AsyncSession,
    tenant_id: UUID,
    payload: EmailNotificationCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    existing = await db.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.tenant_id == tenant_id,
            NotificationOutbox.request_reference == payload.request_reference,
        )
    )
    values = payload.model_dump()
    if existing:
        expected = {**values, "channel": "email"}
        if all(getattr(existing, key) == value for key, value in expected.items()):
            return serialize_notification(existing)
        raise ApiError(
            "notification_request_reference_reused",
            "Notification request reference was already used with different values.",
            status_code=status.HTTP_409_CONFLICT,
            details={"request_reference": payload.request_reference},
        )

    item = NotificationOutbox(
        tenant_id=tenant_id,
        channel="email",
        status="queued",
        scheduled_at=datetime.now(UTC),
        **values,
    )
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="notification.email_queued",
        entity_type="notification_outbox",
        entity_id=item.id,
        new_values=serialize_notification(item),
    )
    return serialize_notification(item)


async def list_notifications(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status: str | None = None,
    channel: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    q = select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant_id)
    if status:
        q = q.where(NotificationOutbox.status == status)
    if channel:
        q = q.where(NotificationOutbox.channel == channel)
    q = q.order_by(NotificationOutbox.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [serialize_notification(n) for n in result.scalars().all()]


async def get_notification(
    db: AsyncSession,
    tenant_id: UUID,
    notification_id: UUID,
) -> dict:
    item = await db.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.id == notification_id,
            NotificationOutbox.tenant_id == tenant_id,
        )
    )
    if not item:
        raise ApiError(
            "notification_not_found",
            "Notification not found.",
            status_code=404,
        )
    return serialize_notification(item)
