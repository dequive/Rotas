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
    tenant_id: UUID,
    scope: str,
    user_id: UUID | None = None,
    driver_id: UUID | None = None,
    role: str | None = None,
    device_id: str | None = None,
    permissions: frozenset[str] | None = None,
) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    claims = {
        "sub": f"{scope}:{user_id or driver_id}",
        "typ": "access",
        "scope": scope,
        "tenant_id": str(tenant_id),
        "user_id": str(user_id) if user_id else None,
        "driver_id": str(driver_id) if driver_id else None,
        "role": role,
        "device_id": device_id,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
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
