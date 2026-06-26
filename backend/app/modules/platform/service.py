"""Platform management service layer (Phase 25 — Plan 02).

All mutating functions call record_platform_audit() inside the same DB session
before db.commit() — audit and mutation are committed atomically.

Cross-tenant read pattern:
  The Tenant table has RLS enabled. Platform operators must SET LOCAL app.tenant_id
  before querying individual tenants. For list_tenants (cross-tenant scan), we use
  SET LOCAL row_security = off, which requires BYPASSRLS or superuser privileges on
  the DB role. In dev/test the rotas user is the DB owner; in production, grant
  BYPASSRLS to rotas_app if needed.
"""

from uuid import UUID

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.errors import ApiError
from app.core.passwords import hash_password
from app.core.rbac import PLATFORM_SUPPORT
from app.modules.platform.audit_service import record_platform_audit
from app.modules.platform.models import PlatformAuditLog, PlatformUser
from app.modules.tenants.models import Tenant

# ── private helpers ────────────────────────────────────────────────────────────


async def _set_tenant_ctx(db: AsyncSession, tenant_id: UUID) -> None:
    """Set the PostgreSQL session variable for the current transaction.

    The Tenant table has RLS; all platform queries must call this before reading
    a specific tenant row. SET LOCAL is transaction-scoped — auto-resets on commit.
    """
    await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def _require_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    """Fetch a Tenant by id, setting the RLS context first. Raises 404 if absent."""
    await _set_tenant_ctx(db, tenant_id)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise ApiError(
            "tenant_not_found",
            "Tenant not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return tenant


def _serialize_tenant(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "is_active": tenant.is_active,
        "is_trial": tenant.is_trial,
        "max_vehicles": tenant.max_vehicles,
        "max_drivers": tenant.max_drivers,
        "max_users": tenant.max_users,
        "trial_ends_at": tenant.trial_ends_at,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
    }


def _serialize_platform_user(user: PlatformUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def _serialize_audit_log(log: PlatformAuditLog) -> dict:
    return {
        "id": log.id,
        "actor_id": log.actor_id,
        "actor_role": log.actor_role,
        "target_tenant_id": log.target_tenant_id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "payload": log.payload,
        "ip_address": log.ip_address,
        "timestamp": log.timestamp,
    }


# ── public service functions ───────────────────────────────────────────────────


async def list_tenants(
    db: AsyncSession,
    *,
    actor_id: UUID,
    actor_role: str,
) -> list[dict]:
    """Return all tenants.

    Disables row-level security for this transaction so the cross-tenant scan
    succeeds. Requires BYPASSRLS or superuser on the connected DB role.
    In dev/test the rotas user owns the DB; in production grant BYPASSRLS to
    rotas_app on the tenants table.
    """
    await db.execute(text("SET LOCAL row_security = off"))
    rows = (await db.scalars(select(Tenant).order_by(Tenant.created_at))).all()
    return [_serialize_tenant(t) for t in rows]


async def get_tenant_detail(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID,
    actor_role: str,
) -> dict:
    """Return detail for a single tenant.

    For platform_support role, logs the cross-tenant read to platform_audit_logs.
    All roles must set app.tenant_id before querying (Tenant table has RLS).
    """
    tenant = await _require_tenant(db, tenant_id)

    if actor_role == PLATFORM_SUPPORT:
        await record_platform_audit(
            db,
            actor_id=actor_id,
            actor_role=actor_role,
            action="tenant.read",
            target_tenant_id=tenant_id,
            resource_type="tenant",
            resource_id=tenant_id,
        )
        await db.commit()

    return _serialize_tenant(tenant)


async def suspend_tenant(db: AsyncSession, tenant_id: UUID, *, actor: Principal) -> dict:
    """Set tenant.is_active=False. Records audit log before commit. Raises 409 if inactive."""
    tenant = await _require_tenant(db, tenant_id)

    if not tenant.is_active:
        raise ApiError(
            "tenant_already_inactive",
            "Tenant is already inactive.",
            status_code=status.HTTP_409_CONFLICT,
        )

    tenant.is_active = False
    await record_platform_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="tenant.suspend",
        target_tenant_id=tenant_id,
        resource_type="tenant",
        resource_id=tenant_id,
    )
    await db.commit()
    await db.refresh(tenant)
    return _serialize_tenant(tenant)


async def reactivate_tenant(db: AsyncSession, tenant_id: UUID, *, actor: Principal) -> dict:
    """Set tenant.is_active=True. Records audit log before commit. Raises 409 if active."""
    tenant = await _require_tenant(db, tenant_id)

    if tenant.is_active:
        raise ApiError(
            "tenant_already_active",
            "Tenant is already active.",
            status_code=status.HTTP_409_CONFLICT,
        )

    tenant.is_active = True
    await record_platform_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="tenant.reactivate",
        target_tenant_id=tenant_id,
        resource_type="tenant",
        resource_id=tenant_id,
    )
    await db.commit()
    await db.refresh(tenant)
    return _serialize_tenant(tenant)


async def change_tenant_plan(
    db: AsyncSession,
    tenant_id: UUID,
    new_plan: str,
    *,
    actor: Principal,
) -> dict:
    """Update tenant.plan. Records audit log before commit."""
    tenant = await _require_tenant(db, tenant_id)
    old_plan = tenant.plan
    tenant.plan = new_plan
    await record_platform_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="tenant.plan_changed",
        target_tenant_id=tenant_id,
        resource_type="tenant",
        resource_id=tenant_id,
        payload={"old_plan": old_plan, "new_plan": new_plan},
    )
    await db.commit()
    await db.refresh(tenant)
    return _serialize_tenant(tenant)


async def list_platform_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return platform_audit_logs filtered by target_tenant_id, newest first."""
    rows = (
        await db.scalars(
            select(PlatformAuditLog)
            .where(PlatformAuditLog.target_tenant_id == tenant_id)
            .order_by(PlatformAuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [_serialize_audit_log(r) for r in rows]


async def list_platform_users(db: AsyncSession) -> list[dict]:
    """Return all platform users ordered by creation date."""
    rows = (await db.scalars(select(PlatformUser).order_by(PlatformUser.created_at))).all()
    return [_serialize_platform_user(u) for u in rows]


async def create_platform_user(
    db: AsyncSession,
    email: str,
    role: str,
    password: str,
    *,
    actor: Principal,
) -> dict:
    """Create a new PlatformUser with a hashed password. Raises 409 on duplicate email."""
    existing = await db.scalar(select(PlatformUser).where(PlatformUser.email == email))
    if existing:
        raise ApiError(
            "platform_user_email_conflict",
            "Email already registered.",
            status_code=status.HTTP_409_CONFLICT,
        )

    user = PlatformUser(
        email=email,
        role=role,
        password_hash=hash_password(password),
    )
    db.add(user)

    await record_platform_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="platform_user.created",
        resource_type="platform_user",
        payload={"email": email, "role": role},
    )
    await db.commit()
    await db.refresh(user)
    return _serialize_platform_user(user)
