from datetime import datetime
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_request_id
from app.modules.audit.models import AuditLog


async def record_audit_log(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        driver_id=driver_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=jsonable_encoder(old_values) if old_values is not None else None,
        new_values=jsonable_encoder(new_values) if new_values is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id or get_request_id(),
    )
    db.add(audit_log)
    return audit_log


async def list_audit_logs(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    action: str | None = None,
    correlation_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if action:
        query = query.where(AuditLog.action == action)
    if correlation_id:
        query = query.where(AuditLog.correlation_id == correlation_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at < date_to)

    result = await db.execute(
        query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    return [
        {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "user_id": log.user_id,
            "driver_id": log.driver_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "correlation_id": log.correlation_id,
            "created_at": log.created_at,
        }
        for log in result.scalars()
    ]
