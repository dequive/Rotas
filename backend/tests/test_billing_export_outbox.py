from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.billing import service as billing_service
from app.modules.billing.models import BillingDocument, ExportJob
from app.modules.outbox.models import OutboxEvent


async def _document(db, tenant_id):
    now = datetime.now(UTC)
    document = BillingDocument(
        tenant_id=tenant_id,
        client_name=f"Export client {uuid4().hex[:8]}",
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="issued",
        currency="MZN",
    )
    db.add(document)
    await db.commit()
    return document


@pytest.mark.asyncio
async def test_billing_export_job_and_dispatch_are_atomic_and_idempotent(db, tenant_id):
    document = await _document(db, tenant_id)

    first = await billing_service.enqueue_export_job(
        db, tenant_id, document.id, "pdf"
    )
    replay = await billing_service.enqueue_export_job(
        db, tenant_id, document.id, "pdf"
    )

    assert replay == first
    job_id = first["job_id"]
    assert (
        await db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.tenant_id == tenant_id,
                ExportJob.entity_id == document.id,
                ExportJob.job_type == "billing_pdf",
            )
        )
        == 1
    )
    event = await db.scalar(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == job_id,
            OutboxEvent.event_type == "billing.internal.export.dispatch",
        )
    )
    assert event is not None
    assert event.payload["document_id"] == str(document.id)


@pytest.mark.asyncio
async def test_export_job_rolls_back_if_durable_dispatch_cannot_be_recorded(
    db, tenant_id, monkeypatch
):
    document = await _document(db, tenant_id)
    document_id = document.id

    async def fail_enqueue(*_args, **_kwargs):
        raise RuntimeError("simulated outbox failure")

    monkeypatch.setattr("app.modules.outbox.enqueue", fail_enqueue)
    with pytest.raises(RuntimeError, match="simulated outbox failure"):
        await billing_service.enqueue_export_job(
            db, tenant_id, document_id, "xlsx"
        )
    await db.rollback()

    assert (
        await db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.tenant_id == tenant_id,
                ExportJob.entity_id == document_id,
                ExportJob.job_type == "billing_xlsx",
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_compliance_export_deduplicates_per_month_not_across_months(db, tenant_id):
    july = await billing_service.create_compliance_report_job(
        db, tenant_id, "2026-07"
    )
    july_replay = await billing_service.create_compliance_report_job(
        db, tenant_id, "2026-07"
    )
    august = await billing_service.create_compliance_report_job(
        db, tenant_id, "2026-08"
    )

    assert july_replay == july
    assert august["job_id"] != july["job_id"]
    assert (
        await db.scalar(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.tenant_id == tenant_id,
                OutboxEvent.event_type
                == "billing.internal.compliance_report.dispatch",
            )
        )
        == 2
    )
