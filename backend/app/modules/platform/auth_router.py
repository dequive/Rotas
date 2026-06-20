from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_raw as get_session
from app.modules.platform import auth_service
from app.modules.platform.schemas import PlatformLoginRequest

router = APIRouter(prefix="/platform/auth", tags=["platform-auth"])


@router.post("/login")
async def platform_login(
    payload: PlatformLoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Authenticate a platform operator and return a platform-scoped JWT.

    This endpoint is public (no auth required). The returned token carries
    scope="platform" with no tenant_id claim and must be used exclusively
    with platform endpoints protected by require_platform_role().
    """
    return await auth_service.platform_login(db, payload.email, payload.password)
