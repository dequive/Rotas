from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from importlib import import_module
from time import perf_counter

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.core.database_pool_metrics import install_database_pool_metrics
from app.core.performance_diagnostics import (
    measure_request_phase,
    observe_request_phase,
)


class Base(DeclarativeBase):
    pass


settings = get_settings()
_deferred_commit_sessions: ContextVar[frozenset[int]] = ContextVar(
    "deferred_commit_sessions",
    default=frozenset(),
)


class RotasAsyncSession(AsyncSession):
    """Session whose inner commits can be deferred by a top-level use case."""

    async def commit(self) -> None:
        if id(self) in _deferred_commit_sessions.get():
            await self.flush()
            return
        await super().commit()


@contextmanager
def defer_session_commits(session: AsyncSession) -> Iterator[None]:
    """Turn commits for one session into flushes until the outer use case commits."""
    deferred_sessions = _deferred_commit_sessions.get()
    token = _deferred_commit_sessions.set(deferred_sessions | {id(session)})
    try:
        yield
    finally:
        _deferred_commit_sessions.reset(token)

# Pool tuning for Gunicorn multi-worker (D-12 / Pitfall 4)
# 4 workers × pool_size=2 × max_overflow=3 = max 20 connections total
# Prevents connection exhaustion and OOM on Railway 2GB instance
_pool_kwargs: dict = {}
if settings.environment == "production":
    _pool_kwargs = {"pool_size": 2, "max_overflow": 3}

engine = create_async_engine(settings.database_url, pool_pre_ping=True, **_pool_kwargs)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=RotasAsyncSession,
    expire_on_commit=False,
)
if settings.resolved_admin_database_url == settings.database_url:
    admin_engine = engine
else:
    admin_engine = create_async_engine(
        settings.resolved_admin_database_url,
        pool_pre_ping=True,
        **_pool_kwargs,
    )
AdminSessionLocal = async_sessionmaker(
    admin_engine,
    class_=RotasAsyncSession,
    expire_on_commit=False,
)

_configured_pool_size = int(_pool_kwargs.get("pool_size", 5))
_configured_max_overflow = int(_pool_kwargs.get("max_overflow", 10))
if admin_engine is engine:
    install_database_pool_metrics(
        engine,
        pool_name="shared",
        pool_size=_configured_pool_size,
        max_overflow=_configured_max_overflow,
    )
else:
    install_database_pool_metrics(
        engine,
        pool_name="application",
        pool_size=_configured_pool_size,
        max_overflow=_configured_max_overflow,
    )
    install_database_pool_metrics(
        admin_engine,
        pool_name="administrative",
        pool_size=_configured_pool_size,
        max_overflow=_configured_max_overflow,
    )


def _install_query_diagnostics(target_engine, phase: str) -> None:  # type: ignore[no-untyped-def]
    key = f"rotas_{phase}_started"

    @event.listens_for(target_engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(  # type: ignore[no-untyped-def]
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        connection.info.setdefault(key, []).append(perf_counter())

    @event.listens_for(target_engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(  # type: ignore[no-untyped-def]
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        starts = connection.info.get(key)
        if starts:
            observe_request_phase(phase, perf_counter() - starts.pop())


if settings.performance_diagnostics:
    _install_query_diagnostics(engine, "app_sql")
    if admin_engine is not engine:
        _install_query_diagnostics(admin_engine, "admin_sql")


@dataclass(frozen=True)
class DatabaseRoleSecurity:
    role_name: str
    is_superuser: bool
    bypasses_rls: bool

    @property
    def is_restricted(self) -> bool:
        return not self.is_superuser and not self.bypasses_rls


async def inspect_application_database_role() -> DatabaseRoleSecurity:
    """Return the security attributes of the role behind DATABASE_URL."""
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT current_user AS role_name, rolsuper, rolbypassrls "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one()
    return DatabaseRoleSecurity(
        role_name=row.role_name,
        is_superuser=row.rolsuper,
        bypasses_rls=row.rolbypassrls,
    )


async def validate_application_database_role(
    *, require_restricted: bool | None = None
) -> DatabaseRoleSecurity:
    """Fail startup when production DATABASE_URL can bypass tenant RLS."""
    role = await inspect_application_database_role()
    must_be_restricted = (
        settings.environment == "production" if require_restricted is None else require_restricted
    )
    if must_be_restricted and not role.is_restricted:
        raise RuntimeError(
            "DATABASE_URL must use a non-superuser role without BYPASSRLS in production. "
            "Use rotas_app for the API and reserve rotas_admin for migrations and workers."
        )
    return role

# ---------------------------------------------------------------------------
# RLS context variable — holds the current request's tenant_id.
# ContextVar is asyncio-safe: each coroutine has its own copy, no shared state.
# ---------------------------------------------------------------------------
_rls_tenant: ContextVar[str | None] = ContextVar("_rls_tenant", default=None)


def set_rls_tenant(tenant_id: str | None) -> None:
    """Set the current request's tenant_id for RLS enforcement.

    Called by get_session() in app.core.deps before yielding the session.
    Call with None to clear after the request completes.
    D-17: Uses SET LOCAL (transaction-scoped, not connection-scoped) — critical for pool safety.
    """
    _rls_tenant.set(tenant_id)


@event.listens_for(AsyncSession.sync_session_class, "after_begin")
def _inject_rls_tenant(session, transaction, connection):  # type: ignore[no-untyped-def]
    """SQLAlchemy after_begin event: fires once per transaction.

    Executes a transaction-local set_config so the PostgreSQL RLS policy can read it.
    Transaction-local scope (not connection scope) is mandatory for pool safety.
    With asyncpg connection pooling, connections are reused across requests.
    The transaction-local flag ensures the tenant_id never leaks across request boundaries (D-17).
    """
    tid = _rls_tenant.get()
    if tid is not None:
        with measure_request_phase("rls_context"):
            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": tid},
            )


async def get_session_raw() -> AsyncIterator[AsyncSession]:
    """Administrative session without tenant RLS injection.

    Used only by identity bootstrap, onboarding and platform control-plane routes
    that must resolve a tenant before an RLS context exists. In production this
    is backed by ADMIN_DATABASE_URL, never DATABASE_URL.
    """
    set_rls_tenant(None)
    try:
        async with AdminSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)


# ---------------------------------------------------------------------------
# NOTE: The RLS-aware get_session() dependency that injects the principal and
# calls set_rls_tenant() lives in app.core.deps — NOT here.
#
# Reason: app.core.auth imports AsyncSessionLocal from this module. If this
# module imported get_current_principal from app.core.auth at module level it
# would create a circular import. Defining get_session in app.core.deps
# (which imports from both modules after they are fully loaded) avoids that.
#
# All routers that previously did:
#   from app.database import get_session
# should now do:
#   from app.core.deps import get_session
#
# The auth router is the exception — it uses get_session_raw from here.
# ---------------------------------------------------------------------------


MODEL_MODULES = (
    "auth",
    "platform",
    "tenants",
    "third_party",
    "contracts",
    "clients",
    "users",
    "drivers",
    "vehicles",
    "files",
    "checklists",
    "fuel",
    "trip_orders",
    "trips",
    "cargo",
    "billing",
    "operations",
    "operational_exceptions",
    "workshop",
    "control_tower",
    "payables",
    "accounting",
    "alerts",
    "notifications",
    "sync",
    "audit",
    "gps",
    "payables",
    "hr",
    "inventory",
    "outbox",
)

ADDITIONAL_MODEL_MODULES = (
    "app.modules.workshop.catalog_models",
    "app.modules.workshop.quote_models",
    "app.modules.workshop.reception_models",
    "app.modules.workshop.warranty_models",
    "app.modules.workshop.workbay_models",
)


def import_all_models() -> None:
    for module in MODEL_MODULES:
        import_module(f"app.modules.{module}.models")
    for module in ADDITIONAL_MODEL_MODULES:
        import_module(module)
