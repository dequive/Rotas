"""ARQ tasks for bounded housekeeping of append-only/TTL tables."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.config import get_settings
from app.modules.audit.models import AuditLog
from app.modules.sync.models import IdempotencyKey

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


async def cleanup_expired_idempotency_keys(ctx: dict, limit: int = DEFAULT_BATCH_SIZE) -> dict:
    """Delete expired HTTP idempotency reservations in bounded batches."""
    session_factory = ctx["session_factory"]
    now = datetime.now(UTC)

    async with session_factory() as db:
        expired_ids = (
            select(IdempotencyKey.id)
            .where(IdempotencyKey.expires_at < now)
            .order_by(IdempotencyKey.expires_at.asc())
            .limit(limit)
            .subquery()
        )
        result = await db.execute(
            delete(IdempotencyKey)
            .where(IdempotencyKey.id.in_(select(expired_ids.c.id)))
            .execution_options(synchronize_session=False)
        )
        await db.commit()

    deleted = int(result.rowcount or 0)
    payload = {"deleted": deleted, "limit": limit}
    logger.info("Expired idempotency cleanup complete: %s", payload)
    return payload


async def prune_old_audit_logs(ctx: dict, limit: int = DEFAULT_BATCH_SIZE) -> dict:
    """Apply configured audit log retention in bounded batches."""
    settings = get_settings()
    retention_days = settings.audit_log_retention_days
    if retention_days <= 0:
        return {"deleted": 0, "limit": limit, "retention_days": retention_days, "skipped": True}

    session_factory = ctx["session_factory"]
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    async with session_factory() as db:
        old_ids = (
            select(AuditLog.id)
            .where(AuditLog.created_at < cutoff)
            .order_by(AuditLog.created_at.asc())
            .limit(limit)
            .subquery()
        )
        result = await db.execute(
            delete(AuditLog)
            .where(AuditLog.id.in_(select(old_ids.c.id)))
            .execution_options(synchronize_session=False)
        )
        await db.commit()

    deleted = int(result.rowcount or 0)
    payload = {
        "deleted": deleted,
        "limit": limit,
        "retention_days": retention_days,
        "cutoff": cutoff.isoformat(),
    }
    logger.info("Audit log retention cleanup complete: %s", payload)
    return payload


async def run_housekeeping(ctx: dict) -> dict:
    """Daily worker entrypoint for storage/retention cleanup."""
    idempotency = await cleanup_expired_idempotency_keys(ctx)
    audit_logs = await prune_old_audit_logs(ctx)
    return {"idempotency_keys": idempotency, "audit_logs": audit_logs}
