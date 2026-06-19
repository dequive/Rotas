from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.database import AsyncSessionLocal
from app.modules.third_party import service
from app.modules.third_party.schemas import (
    RoleCreate,
    ServiceProviderProfileCreate,
    SupplierProfileCreate,
    ThirdPartyCreate,
    ThirdPartyUpdate,
)

router = APIRouter(prefix="/third-party", tags=["third-party"])


async def _get_anon_session() -> AsyncIterator[AsyncSession]:
    """Unauthenticated session for reference-data endpoints (no RLS needed)."""
    async with AsyncSessionLocal() as session:
        yield session


# ── Province reference (no auth needed — platform reference data) ─────────────

@router.get("/provinces")
async def list_provinces(
    db: Annotated[AsyncSession, Depends(_get_anon_session)],
):
    return await service.list_provinces(db)


# ── Third party CRUD ─────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_third_party(
    payload: ThirdPartyCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_third_party(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("")
async def list_third_parties(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_third_parties(
        db, principal.tenant_id, status=status, limit=limit, offset=offset
    )


# ── Sub-resource routes BEFORE /{tp_id} to avoid UUID path conflicts ──────────


@router.get("/{tp_id}/roles")
async def list_roles(
    tp_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_roles(db, principal.tenant_id, tp_id)


@router.post("/{tp_id}/roles", status_code=201)
async def create_role(
    tp_id: UUID,
    payload: RoleCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_role(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


@router.put("/{tp_id}/supplier-profile", status_code=200)
async def upsert_supplier_profile(
    tp_id: UUID,
    payload: SupplierProfileCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.upsert_supplier_profile(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


@router.put("/{tp_id}/service-provider-profile", status_code=200)
async def upsert_service_provider_profile(
    tp_id: UUID,
    payload: ServiceProviderProfileCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.upsert_service_provider_profile(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


# ── Single third party (after all sub-resource routes) ───────────────────────


@router.get("/{tp_id}")
async def get_third_party(
    tp_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_third_party(db, principal.tenant_id, tp_id)


@router.patch("/{tp_id}")
async def update_third_party(
    tp_id: UUID,
    payload: ThirdPartyUpdate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.update_third_party(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )
