"""ARQ background worker for ROTAS. Handles billing export jobs and KPI cache refresh."""
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def startup(ctx: dict) -> None:
    import sentry_sdk
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings as _get_settings
    from app.main import _scrub_pii

    _settings = _get_settings()
    # INFRA-01: Sentry in ARQ worker — init before any job processing (D-04)
    if _settings.sentry_dsn_backend:
        sentry_sdk.init(
            dsn=_settings.sentry_dsn_backend,
            environment=_settings.environment,
            traces_sample_rate=0.05,
            before_send=_scrub_pii,
        )
    # D-18 / RLS-02: ARQ worker uses rotas_admin role (BYPASSRLS) for cross-tenant queries.
    # resolved_admin_database_url falls back to database_url in local dev where RLS may not
    # be active — no local dev config change required.
    admin_engine = create_async_engine(
        _settings.resolved_admin_database_url,
        pool_pre_ping=True,
    )
    ctx["db_factory"] = async_sessionmaker(admin_engine, expire_on_commit=False)
    ctx["admin_engine"] = admin_engine  # store for cleanup in shutdown


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
    from pathlib import Path
    from uuid import UUID

    from sqlalchemy import select

    from app.config import get_settings as _get_settings
    from app.modules.billing.exporters import render_billing_export
    from app.modules.billing.models import BillingDocument, BillingItem, ExportJob
    from app.modules.tenants.models import Tenant

    _settings = _get_settings()
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
                await db.execute(
                    select(BillingItem).where(
                        BillingItem.billing_document_id == doc.id,
                        BillingItem.tenant_id == UUID(tenant_id),
                    )
                )
            ).scalars().all()

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

            # Save file to LOCAL_UPLOAD_DIR / tenant_id
            upload_dir = Path(_settings.local_upload_dir) / tenant_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / artifact.filename
            file_path.write_bytes(artifact.content)

            job.status = "done"
            job.file_path = str(file_path)
            await db.commit()
            return {"job_id": job_id, "status": "done", "file_path": str(file_path)}

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:500]
            await db.commit()
            return {"error": str(exc)}


class WorkerSettings:
    functions = [generate_billing_export]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    max_tries = 3
    keep_result = 86400  # 24 hours — keep job results for 1 day
    on_startup = startup
    on_shutdown = shutdown
