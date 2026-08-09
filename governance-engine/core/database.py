from collections.abc import AsyncIterator
from contextvars import ContextVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import NullPool

from core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Pool tuning: 4 workers × pool_size=3 × max_overflow=2 = max 20 connections.
# Adjust pool_size and max_overflow to match your PostgreSQL max_connections.
_pool_kwargs: dict = {}
if settings.environment == "production":
    _pool_kwargs = {"pool_size": 3, "max_overflow": 2, "pool_timeout": 10}
elif settings.environment == "test":
    # pytest uses a new asyncio loop per test; pooled asyncpg connections are
    # bound to the loop that created them and cannot be reused safely.
    _pool_kwargs = {"poolclass": NullPool}

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    **_pool_kwargs,
)
# ─── RLS context ─────────────────────────────────────────────────────────────
_rls_tenant: ContextVar[str | None] = ContextVar("_rls_tenant", default=None)


class GovernanceSession(Session):
    """Synchronous session behind Governance AsyncSession instances."""


@event.listens_for(GovernanceSession, "after_begin")
def _apply_rls_tenant_on_transaction(_session: Session, _transaction, connection) -> None:
    """Apply tenant context transaction-locally on every checked-out connection."""
    tenant_id = _rls_tenant.get()
    if tenant_id:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": tenant_id},
        )


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    sync_session_class=GovernanceSession,
)


def set_rls_tenant(tenant_id: str | None) -> None:
    _rls_tenant.set(tenant_id)


async def get_raw_session() -> AsyncIterator[AsyncSession]:
    """Session without RLS — for auth lookups before principal is known."""
    set_rls_tenant(None)
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)
