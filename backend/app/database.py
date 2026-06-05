from collections.abc import AsyncIterator
from importlib import import_module

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Pool tuning for Gunicorn multi-worker (D-12 / Pitfall 4)
# 4 workers × pool_size=2 × max_overflow=3 = max 20 connections total
# Prevents connection exhaustion and OOM on Railway 2GB instance
_pool_kwargs: dict = {}
if settings.environment == "production":
    _pool_kwargs = {"pool_size": 2, "max_overflow": 3}

engine = create_async_engine(settings.database_url, pool_pre_ping=True, **_pool_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


MODEL_MODULES = (
    "auth",
    "tenants",
    "contracts",
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
    "alerts",
    "sync",
    "audit",
)


def import_all_models() -> None:
    for module in MODEL_MODULES:
        import_module(f"app.modules.{module}.models")
