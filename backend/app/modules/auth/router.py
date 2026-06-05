from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
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
    return await service.login(db, payload)


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    payload: schemas.RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.refresh(db, payload)


@router.post("/logout")
async def logout(
    payload: schemas.LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.logout(db, payload)


@driver_router.post("/pair")
@limiter.limit("10/minute")
async def pair_driver_device(
    request: Request,
    payload: schemas.DriverPairRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.pair_driver_device(db, payload)
