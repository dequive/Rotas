from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session as get_rls_session
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.core.permissions import DASHBOARD_ROLES, require_roles
from app.database import get_session_raw as get_session
from app.modules.auth import schemas, service

router = APIRouter(prefix="/auth", tags=["auth"])
driver_router = APIRouter(prefix="/driver-auth", tags=["driver-auth"])


# CRITICAL slowapi rules:
# 1. @router.post() MUST be above @limiter.limit() — reversed order causes limit to not fire
# 2. request: Request MUST be an explicit parameter — not injected via Depends()
# 3. Threshold: 10 requests/minute per IP — D-08 per CONTEXT.md

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: schemas.LoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.login(
        db,
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    payload: schemas.RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.refresh(
        db,
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/mfa/verify")
@limiter.limit("10/minute")
async def verify_mfa(
    request: Request,
    payload: schemas.MfaVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.verify_mfa_challenge(
        db,
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout")
async def logout(
    payload: schemas.LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.logout(db, payload)


@router.post("/password-reset/request")
@limiter.limit("5/minute")
async def request_password_reset(
    request: Request,
    payload: schemas.PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.request_password_reset(
        db,
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/password-reset/complete")
@limiter.limit("5/minute")
async def complete_password_reset(
    request: Request,
    payload: schemas.PasswordResetCompleteRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.complete_password_reset(db, payload)


@router.get("/sessions")
async def list_sessions(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
    user_id: UUID | None = None,
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.list_sessions(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_id=user_id,
    )


@router.delete("/sessions/{session_id}", response_model=schemas.SessionRevokeResponse)
async def revoke_session(
    session_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.revoke_session(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        session_id=session_id,
    )


@router.get("/mfa")
async def get_mfa_status(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.get_mfa_status(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )


@router.post("/mfa/setup")
async def setup_mfa(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.setup_mfa(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )


@router.post("/mfa/confirm")
async def confirm_mfa(
    payload: schemas.MfaCodeRequest,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.confirm_mfa(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        payload=payload,
    )


@router.delete("/mfa")
async def disable_mfa(
    payload: schemas.MfaCodeRequest,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_rls_session)],
):
    if principal.user_id is None:
        raise ApiError("user_required", "User session is required.", status_code=403)
    return await service.disable_mfa(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        payload=payload,
    )


@driver_router.post("/pair")
@limiter.limit("10/minute")
async def pair_driver_device(
    request: Request,
    payload: schemas.DriverPairRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.pair_driver_device(db, payload)
