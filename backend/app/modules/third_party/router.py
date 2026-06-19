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
    AssignmentCreate,
    DocumentCreate,
    DocumentVerify,
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


# ── Operational Documents (BEFORE /{tp_id} to avoid path conflict) ────────────


@router.post("/documents", status_code=201)
async def create_document(
    payload: DocumentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_document(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/documents/expiring")
async def get_expiring_documents(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    days_ahead: int = Query(30, ge=1, le=365),
):
    return await service.get_expiring_documents(db, principal.tenant_id, days_ahead)


@router.get("/documents")
async def list_documents(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    subject_type: str | None = Query(None),
    subject_id: UUID | None = Query(None),
    verification_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_documents(
        db, principal.tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )


@router.post("/documents/{doc_id}/verify")
async def verify_document(
    doc_id: UUID,
    payload: DocumentVerify,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.verify_document(
        db, principal.tenant_id, doc_id, payload, actor_id=principal.user_id
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


# ── Driver-Vehicle Assignments ────────────────────────────────────────────────


@router.post("/driver-vehicle-assignments", status_code=201)
async def assign_driver_to_vehicle(
    payload: AssignmentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.assign_driver_to_vehicle(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/driver-vehicle-assignments")
async def list_assignments(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    driver_id: UUID | None = Query(None),
    vehicle_id: UUID | None = Query(None),
    current_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_assignments(
        db, principal.tenant_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        current_only=current_only,
        limit=limit,
        offset=offset,
    )


@router.delete("/driver-vehicle-assignments/{assignment_id}", status_code=200)
async def unassign_driver_from_vehicle(
    assignment_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.unassign_driver_from_vehicle(
        db, principal.tenant_id, assignment_id, actor_id=principal.user_id
    )
