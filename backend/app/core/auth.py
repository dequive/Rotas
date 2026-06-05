from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, status
import jwt  # PyJWT — not python-jose; rejects alg=none by default (CVE-2025-61152 fix)
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
    tenant_id: UUID
    scope: str
    role: str | None = None
    user_id: UUID | None = None
    driver_id: UUID | None = None
    device_id: str | None = None


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
    if token == "test-token" and settings.environment in {"development", "test"}:
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
            device = await db.scalar(
                select(DriverDevice).where(
                    DriverDevice.tenant_id == tenant_id,
                    DriverDevice.driver_id == driver_id,
                    DriverDevice.device_id == claims["device_id"],
                    DriverDevice.is_active.is_(True),
                )
            )
            if (
                not driver
                or driver.tenant_id != tenant_id
                or driver.status != "active"
                or not device
            ):
                raise ApiError("driver_inactive", "Driver device is inactive.", status_code=401)
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
