"""ARQ background worker for ROTAS. Handles billing export jobs and KPI cache refresh."""

from datetime import UTC

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def startup(ctx: dict) -> None:
    import sentry_sdk
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings as _get_settings
    from app.core.logging import configure_structlog  # INFRA2-02
    from app.main import _scrub_pii

    _settings = _get_settings()

    # INFRA2-02: Configure structured logging before anything else
    configure_structlog(json_logs=_settings.environment == "production")

    # INFRA-01: Sentry in ARQ worker — init before any job processing (D-04)
    if _settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=_settings.sentry_dsn_backend,
            environment=_settings.environment,
            traces_sample_rate=0.05,
            before_send=_scrub_pii,
        )
    # D-18 / RLS-02: ARQ worker uses rotas_admin role (BYPASSRLS) for cross-tenant queries.
    admin_engine = create_async_engine(
        _settings.resolved_admin_database_url,
        pool_pre_ping=True,
    )
    ctx["db_factory"] = async_sessionmaker(admin_engine, expire_on_commit=False)
    ctx["admin_engine"] = admin_engine  # store for cleanup in shutdown

    import structlog

    _logger = structlog.get_logger("worker")
    _logger.info("arq_worker_started")

    # INFRA2-04: Enqueue first heartbeat immediately
    from datetime import datetime

    redis = ctx.get("redis")
    if redis:
        await redis.setex("arq:health:worker_heartbeat", 90, datetime.now(UTC).isoformat())


async def shutdown(ctx: dict) -> None:
    if "admin_engine" in ctx:
        await ctx["admin_engine"].dispose()


async def generate_billing_export(
    ctx: dict,
    job_id: str,
    document_id: str,
    export_format: str,
    tenant_id: str,
) -> dict:
    """ARQ task: generate PDF or XLSX for a billing document.

    Idempotent: checks existing job record before generating.
    Updates ExportJob status: queued → processing → done/failed.
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.modules.billing.exporters import render_billing_export
    from app.modules.billing.models import BillingDocument, BillingItem, ExportJob
    from app.modules.files.service import save_generated_file as _save_generated_file
    from app.modules.tenants.models import Tenant

    async with ctx["db_factory"]() as db:
        # Update job status to processing
        job = await db.scalar(select(ExportJob).where(ExportJob.id == UUID(job_id)))
        if not job:
            return {"error": "job_not_found"}
        job.status = "processing"
        await db.commit()

        try:
            doc = await db.scalar(
                select(BillingDocument).where(
                    BillingDocument.id == UUID(document_id),
                    BillingDocument.tenant_id == UUID(tenant_id),
                )
            )
            if not doc:
                job.status = "failed"
                job.error_message = "Document not found"
                await db.commit()
                return {"error": "document_not_found"}

            items = (
                (
                    await db.execute(
                        select(BillingItem).where(
                            BillingItem.billing_document_id == doc.id,
                            BillingItem.tenant_id == UUID(tenant_id),
                        )
                    )
                )
                .scalars()
                .all()
            )

            tenant = await db.get(Tenant, UUID(tenant_id))
            issuer_name = tenant.name if tenant else "ROTAS"
            issuer_contact = tenant.whatsapp_number if tenant else None

            artifact = render_billing_export(
                doc,
                list(items),
                export_format,
                issuer_name=issuer_name,
                issuer_contact=issuer_contact,
            )

            # INFRA-02: route through files module — no direct disk writes
            file_obj = await _save_generated_file(
                db,
                UUID(tenant_id),
                content=artifact.content,
                filename=artifact.filename,
                mime_type=artifact.mime_type,
                file_type=export_format,
                entity_type="billing_document",
                entity_id=UUID(document_id),
            )
            job.status = "done"
            job.file_id = file_obj.id
            job.file_path = file_obj.storage_key
            await db.commit()
            return {"job_id": job_id, "status": "done", "file_id": str(file_obj.id)}

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:500]
            await db.commit()
            return {"error": str(exc)}


# ── SM-01: BillingDocument overdue cron ──────────────────────────────────────


async def task_mark_overdue_billing_documents(ctx: dict) -> str:
    """SM-01: Daily cron — mark issued BillingDocuments past due_date as overdue.

    Runs daily at 01:00 Africa/Maputo (23:00 UTC).
    Uses BYPASSRLS admin session — operates across all tenants.
    """
    from datetime import datetime

    import structlog
    from sqlalchemy import and_, update

    from app.modules.billing.models import BillingDocument

    logger = structlog.get_logger("worker")

    async with ctx["db_factory"]() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            update(BillingDocument)
            .where(
                and_(
                    BillingDocument.status == "issued",
                    BillingDocument.billing_period_end < now,
                )
            )
            .values(status="overdue", overdue_since_at=now)
            .returning(BillingDocument.id)
        )
        overdue_ids = result.scalars().all()
        await db.commit()

    count = len(overdue_ids)
    logger.info("task_mark_overdue_billing_documents", count=count)
    return f"Marked {count} billing documents as overdue"


# ── SM-02: Contract expiration cron ──────────────────────────────────────────


async def task_expire_contracts(ctx: dict) -> str:
    """SM-02: Daily cron — mark active/paused Contracts past ends_at as expired.

    Runs daily at 00:30 Africa/Maputo (22:30 UTC).
    Uses BYPASSRLS admin session — operates across all tenants.
    """
    from datetime import datetime

    import structlog
    from sqlalchemy import and_, update

    from app.modules.contracts.models import Contract

    logger = structlog.get_logger("worker")

    async with ctx["db_factory"]() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            update(Contract)
            .where(
                and_(
                    Contract.status.in_(["active", "paused"]),
                    Contract.ends_at != None,
                    Contract.ends_at < now,
                )
            )
            .values(status="expired")
            .returning(Contract.id)
        )
        expired_ids = result.scalars().all()
        await db.commit()

    count = len(expired_ids)
    logger.info("task_expire_contracts", count=count)
    return f"Expired {count} contracts"


# ── SM-04: DispatchClearance escalation cron ───────────────────────────────


async def task_escalate_pending_clearances(ctx: dict) -> str:
    """SM-04: Hourly cron — escalate pending dispatch clearances past SLA."""
    from datetime import datetime, timedelta

    import structlog
    from sqlalchemy import and_, select

    from app.modules.trip_orders.models import TripOrder

    logger = structlog.get_logger("worker")

    async with ctx["db_factory"]() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            select(TripOrder).where(
                and_(
                    TripOrder.status == "dispatch_pending",
                    TripOrder.escalated_at.is_(None),
                    TripOrder.created_at < now - timedelta(hours=1),
                )
            )
        )
        pending_orders = result.scalars().all()

        escalated = []
        for order in pending_orders:
            sla = order.clearance_sla_hours or 24
            if (now - order.created_at.replace(tzinfo=UTC)) > timedelta(hours=sla):
                order.escalated_at = now
                db.add(order)
                escalated.append(order.id)

        await db.commit()

    count = len(escalated)
    logger.info("task_escalate_pending_clearances", escalated_count=count)
    return f"Escalated {count} dispatch clearances past SLA"


# ── INFRA2-03: Prometheus metrics update cron ──────────────────────────────


async def task_update_active_tenants_metric(ctx: dict) -> str:
    """INFRA2-03: Update Prometheus active_tenants gauge every 5 minutes."""
    import structlog
    from sqlalchemy import func, select

    from app.modules.tenants.models import Tenant

    logger = structlog.get_logger("worker")

    async with ctx["db_factory"]() as db:
        result = await db.execute(select(func.count()).where(Tenant.is_active == True))
        count = result.scalar_one_or_none() or 0

    try:
        from prometheus_client import Gauge

        g = Gauge("rotas_active_tenants_total", "Number of active tenants in the platform")
        g.set(count)
    except Exception:
        pass

    logger.info("task_update_active_tenants_metric", active_tenants=count)
    return f"Active tenants: {count}"


# ── INFRA2-04: Worker heartbeat ───────────────────────────────────────────


async def task_worker_heartbeat(ctx: dict) -> str:
    """INFRA2-04: Worker heartbeat — update Redis key every 30 seconds."""
    from datetime import datetime

    import structlog

    logger = structlog.get_logger("worker")
    now = datetime.now(UTC).isoformat()

    redis = ctx.get("redis")
    if redis:
        await redis.setex("arq:health:worker_heartbeat", 90, now)
        logger.info("task_worker_heartbeat", timestamp=now)
        return f"Heartbeat: {now}"
    else:
        logger.warning("task_worker_heartbeat_no_redis")
        return "No Redis — heartbeat skipped"


class WorkerSettings:
    functions = [
        generate_billing_export,
        task_mark_overdue_billing_documents,
        task_expire_contracts,
        task_escalate_pending_clearances,
        task_update_active_tenants_metric,
        task_worker_heartbeat,
    ]
    cron_jobs = [
        # SM-01: Mark overdue billing documents — 01:00 Africa/Maputo = 23:00 UTC
        cron(task_mark_overdue_billing_documents, hour=23, minute=0),
        # SM-02: Expire contracts — 00:30 Africa/Maputo = 22:30 UTC
        cron(task_expire_contracts, hour=22, minute=30),
        # SM-04: Hourly escalation check
        cron(task_escalate_pending_clearances, minute=15),
        # INFRA2-03: Every 5 minutes
        cron(
            task_update_active_tenants_metric, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        ),
        # INFRA2-04: Worker heartbeat (every minute in ARQ cron if second not supported)
        cron(task_worker_heartbeat, minute=set(range(60))),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    max_tries = 3
    keep_result = 86400  # 24 hours
    on_startup = startup
    on_shutdown = shutdown
