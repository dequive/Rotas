"""ARQ WorkerSettings for ROTAS.

Start command: arq app.jobs.worker.WorkerSettings

This worker:
- Runs daily maintenance schedule cron at 02:00 UTC (MAINT-01 D-07)
- Handles per-vehicle immediate maintenance checks (MAINT-01 D-01)
- Runs daily document expiry scan at 03:00 UTC (scan_expiring_documents)
- Uses ADMIN_DATABASE_URL with rotas_admin role (BYPASSRLS) per D-18

IMPORTANT: This worker must be deployed as a separate Railway service from the HTTP backend.
Command: arq app.jobs.worker.WorkerSettings
"""
import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.jobs.tasks.document_expiry import scan_expiring_documents
from app.jobs.tasks.maintenance import check_maintenance_schedules, check_vehicle_maintenance
from app.jobs.tasks.notifications import deliver_queued_notifications

logger = logging.getLogger(__name__)

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize DB session factory using admin URL (BYPASSRLS)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    # Use rotas_admin URL for BYPASSRLS — worker queries all tenants without RLS filter
    admin_url = _settings.resolved_admin_database_url
    engine = create_async_engine(admin_url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["engine"] = engine
    logger.info("ARQ worker started, admin DB: %s", admin_url[:30] + "...")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Dispose DB engine on shutdown."""
    if engine := ctx.get("engine"):
        await engine.dispose()
    logger.info("ARQ worker shut down.")


class WorkerSettings:
    functions = [
        check_maintenance_schedules,
        check_vehicle_maintenance,
        scan_expiring_documents,
        deliver_queued_notifications,
    ]
    cron_jobs = [
        # D-07: daily safety net for calendar-based maintenance plans
        cron(check_maintenance_schedules, hour={2}, minute=0, run_at_startup=False),
        # 260607-o5b: daily document expiry scan — offset by 1h to avoid DB contention
        cron(scan_expiring_documents, hour={3}, minute=0, run_at_startup=False),
        cron(deliver_queued_notifications, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host=_settings.redis_host, port=_settings.redis_port)
