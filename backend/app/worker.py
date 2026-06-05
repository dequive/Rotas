"""ARQ background worker for ROTAS. Handles billing export jobs and KPI cache refresh."""
from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def startup(ctx: dict) -> None:
    from app.database import AsyncSessionLocal

    ctx["db_factory"] = AsyncSessionLocal


async def shutdown(ctx: dict) -> None:
    pass


async def generate_billing_export(
    ctx: dict,
    job_id: str,
    document_id: str,
    export_format: str,
    tenant_id: str,
) -> dict:
    """ARQ task: generate PDF or XLSX for a billing document.

    Full implementation in Plan 06. This stub updates job status to 'processing' and back.
    """
    # Stub — Plan 06 implements the actual fpdf2/openpyxl generation
    return {"job_id": job_id, "status": "done", "file_path": None}


class WorkerSettings:
    functions = [generate_billing_export]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    max_tries = 3
    keep_result = 86400  # 24 hours — keep job results for 1 day
    on_startup = startup
    on_shutdown = shutdown
