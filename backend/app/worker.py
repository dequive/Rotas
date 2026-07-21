"""ARQ background worker for ROTAS. Handles billing export jobs and KPI cache refresh."""

from datetime import UTC

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.jobs.tasks.billing_export import task_export_compliance_report
from app.jobs.tasks.document_expiry import scan_expiring_documents
from app.jobs.tasks.housekeeping import run_housekeeping
from app.jobs.tasks.maintenance import check_maintenance_schedules, check_vehicle_maintenance
from app.jobs.tasks.notifications import deliver_queued_notifications

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
    ctx["session_factory"] = ctx["db_factory"]  # alias used by app.jobs.tasks.*
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
                    Contract.ends_at.is_not(None),
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
        result = await db.execute(select(func.count()).where(Tenant.is_active.is_(True)))
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


# ── TP-10: Document expiry alert cron ────────────────────────────────────────


async def task_check_document_expiry(ctx: dict) -> str:
    """TP-10: Daily cron — generate alerts for operational_documents expiring within 30 days.

    Uses BYPASSRLS admin session (cross-tenant scan).
    Alert deduplication: create_alert() is idempotent on request_reference.
    request_reference format: 'doc_expiry:{doc_id}:{expiry_date.isoformat()}'
    — includes doc.id to prevent collisions between documents with same expiry date.

    Runs daily at 06:00 Africa/Maputo = 04:00 UTC.
    """
    from datetime import date, timedelta

    import structlog
    from sqlalchemy import and_, select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.third_party.models import OperationalDocument

    logger = structlog.get_logger("worker")
    today = date.today()
    cutoff = today + timedelta(days=30)
    alert_count = 0

    async with ctx["db_factory"]() as db:
        # Admin session bypasses RLS — query all tenants' expiring documents in one pass
        result = await db.execute(
            select(OperationalDocument).where(
                and_(
                    OperationalDocument.expiry_date.isnot(None),
                    OperationalDocument.expiry_date >= today,
                    OperationalDocument.expiry_date <= cutoff,
                )
            )
        )
        docs = result.scalars().all()

        for doc in docs:
            days_remaining = (doc.expiry_date - today).days
            priority = "critical" if days_remaining <= 7 else "high"
            # Deterministic request_reference: includes doc.id to prevent cross-document collisions
            request_reference = f"doc_expiry:{doc.id}:{doc.expiry_date.isoformat()}"

            payload = AlertCreate(
                request_reference=request_reference,
                alert_type="document_expiring_soon",
                priority=priority,
                entity_type=doc.subject_type,
                entity_id=doc.subject_id,
                title=f"Document expiring: {doc.document_type}",
                message=(
                    f"Document '{doc.document_type}' "
                    f"(subject: {doc.subject_type} {doc.subject_id}) "
                    f"expires in {days_remaining} day(s) on {doc.expiry_date.isoformat()}."
                ),
                channel="dashboard",
            )
            try:
                await create_alert(db, doc.tenant_id, payload)
                alert_count += 1
            except Exception as exc:
                # Log and continue — do not abort the whole batch for one document
                # create_alert raises ApiError(409) on duplicate request_reference with
                # different values; same-values duplicates are returned silently (idempotent).
                logger.warning(
                    "task_check_document_expiry_alert_error",
                    doc_id=str(doc.id),
                    error=str(exc),
                )

    logger.info("task_check_document_expiry", alerts_generated=alert_count)
    return f"Generated {alert_count} document expiry alerts"


# ── INS-02: Insurance renewal alert cron ─────────────────────────────────────


async def task_check_insurance_renewals(ctx: dict) -> str:
    """INS-02: Daily cron — generate alerts for vehicle insurance policies expiring
    in 60, 30, and 7 days. Deduplicates via request_reference.
    Uses BYPASSRLS admin session for cross-tenant scan.
    Runs daily at 07:00 Africa/Maputo = 05:00 UTC.
    """
    from datetime import date, timedelta

    import structlog
    from sqlalchemy import and_, select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.vehicles.models import Vehicle, VehicleInsurance

    logger = structlog.get_logger("worker")
    today = date.today()
    alert_count = 0
    THRESHOLDS = [60, 30, 7]

    async with ctx["db_factory"]() as db:
        for days in THRESHOLDS:
            target_date = today + timedelta(days=days)
            result = await db.execute(
                select(VehicleInsurance, Vehicle.plate)
                .join(Vehicle, Vehicle.id == VehicleInsurance.vehicle_id)
                .where(
                    and_(
                        VehicleInsurance.valid_until == target_date,
                    )
                )
            )
            rows = result.all()
            for ins, plate in rows:
                priority = "critical" if days <= 7 else "high" if days <= 30 else "medium"
                try:
                    await create_alert(
                        db,
                        ins.tenant_id,
                        AlertCreate(
                            alert_type="insurance_renewal",
                            priority=priority,
                            entity_type="vehicle_insurance",
                            entity_id=ins.id,
                            title="Apólice de seguro a renovar",
                            message=(
                                f"Apólice {ins.policy_number} do veículo {plate} "
                                f"vence em {days} dias ({ins.valid_until.isoformat()})"
                            ),
                            channel="dashboard",
                            request_reference=(
                                f"ins_renewal:{ins.id}:{ins.valid_until.isoformat()}:{days}d"
                            ),
                        ),
                    )
                    alert_count += 1
                except Exception:
                    # Duplicate key (same request_reference) — already alerted, skip silently
                    pass

    logger.info("task_check_insurance_renewals", alerts_created=alert_count)
    return f"Insurance renewal alerts created: {alert_count}"


# ── NOTIF-01: Notification outbox flush — see app.jobs.tasks.notifications ───
# deliver_queued_notifications imported at top; registered in WorkerSettings below.
# It supersedes the previous task_process_notification_outbox with exponential
# backoff (5 attempts), dead-letter support, and HTML email body.

# ── NOTIF-02: Dispatch rejected notification (on-demand) ─────────────────────


async def task_notify_dispatch_rejected(ctx: dict, order_id: str, tenant_id: str) -> str:
    """NOTIF-02: Notify tenant admins when a dispatch clearance is rejected.

    Triggered on-demand by trip_orders/router.py on clearance rejection.
    Enqueues email notification to all active owner/admin users of the tenant.
    Idempotent via enqueue_email request_reference — safe to retry.
    Not a cron — registered in functions only.
    """
    from uuid import UUID

    import structlog
    from sqlalchemy import and_, select

    from app.modules.notifications.schemas import EmailNotificationCreate
    from app.modules.notifications.service import enqueue_email
    from app.modules.trip_orders.models import TripOrder
    from app.modules.users.models import User

    logger = structlog.get_logger("worker")
    _tenant_id = UUID(tenant_id)
    _order_id = UUID(order_id)

    async with ctx["db_factory"]() as db:
        order = await db.scalar(
            select(TripOrder).where(
                TripOrder.id == _order_id,
                TripOrder.tenant_id == _tenant_id,
            )
        )
        if not order:
            logger.warning("task_notify_dispatch_rejected_order_not_found", order_id=order_id)
            return f"Order {order_id} not found"

        result = await db.execute(
            select(User).where(
                and_(
                    User.tenant_id == _tenant_id,
                    User.role.in_(["owner", "admin"]),
                    User.email.isnot(None),
                    User.is_active.is_(True),
                )
            )
        )
        users = result.scalars().all()

        order_ref = order.customer_reference or str(order.id)[:8].upper()
        reason = order.rejection_reason or "Sem motivo indicado."
        notified = 0

        for user in users:
            ref = f"dispatch_rejected:{order.id}:{user.id}"
            body = (
                f"O despacho da ordem #{order_ref} "
                f"({order.origin} -> {order.destination}) foi rejeitado.\n\n"
                f"Motivo: {reason}\n\n"
                "Aceda ao painel de gestao para rever e reencaminhar a ordem."
            )
            try:
                await enqueue_email(
                    db,
                    _tenant_id,
                    EmailNotificationCreate(
                        request_reference=ref,
                        recipient=user.email,
                        subject=f"Despacho rejeitado — Ordem #{order_ref}",
                        body_text=body,
                    ),
                    actor_id=None,
                )
                notified += 1
            except Exception as exc:
                logger.warning(
                    "task_notify_dispatch_rejected_enqueue_error",
                    user_id=str(user.id),
                    error=str(exc)[:200],
                )

        await db.commit()

    logger.info("task_notify_dispatch_rejected", order_id=order_id, notified=notified)
    return f"Dispatch rejected notification: {notified} user(s) notified"


# ── NOTIF-04: Driver document expiry alert cron ──────────────────────────────


async def task_check_driver_document_expiry(ctx: dict) -> str:
    """NOTIF-04: Daily cron — generate alerts for driver documents expiring within 30 days.

    Reads Driver.documents JSON column (same shape as Vehicle.documents):
      {doc_type: {"expiry_date": "YYYY-MM-DD", ...}, ...}

    Mirrors task_check_vehicle_document_expiry pattern exactly.
    Licence and identity document types covered here; HOS is separate (task_check_hos_violations).
    Deduplication: create_alert() is idempotent on request_reference.
    request_reference format: 'driver_doc:{driver.id}:{doc_type}:{expiry_date}'
    Runs daily at 05:00 UTC (07:00 Africa/Maputo).
    """
    from datetime import date, timedelta

    import structlog
    from sqlalchemy import select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.drivers.models import Driver

    logger = structlog.get_logger("worker")
    today = date.today()
    cutoff = today + timedelta(days=30)
    alert_count = 0

    async with ctx["db_factory"]() as db:
        result = await db.execute(select(Driver).where(Driver.documents.isnot(None)))
        drivers = result.scalars().all()

        for driver in drivers:
            docs = driver.documents or {}
            if not isinstance(docs, dict):
                continue
            for doc_type, doc_data in docs.items():
                if not isinstance(doc_data, dict):
                    continue
                raw_expiry = doc_data.get("expiry_date")
                if not raw_expiry:
                    continue
                try:
                    expiry_date = date.fromisoformat(str(raw_expiry))
                except (ValueError, TypeError):
                    continue
                if not (today <= expiry_date <= cutoff):
                    continue

                days_remaining = (expiry_date - today).days
                priority = "critical" if days_remaining <= 7 else "high"
                request_reference = f"driver_doc:{driver.id}:{doc_type}:{expiry_date.isoformat()}"

                try:
                    await create_alert(
                        db,
                        driver.tenant_id,
                        AlertCreate(
                            request_reference=request_reference,
                            alert_type="driver_document_expiring_soon",
                            priority=priority,
                            entity_type="driver",
                            entity_id=driver.id,
                            title=f"Documento a vencer — {doc_type}",
                            message=(
                                f"Documento '{doc_type}' do motorista vence em "
                                f"{days_remaining} dia(s) ({expiry_date.isoformat()})."
                            ),
                            channel="dashboard",
                        ),
                    )
                    alert_count += 1
                except Exception as exc:
                    logger.warning(
                        "task_check_driver_document_expiry_error",
                        driver_id=str(driver.id),
                        doc_type=doc_type,
                        error=str(exc),
                    )

    logger.info("task_check_driver_document_expiry", alerts_generated=alert_count)
    return f"Generated {alert_count} driver document expiry alerts"


# ── HOS-01: HOS violation scan cron ──────────────────────────────────────────


async def task_check_hos_violations(ctx: dict) -> str:
    """HOS-01: Every 30 min — detect drivers on active trips exceeding HOS limits.

    Scans all drivers with trips currently in active statuses. Calls
    calculate_driving_hours() per driver. Generates:
      - alert_type="driver_hos_warning"   when status=="warning"   (>= 8h today)
      - alert_type="driver_hos_violation" when status=="violation"  (>= 9h today or >= 48h week)

    Deduplication: request_reference includes the ISO date to generate at most
    one alert per driver per day per severity level.

    Uses BYPASSRLS admin session — cross-tenant scan.
    """
    from datetime import UTC, datetime

    import structlog
    from sqlalchemy import select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.drivers.hos_service import (
        HOS_VIOLATION_HOURS_DAY,
        HOS_VIOLATION_HOURS_WEEK,
        HOS_WARNING_HOURS_DAY,
        calculate_driving_hours,
    )
    from app.modules.trips.models import Trip

    logger = structlog.get_logger("worker")
    today = datetime.now(UTC).date()
    today_iso = today.isoformat()
    warnings = 0
    violations = 0

    ACTIVE_STATUSES = ("in_progress", "delayed", "incident")

    async with ctx["db_factory"]() as db:
        # Find distinct drivers currently on active trips (cross-tenant)
        result = await db.execute(
            select(Trip.driver_id, Trip.tenant_id)
            .where(Trip.status.in_(ACTIVE_STATUSES), Trip.driver_id.isnot(None))
            .distinct()
        )
        active_drivers = result.all()

        for driver_id, tenant_id in active_drivers:
            hos = await calculate_driving_hours(driver_id, tenant_id, db, target_date=today)
            status = hos["status"]
            if status == "ok":
                continue

            alert_type = "driver_hos_warning" if status == "warning" else "driver_hos_violation"
            priority = "high" if status == "warning" else "critical"
            violation_reason = hos.get("violation_reason")

            if violation_reason == "daily_limit":
                detail = f"{hos['hours_today']:.1f}h hoje (limite: {HOS_VIOLATION_HOURS_DAY}h)"
            elif violation_reason == "weekly_limit":
                detail = (
                    f"{hos['hours_this_week']:.1f}h esta semana "
                    f"(limite: {HOS_VIOLATION_HOURS_WEEK}h)"
                )
            else:
                # warning branch: no violation_reason set
                detail = f"{hos['hours_today']:.1f}h hoje (limite: {HOS_WARNING_HOURS_DAY}h)"

            request_reference = f"hos:{driver_id}:{today_iso}:{status}"
            try:
                await create_alert(
                    db,
                    tenant_id,
                    AlertCreate(
                        request_reference=request_reference,
                        alert_type=alert_type,
                        priority=priority,
                        entity_type="driver",
                        entity_id=driver_id,
                        title=f"HOS {'alerta' if status == 'warning' else 'violação'} — motorista",
                        message=f"Motorista acumulou {detail} de condução.",
                        channel="dashboard",
                    ),
                )
                if status == "warning":
                    warnings += 1
                else:
                    violations += 1
            except Exception as exc:
                logger.warning(
                    "task_check_hos_violations_alert_error",
                    driver_id=str(driver_id),
                    error=str(exc),
                )

    logger.info("task_check_hos_violations", warnings=warnings, violations=violations)
    return f"HOS: {warnings} warnings, {violations} violations"


# ── NOTIF-03: Vehicle document expiry alert cron ──────────────────────────────


async def task_check_vehicle_document_expiry(ctx: dict) -> str:
    """NOTIF-03: Daily cron — generate alerts for vehicle documents expiring within 30 days.

    Reads Vehicle.documents JSON column (shape: {doc_type: {expiry_date: "YYYY-MM-DD", ...}}).
    Deduplication: create_alert() is idempotent on request_reference.
    request_reference format: 'vehicle_doc:{vehicle.id}:{doc_type}:{expiry_date}'
    Insurance is separately covered by task_check_insurance_renewals (INS-02).
    Runs daily at 06:30 Africa/Maputo = 04:30 UTC.
    """
    from datetime import date, timedelta

    import structlog
    from sqlalchemy import select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.vehicles.models import Vehicle

    logger = structlog.get_logger("worker")
    today = date.today()
    cutoff = today + timedelta(days=30)
    alert_count = 0

    async with ctx["db_factory"]() as db:
        result = await db.execute(select(Vehicle).where(Vehicle.documents.isnot(None)))
        vehicles = result.scalars().all()

        for vehicle in vehicles:
            docs = vehicle.documents or {}
            for doc_type, doc_data in docs.items():
                if not isinstance(doc_data, dict):
                    continue
                expiry_str = doc_data.get("expiry_date")
                if not expiry_str:
                    continue
                try:
                    expiry_date = date.fromisoformat(expiry_str)
                except ValueError:
                    continue
                if expiry_date < today or expiry_date > cutoff:
                    continue

                days_remaining = (expiry_date - today).days
                priority = "critical" if days_remaining <= 7 else "high"
                request_reference = f"vehicle_doc:{vehicle.id}:{doc_type}:{expiry_date.isoformat()}"

                try:
                    await create_alert(
                        db,
                        vehicle.tenant_id,
                        AlertCreate(
                            request_reference=request_reference,
                            alert_type="vehicle_document_expiring_soon",
                            priority=priority,
                            entity_type="vehicle",
                            entity_id=vehicle.id,
                            title=f"Documento de viatura a expirar: {doc_type}",
                            message=(
                                f"Documento '{doc_type}' da viatura {vehicle.plate} "
                                f"expira em {days_remaining} dia(s) ({expiry_date.isoformat()})."
                            ),
                            channel="dashboard",
                        ),
                    )
                    alert_count += 1
                except Exception as exc:
                    logger.warning(
                        "task_check_vehicle_document_expiry_alert_error",
                        vehicle_id=str(vehicle.id),
                        doc_type=doc_type,
                        error=str(exc),
                    )

    logger.info("task_check_vehicle_document_expiry", alerts_generated=alert_count)
    return f"Generated {alert_count} vehicle document expiry alerts"


async def task_expire_gps_partitions(ctx: dict) -> str:
    """Drop gps_positions partitions older than 90 days (GPS-07 — storage bloat prevention)."""
    from datetime import date, timedelta

    import structlog
    from sqlalchemy import text

    logger = structlog.get_logger("worker")
    dropped = []
    cutoff = date.today() - timedelta(days=90)
    async with ctx["db_factory"]() as db:
        # List all gps_positions_YYYY_MM partitions
        result = await db.execute(
            text(
                "SELECT relname FROM pg_class "
                "WHERE relname LIKE 'gps_positions_%' "
                "AND relkind = 'r' "
                "AND relname ~ '^gps_positions_\\d{4}_\\d{2}$'"
            )
        )
        partitions = [row[0] for row in result.fetchall()]
        for part in partitions:
            # parse YYYY_MM from name
            try:
                _, _, year_str, month_str = part.split("_")
                part_date = date(int(year_str), int(month_str), 1)
            except (ValueError, IndexError):
                continue
            if part_date < cutoff.replace(day=1):
                await db.execute(text(f"DROP TABLE IF EXISTS {part} CASCADE"))
                dropped.append(part)
        await db.commit()

    logger.info("task_expire_gps_partitions", dropped=dropped)
    return f"Dropped {len(dropped)} GPS partitions: {dropped}"


async def task_outbox_drain(ctx: dict) -> str:
    """Stabilization/P0-F8: drain the ROTAS -> Governance transactional outbox.

    Picks up pending outbox rows (respecting next_attempt_at), ships them to
    the configured governance engine, records the returned ``case_id`` and
    reschedules failures with exponential backoff. Honors
    ``FF_GOVERNANCE_OUTBOX`` — when the flag is off, the cycle is a no-op.
    """
    import structlog

    from app.modules.outbox import drain_outbox

    logger = structlog.get_logger("worker.outbox")
    async with ctx["db_factory"]() as db:
        counts = await drain_outbox(db, max_rows=100)

    if counts["scanned"] == 0:
        return "outbox_drain: nothing to do"
    logger.info("outbox_drain", **counts)
    return (
        f'outbox_drain: scanned={counts["scanned"]} sent={counts["sent"]} '
        f'retried={counts["retried"]} dead_letter={counts["dead_letter"]}'
    )


class WorkerSettings:
    functions = [
        # Billing
        generate_billing_export,
        task_export_compliance_report,
        # State-machine crons
        task_mark_overdue_billing_documents,
        task_expire_contracts,
        task_escalate_pending_clearances,
        # Infrastructure
        task_update_active_tenants_metric,
        task_worker_heartbeat,
        run_housekeeping,
        # Document expiry alerts
        task_check_document_expiry,  # OperationalDocument (third-party docs)
        scan_expiring_documents,  # Driver + vehicle docs via analytics
        task_check_vehicle_document_expiry,  # Vehicle.documents JSON column
        task_check_driver_document_expiry,  # Driver.documents JSON column (NOTIF-04)
        task_check_hos_violations,  # HOS violation scan (HOS-01)
        # Insurance
        task_check_insurance_renewals,
        # Notifications
        deliver_queued_notifications,  # Replaces task_process_notification_outbox
        task_notify_dispatch_rejected,
        # Maintenance
        check_maintenance_schedules,
        check_vehicle_maintenance,
        # GPS
        task_expire_gps_partitions,
        # Stabilization/P0-F8: governability-outbox drainer
        task_outbox_drain,
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
        # INFRA2-04: Worker heartbeat every minute
        cron(task_worker_heartbeat, minute=set(range(60))),
        # MAINT-01: Daily maintenance schedule check — 02:00 UTC
        cron(check_maintenance_schedules, hour=2, minute=0),
        # Driver + vehicle document expiry — 03:00 UTC
        cron(scan_expiring_documents, hour=3, minute=0),
        # TP-10: Third-party operational document expiry alerts — 04:00 UTC
        cron(task_check_document_expiry, hour=4, minute=0),
        # NOTIF-03: Vehicle document expiry alerts — 04:30 UTC
        cron(task_check_vehicle_document_expiry, hour=4, minute=30),
        # Housekeeping: idempotency key + audit log cleanup — 04:15 UTC
        cron(run_housekeeping, hour=4, minute=15),
        # NOTIF-04: Driver document expiry alerts — 05:00 UTC (07:00 Africa/Maputo)
        cron(task_check_driver_document_expiry, hour=5, minute=0),
        # HOS-01: HOS violation scan — every 30 minutes
        cron(task_check_hos_violations, minute={0, 30}),
        # INS-02: Insurance renewal alerts — 07:30 Africa/Maputo = 05:30 UTC
        cron(task_check_insurance_renewals, hour=5, minute=30),
        # NOTIF-01: Flush notification outbox every 5 minutes (exponential backoff, dead-letter)
        cron(
            deliver_queued_notifications,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
        # GPS-07: Drop gps_positions partitions older than 90 days — daily 06:00 UTC
        cron(task_expire_gps_partitions, hour=6, minute=0),
        # STAB-F8: Outbox drainer every 5 minutes (gated by FF_GOVERNANCE_OUTBOX)
        cron(
            task_outbox_drain,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    max_tries = 3
    keep_result = 86400  # 24 hours
    on_startup = startup
    on_shutdown = shutdown
