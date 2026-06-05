"""FastAPI dependencies for tenant-aware database sessions.

This module exists to break the circular import between app.database and app.core.auth:
  - app.database defines AsyncSessionLocal and set_rls_tenant (no auth import)
  - app.core.auth imports AsyncSessionLocal from app.database
  - app.core.deps imports from both — safe because it is loaded after both modules

Usage in routers (replaces the old `from app.database import get_session`):
    from app.core.deps import get_session
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.database import AsyncSessionLocal, set_rls_tenant


async def get_session(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields AsyncSession with RLS tenant_id pre-set.

    Sets the request-scoped ContextVar before opening the session so the
    SQLAlchemy after_begin event fires SET LOCAL app.tenant_id on the first
    transaction. Clears it in the finally block so pooled connections are
    never contaminated with a previous request's tenant context (D-17).
    """
    set_rls_tenant(str(principal.tenant_id))
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)
