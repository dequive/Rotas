from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import Principal, validate_api_key
from core.database import AsyncSessionLocal, get_raw_session, set_rls_tenant

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_principal(
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
    api_key_raw: str | None = Security(_api_key_header),
    auth_db: AsyncSession = Depends(get_raw_session),
) -> Principal:
    if api_key_raw:
        principal = await validate_api_key(auth_db, api_key_raw)
        if principal:
            return principal
    raise HTTPException(
        status_code=401, detail={"code": "unauthorized", "message": "Invalid credentials."}
    )


async def get_session(
    principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    set_rls_tenant(principal.tenant_id)
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)


async def get_current_principal(
    principal: Principal = Depends(get_principal),
) -> Principal:
    return principal


def require_scope(scope: str):
    async def _check(principal: Principal = Depends(get_principal)) -> Principal:
        if scope not in (principal.scopes or []):
            raise HTTPException(
                status_code=403,
                detail={"code": "forbidden", "message": f"Scope '{scope}' required."},
            )
        return principal

    return _check
