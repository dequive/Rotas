from uuid import UUID

from fastapi import status
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.passwords import hash_password
from app.modules.audit.service import record_audit_log
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserPatch

USER_ROLES = {"owner", "admin", "manager", "viewer"}


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_role(role: str) -> None:
    if role not in USER_ROLES:
        raise ApiError(
            "invalid_user_role",
            "User role is not supported.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed_roles": sorted(USER_ROLES)},
        )


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise ApiError(
            "weak_password",
            "Password must contain at least 8 characters.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


async def _get_cached_user_count(
    db: AsyncSession, tenant_id: UUID, redis: AsyncRedis | None
) -> int:
    """Return active user count from Redis cache (TTL 30s) or DB (D-15)."""
    cache_key = f"tenant:limits:{tenant_id}"
    if redis is not None:
        cached = await redis.hget(cache_key, "user_count")
        if cached is not None:
            return int(cached)
    result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    )
    count = result.scalar_one()
    if redis is not None:
        await redis.hset(cache_key, "user_count", count)
        await redis.expire(cache_key, 30)
    return count


async def _check_user_limit(
    db: AsyncSession, tenant: Tenant, redis: AsyncRedis | None
) -> None:
    """Raise plan_limit_reached if tenant is at or over max_users (D-13, D-14).

    Skip entirely when max_users is None (unlimited enterprise plan).
    """
    if tenant.max_users is None:
        return
    count = await _get_cached_user_count(db, tenant.id, redis)
    if count >= tenant.max_users:
        raise ApiError(
            "plan_limit_reached",
            f"User limit reached ({count}/{tenant.max_users}). Upgrade your plan.",
            status_code=403,
            details={
                "upgrade_url": get_settings().upgrade_url,
                "dimension": "users",
                "used": count,
                "max": tenant.max_users,
            },
        )


async def _require_user(db: AsyncSession, tenant_id: UUID, user_id: UUID) -> User:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise ApiError("user_not_found", "User not found.", status_code=status.HTTP_404_NOT_FOUND)
    return user


async def _email_exists(
    db: AsyncSession,
    tenant_id: UUID,
    email: str,
    *,
    exclude_user_id: UUID | None = None,
) -> bool:
    query = select(User.id).where(User.tenant_id == tenant_id, User.email == email)
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    return await db.scalar(query) is not None


async def list_users(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.full_name.asc(), User.email.asc())
        .limit(limit)
        .offset(offset)
    )
    return [serialize_user(user) for user in result.scalars()]


async def create_user(
    db: AsyncSession,
    tenant_id: UUID,
    payload: UserCreate,
    *,
    actor_id: UUID | None = None,
    redis: AsyncRedis | None = None,
) -> dict:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise ApiError("tenant_not_found", "Tenant not found or inactive.", status_code=404)

    email = _normalize_email(payload.email)
    _validate_role(payload.role)
    _validate_password(payload.password)
    # Duplicate check before limit check — 409 takes precedence over 403
    if await _email_exists(db, tenant_id, email):
        raise ApiError(
            "user_email_conflict",
            "User email already exists for this tenant.",
            status_code=status.HTTP_409_CONFLICT,
            details={"email": email},
        )

    await _check_user_limit(db, tenant, redis)

    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        new_values=serialize_user(user),
    )
    await db.commit()
    await db.refresh(user)
    return serialize_user(user)


async def patch_user(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    payload: UserPatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    user = await _require_user(db, tenant_id, user_id)
    old_values = serialize_user(user)
    values = payload.model_dump(exclude_unset=True)
    if "email" in values:
        values["email"] = _normalize_email(values["email"])
        if await _email_exists(db, tenant_id, values["email"], exclude_user_id=user.id):
            raise ApiError(
                "user_email_conflict",
                "User email already exists for this tenant.",
                status_code=status.HTTP_409_CONFLICT,
                details={"email": values["email"]},
            )
    if "role" in values:
        _validate_role(values["role"])
    for field, value in values.items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        old_values=old_values,
        new_values=serialize_user(user),
    )
    await db.commit()
    await db.refresh(user)
    return serialize_user(user)
