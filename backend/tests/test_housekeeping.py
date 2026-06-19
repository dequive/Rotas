from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.jobs.tasks import housekeeping
from app.jobs.tasks.housekeeping import cleanup_expired_idempotency_keys, prune_old_audit_logs
from app.modules.audit.models import AuditLog
from app.modules.sync.models import IdempotencyKey
from app.modules.tenants.models import Tenant


async def _create_tenant(db) -> Tenant:
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Tenant Housekeeping {suffix}", slug=f"housekeeping-{suffix}")
    db.add(tenant)
    await db.flush()
    return tenant


@pytest.mark.asyncio
async def test_cleanup_expired_idempotency_keys_deletes_only_expired(db) -> None:
    tenant = await _create_tenant(db)
    now = datetime.now(UTC)
    expired = IdempotencyKey(
        tenant_id=tenant.id,
        idempotency_key=f"expired-{uuid4().hex}",
        operation="test",
        entity_type="test",
        request_hash="a" * 64,
        response_body={"ok": True},
        status_code=200,
        expires_at=now - timedelta(seconds=1),
    )
    active = IdempotencyKey(
        tenant_id=tenant.id,
        idempotency_key=f"active-{uuid4().hex}",
        operation="test",
        entity_type="test",
        request_hash="b" * 64,
        response_body={"ok": True},
        status_code=200,
        expires_at=now + timedelta(days=1),
    )
    db.add_all([expired, active])
    await db.commit()

    result = await cleanup_expired_idempotency_keys({"session_factory": AsyncSessionLocal})

    assert result["deleted"] >= 1
    remaining = (
        await db.scalars(select(IdempotencyKey.id).where(IdempotencyKey.tenant_id == tenant.id))
    ).all()
    assert remaining == [active.id]


@pytest.mark.asyncio
async def test_prune_old_audit_logs_respects_retention(db, monkeypatch) -> None:
    tenant = await _create_tenant(db)
    now = datetime.now(UTC)
    old_log = AuditLog(
        tenant_id=tenant.id,
        action="test.old",
        entity_type="test",
        entity_id=None,
        created_at=now - timedelta(days=45),
    )
    recent_log = AuditLog(
        tenant_id=tenant.id,
        action="test.recent",
        entity_type="test",
        entity_id=None,
        created_at=now - timedelta(days=5),
    )
    db.add_all([old_log, recent_log])
    await db.commit()

    settings = type("SettingsStub", (), {"audit_log_retention_days": 30})()
    monkeypatch.setattr(housekeeping, "get_settings", lambda: settings)

    result = await prune_old_audit_logs({"session_factory": AsyncSessionLocal})

    assert result["deleted"] >= 1
    remaining_actions = (
        await db.scalars(select(AuditLog.action).where(AuditLog.tenant_id == tenant.id))
    ).all()
    assert remaining_actions == ["test.recent"]
