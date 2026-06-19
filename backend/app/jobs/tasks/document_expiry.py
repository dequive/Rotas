"""ARQ task: scan expiring documents across all tenants and create Alert records.

Cron: 03:00 UTC daily (offset from maintenance at 02:00 to avoid DB contention).
Uses ADMIN_DATABASE_URL (rotas_admin BYPASSRLS role) — scans all active tenants.

Idempotency:
  request_reference = f"doc_expiry:{tenant_id}:{entity_id}:{doc_type}:{iso_week}"
  where iso_week = date.today().isocalendar() formatted as "YYYY-Www".
  Same entity+doc_type produces the same reference within a calendar week → safe to re-run.
  409 from create_alert with alert_request_reference_reused is treated as an idempotent skip.
"""

import logging
from datetime import UTC, date, datetime

logger = logging.getLogger(__name__)


def _iso_week(d: date) -> str:
    """Format: '2026-W23' — stable within the calendar week."""
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _priority_from_severity(severity: str) -> str:
    """Map analytics severity label to Alert priority string."""
    return {"critical": "critical", "urgent": "high"}.get(severity, "medium")


async def scan_expiring_documents(ctx: dict) -> dict:
    """Daily cron: scan all active tenants for expiring driver and vehicle documents.

    Uses ADMIN_DATABASE_URL (BYPASSRLS) to query across tenants without RLS filter.
    For each expiring document found within a 30-day horizon, creates an Alert record
    (idempotent via request_reference scoped to calendar week).

    Returns summary dict: {tenants_scanned, alerts_created, alerts_skipped}.
    """
    from sqlalchemy import select

    from app.modules.alerts.schemas import AlertCreate
    from app.modules.alerts.service import create_alert
    from app.modules.analytics.service import get_document_expiry_alerts
    from app.modules.tenants.models import Tenant

    session_factory = ctx["session_factory"]
    today = datetime.now(UTC).date()
    iso_week = _iso_week(today)

    alerts_created = 0
    alerts_skipped = 0
    tenants_scanned = 0

    async with session_factory() as db:
        # Fetch all active tenants — BYPASSRLS role sees all rows
        tenants = (
            (
                await db.execute(
                    select(Tenant).where(Tenant.is_active == True).limit(500)  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        for tenant in tenants:
            tenants_scanned += 1
            try:
                items = await get_document_expiry_alerts(db, tenant.id, horizon_days=30)
            except Exception as exc:
                logger.warning(
                    "scan_expiring_documents: tenant %s error fetching alerts: %s",
                    tenant.id,
                    exc,
                )
                continue

            for item in items:
                entity_type = item["entity_type"]
                entity_id = item["entity_id"]
                doc_type = item["document_type"]
                days_remaining = item["days_remaining"]
                entity_name = item.get("entity_name", "")
                expires_at = item["expires_at"]
                severity = item.get("severity", "warning")

                # Stable reference within the calendar week — prevents duplicate alerts
                # Truncated to 120 chars (AlertCreate.request_reference max length)
                reference = (f"doc_expiry:{tenant.id}:{entity_id}:{doc_type}:{iso_week}")[:120]

                priority = _priority_from_severity(severity)
                doc_label = doc_type.replace("_", " ").title()
                title = f"Documento a expirar: {doc_label} — {entity_name}"[:200]
                message = (
                    f"{entity_type.capitalize()} {entity_name}: {doc_type} expira em "
                    f"{expires_at} ({days_remaining} dia(s))."
                )

                payload = AlertCreate(
                    request_reference=reference,
                    alert_type="document_expiring",
                    priority=priority,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=title,
                    message=message,
                    channel="dashboard",
                )
                try:
                    await create_alert(db, tenant.id, payload, actor_id=None)
                    alerts_created += 1
                except Exception as exc:
                    exc_str = str(exc)
                    if "alert_request_reference_reused" in exc_str:
                        # Same reference used this week — idempotent skip, not an error
                        alerts_skipped += 1
                    else:
                        logger.warning(
                            "scan_expiring_documents: alert creation failed tenant=%s ref=%s: %s",
                            tenant.id,
                            reference,
                            exc,
                        )
                        alerts_skipped += 1

    result = {
        "tenants_scanned": tenants_scanned,
        "alerts_created": alerts_created,
        "alerts_skipped": alerts_skipped,
    }
    logger.info("scan_expiring_documents complete: %s", result)
    return result
