import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt  # PyJWT — not python-jose; rejects alg=none by default (CVE-2025-61152 fix)

from app.config import get_settings


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(
    *,
    tenant_id: UUID | None,
    scope: str,
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
    role: str | None = None,
    device_id: str | None = None,
    permissions: frozenset[str] | None = None,
    platform_user_id: UUID | None = None,
) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    # Phase 25: sub construction — use platform_user_id for platform-scoped tokens.
    if user_id or driver_id:
        sub = f"{scope}:{user_id or driver_id}"
    elif platform_user_id:
        sub = f"{scope}:{platform_user_id}"
    else:
        sub = f"{scope}:platform"
    claims: dict = {
        "sub": sub,
        "typ": "access",
        "scope": scope,
        "role": role,
        "device_id": device_id,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    # Phase 25: omit tenant_id claim entirely when None (platform tokens have no tenant context).
    # Do NOT write "tenant_id": null — existing decoder uses UUID(claims["tenant_id"]) which
    # would raise TypeError on None.
    if tenant_id is not None:
        claims["tenant_id"] = str(tenant_id)
    if user_id is not None:
        claims["user_id"] = str(user_id)
    if driver_id is not None:
        claims["driver_id"] = str(driver_id)
    # Phase 25: embed platform_user_id for platform-scoped tokens.
    if platform_user_id is not None:
        claims["platform_user_id"] = str(platform_user_id)
    # Phase 22: embed permissions as sorted list when provided.
    # Omit the key entirely when None — keeps backward compat with decoders
    # that use claims.get("perms") returning None for absent keys.
    if permissions is not None:
        claims["perms"] = sorted(permissions)
    return (
        jwt.encode(
            claims, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
        ),
        settings.access_token_minutes * 60,
    )
