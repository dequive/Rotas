from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.passwords import verify_password
from app.core.tokens import create_access_token
from app.modules.platform.models import PlatformUser


async def platform_login(db: AsyncSession, email: str, password: str) -> dict:
    """Authenticate a platform user and return a platform-scoped JWT.

    Raises ApiError 401 on bad credentials or inactive user.
    Token has scope="platform", no tenant_id claim, and embeds platform_user_id.
    """
    user = await db.scalar(select(PlatformUser).where(PlatformUser.email == email))
    if not user:
        raise ApiError("invalid_credentials", "Invalid email or password.", status_code=401)
    if not verify_password(password, user.password_hash):
        raise ApiError("invalid_credentials", "Invalid email or password.", status_code=401)
    if not user.is_active:
        raise ApiError("platform_user_inactive", "Platform user is inactive.", status_code=401)

    access_token, expires_in = create_access_token(
        tenant_id=None,
        scope="platform",
        role=user.role,
        platform_user_id=user.id,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
        },
    }
