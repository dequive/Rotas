"""
Platform admin — tenant provisioning.

POST /platform/onboard atomically:
  1. Creates Tenant record
  2. Creates an initial API key with full scopes
  3. Bootstraps the ROTAS taxonomy for that tenant
  4. Returns tenant_id + full_key (one-time, never retrievable again)

Protected by X-Platform-Key (static secret from PLATFORM_ADMIN_KEY env var).
Uses get_raw_session() — operates outside tenant RLS.
"""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.rotas.service import RotasAdapterService
from core.auth import generate_api_key
from core.config import get_settings
from core.database import AsyncSessionLocal, get_raw_session, set_rls_tenant
from core.limiter import limiter
from core.models_auth import ApiKey, Tenant

router = APIRouter(prefix="/platform", tags=["platform"])

_FULL_SCOPES = [
    "occurrences:read",
    "occurrences:write",
    "cases:read",
    "cases:write",
    "admin:read",
    "admin:write",
    "adapter:rotas",
]


class OnboardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9\-]+$")
    platform_key: str = Field(..., description="Must match PLATFORM_ADMIN_KEY env var")
    bootstrap_rotas: bool = Field(True, description="Auto-bootstrap ROTAS taxonomy")


class OnboardResponse(BaseModel):
    tenant_id: UUID
    api_key_id: UUID
    key_prefix: str
    full_key: str
    bootstrap_result: dict | None = None


@router.post("/onboard", status_code=201, response_model=OnboardResponse)
@limiter.limit("5/minute", key_func=get_remote_address)
async def onboard_tenant(
    request: Request,
    body: OnboardRequest,
    db: AsyncSession = Depends(get_raw_session),
) -> OnboardResponse:
    settings = get_settings()

    # Constant-time comparison to prevent timing attacks
    expected = settings.platform_admin_key.get_secret_value()
    if not secrets.compare_digest(body.platform_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=403, detail={"code": "forbidden", "message": "Invalid platform key."}
        )

    # Slug uniqueness check (tenants has no RLS — safe on raw session)
    existing = await db.scalar(select(Tenant).where(Tenant.slug == body.slug))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": f"Slug '{body.slug}' already exists."},
        )

    tenant = Tenant(name=body.name, slug=body.slug)
    db.add(tenant)
    await db.flush()

    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        tenant_id=tenant.id,
        label="default",
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=_FULL_SCOPES,
    )
    db.add(api_key)
    await db.flush()
    await db.commit()

    bootstrap_result: dict | None = None
    if body.bootstrap_rotas:
        # Bootstrap runs with RLS active for the new tenant
        set_rls_tenant(str(tenant.id))
        try:
            async with AsyncSessionLocal() as rls_db:
                await rls_db.execute(
                    text("SELECT set_config('app.tenant_id', :tid, false)"),
                    {"tid": str(tenant.id)},
                )
                svc = RotasAdapterService(rls_db, tenant.id, api_key.id)
                bootstrap_result = await svc.bootstrap()
        finally:
            set_rls_tenant(None)

    return OnboardResponse(
        tenant_id=tenant.id,
        api_key_id=api_key.id,
        key_prefix=prefix,
        full_key=full_key,
        bootstrap_result=bootstrap_result,
    )
