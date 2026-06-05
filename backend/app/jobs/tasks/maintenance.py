"""ARQ tasks for preventive maintenance scheduler (MAINT-01).

Two tasks:
- check_maintenance_schedules: daily cron, scans all active tenants
- check_vehicle_maintenance: per-vehicle immediate trigger from odometer update
"""
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def check_maintenance_schedules(ctx: dict) -> dict:
    """Daily cron: check all active tenants for overdue maintenance plans.

    Uses ADMIN_DATABASE_URL (rotas_admin BYPASSRLS role) to query across all tenants.
    Called by WorkerSettings.cron_jobs — fires at 02:00 UTC daily.
    """
    from app.modules.workshop.service import evaluate_maintenance_schedule_all_tenants

    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        result = await evaluate_maintenance_schedule_all_tenants(db)
    logger.info("Daily maintenance check complete: %s", result)
    return result


async def check_vehicle_maintenance(
    ctx: dict,
    vehicle_id: str,
    tenant_id: str,
    current_km: int,
) -> dict:
    """Per-vehicle maintenance trigger (D-01 odometer event path).

    Called immediately when fuel service updates vehicle.current_km.
    Runs evaluate_maintenance_schedule for the single tenant only.
    """
    from app.modules.workshop.service import evaluate_maintenance_schedule

    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        result = await evaluate_maintenance_schedule(
            db, UUID(tenant_id), actor_id=None
        )
    logger.info(
        "Vehicle %s maintenance check at km=%s: %s",
        vehicle_id,
        current_km,
        result,
    )
    return result
