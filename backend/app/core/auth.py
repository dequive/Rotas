from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt  # PyJWT — not python-jose; rejects alg=none by default (CVE-2025-61152 fix)
from fastapi import Depends, Header, status
from sqlalchemy import select

from app.config import get_settings
from app.core.errors import ApiError
from app.database import AsyncSessionLocal
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.tenants.models import Tenant
from app.modules.users.models import User


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: UUID | None  # Phase 25: None for platform-scoped tokens
    scope: str
    role: str | None = None
    user_id: UUID | None = None
    driver_id: UUID | None = None
    device_id: str | None = None
    # Phase 22: optional explicit permission set (from JWT "perms" claim or custom tenant role).
    # When None, has_any_permission() falls back to ROLE_PERMISSIONS[role] (static mapping).
    # Existing tokens without "perms" claim will have permissions=None — backward compatible.
    permissions: frozenset[str] | None = None

    def has_any_permission(self, required: frozenset[str]) -> bool:
        """Return True if the principal holds at least one of the required permissions.

        Effective permissions are resolved in priority order:
          1. self.permissions (explicit frozenset from JWT "perms" claim or custom role)
          2. ROLE_PERMISSIONS[self.role] (static mapping — fallback for existing tokens)
        """
        from app.core.rbac import ROLE_PERMISSIONS  # late import — breaks circular dep

        effective = (
            self.permissions
            if self.permissions is not None
            else ROLE_PERMISSIONS.get(self.role or "", frozenset())
        )
        return bool(effective & required)


async def get_current_principal(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-Id")] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(
            "unauthorized",
            "Authentication token is required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = authorization.split(" ", 1)[1]
    settings = get_settings()
    dev_test_token = settings.dev_test_token.get_secret_value()
    if (
        dev_test_token
        and token == dev_test_token
        and settings.environment in {"development", "test"}
    ):
        if x_tenant_id is None:
            raise ApiError(
                "tenant_required",
                "Tenant context is required for the development token.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return Principal(
            subject="development:user",
            tenant_id=x_tenant_id,
            scope="dashboard",
            role="admin",
        )
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if claims.get("typ") != "access":
            raise jwt.DecodeError("invalid token type")
        tenant_id = UUID(claims["tenant_id"])
        user_id = UUID(claims["user_id"]) if claims.get("user_id") else None
        driver_id = UUID(claims["driver_id"]) if claims.get("driver_id") else None
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise ApiError(
            "invalid_token",
            "Authentication token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if x_tenant_id and x_tenant_id != tenant_id:
        raise ApiError(
            "tenant_mismatch",
            "Tenant header does not match the authenticated tenant.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    # Phase 22: extract permissions claim — None when absent (backward compat with old tokens)
    raw_perms = claims.get("perms")  # list[str] | None
    permissions: frozenset[str] | None = frozenset(raw_perms) if raw_perms else None
    scope = claims.get("scope")
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant or not tenant.is_active:
            raise ApiError("tenant_inactive", "Tenant is inactive.", status_code=401)
        if scope == "dashboard" and user_id:
            user = await db.get(User, user_id)
            if not user or user.tenant_id != tenant_id or not user.is_active:
                raise ApiError("user_inactive", "User is inactive.", status_code=401)
        elif scope == "driver_app" and driver_id and claims.get("device_id"):
            driver = await db.get(Driver, driver_id)
            if not driver or driver.tenant_id != tenant_id:
                raise ApiError("driver_inactive", "Driver not found.", status_code=401)

            # D-08: Query device WITHOUT is_active filter so we can distinguish
            # "device deactivated" (revocation) from "device not found"
            device = await db.scalar(
                select(DriverDevice).where(
                    DriverDevice.tenant_id == tenant_id,
                    DriverDevice.driver_id == driver_id,
                    DriverDevice.device_id == claims["device_id"],
                )
            )
            if not device:
                raise ApiError("driver_inactive", "Driver device not found.", status_code=401)

            # D-08: Deactivated device is a permanent revocation — different error code than
            # temporary suspension. The client (api.ts refreshAccessToken) checks this code to
            # show "Acesso revogado" message and preserve local Dexie data.
            if not device.is_active:
                raise ApiError(
                    "driver_access_revoked",
                    "Driver access has been revoked by the manager.",
                    status_code=401,
                )

            if driver.status != "active":
                raise ApiError("driver_inactive", "Driver is inactive.", status_code=401)
        else:
            raise ApiError(
                "invalid_token_scope",
                "Authentication scope is invalid.",
                status_code=401,
            )
    return Principal(
        subject=claims["sub"],
        tenant_id=tenant_id,
        scope=scope,
        role=claims.get("role"),
        user_id=user_id,
        driver_id=driver_id,
        device_id=claims.get("device_id"),
        permissions=permissions,
    )


async def get_current_platform_principal(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> "Principal":
    """Decode and validate a platform-scoped JWT.

    This is a SEPARATE function from get_current_principal() — not a branch inside it.
    Structural separation is a security invariant: tenant tokens never reach platform logic.

    Scope check fires BEFORE any role or DB lookup — a tenant JWT with role="platform_admin"
    is rejected at the scope check, before its role field is ever examined.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(
            "unauthorized",
            "Authentication token is required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = authorization.split(" ", 1)[1]
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if claims.get("typ") != "access":
            raise jwt.DecodeError("invalid token type")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise ApiError(
            "invalid_token",
            "Authentication token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    # Scope check MUST come before role — rejects tenant tokens that happen to have a
    # role string matching a platform role name.
    if claims.get("scope") != "platform":
        raise ApiError(
            "forbidden",
            "Platform scope required.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    platform_user_id_str = claims.get("platform_user_id")
    if not platform_user_id_str:
        raise ApiError(
            "invalid_token",
            "Token missing platform_user_id.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    platform_user_id = UUID(platform_user_id_str)

    async with AsyncSessionLocal() as db:
        from app.modules.platform.models import PlatformUser  # noqa: PLC0415

        user = await db.get(PlatformUser, platform_user_id)
        if not user or not user.is_active:
            raise ApiError(
                "forbidden",
                "Platform user inactive or not found.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    return Principal(
        subject=claims["sub"],
        tenant_id=None,
        scope="platform",
        role=claims.get("role"),
        user_id=platform_user_id,
    )


async def get_driver_principal(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    # Allow the development test-token bypass (subject="development:user") so existing
    # integration tests that exercise sync internals continue to work.
    # Real manager tokens (scope="dashboard", subject != "development:user") are rejected.
    if principal.scope == "driver_app" or principal.subject == "development:user":
        return principal
    raise ApiError(
        "driver_scope_required",
        "Driver app token is required.",
        status_code=status.HTTP_403_FORBIDDEN,
    )
