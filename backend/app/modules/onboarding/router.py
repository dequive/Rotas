from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.database import get_session_raw as get_session
from app.modules.onboarding import schemas, service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post(
    "/register",
    response_model=schemas.OnboardingRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: schemas.OnboardingRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.register_tenant(
        db,
        payload,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/verify-email", response_model=schemas.EmailVerificationResponse)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    payload: schemas.EmailVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.verify_email(db, payload)
