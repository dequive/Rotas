from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import PlatformAuditLog


async def record_platform_audit(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_role: str,
    action: str,
    target_tenant_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    payload: dict | None = None,
    ip_address: str | None = None,
) -> PlatformAuditLog:
    """Append an entry to platform_audit_logs.

    Caller is responsible for committing the session — same pattern as
    record_audit_log() in audit/service.py. This allows callers to batch
    the audit log insert with their primary mutation in one transaction.
    """
    log = PlatformAuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        target_tenant_id=target_tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        ip_address=ip_address,
    )
    db.add(log)
    return log
