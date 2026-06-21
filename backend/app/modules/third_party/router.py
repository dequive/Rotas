from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.database import AsyncSessionLocal
from app.modules.third_party import service
from app.modules.third_party.schemas import (
    AssignmentCreate,
    ContactCreate,
    DocumentCreate,
    DocumentVerify,
    EvaluationCreate,
    PartyDirectoryEntry,
    PaymentCreate,
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
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_third_party(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("")
async def list_third_parties(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = Query(None),
    role_type: str | None = Query(None, description="Filter by role type"),
    name: str | None = Query(None, description="Case-insensitive name search (ILIKE)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_third_parties(
        db,
        principal.tenant_id,
        status=status,
        role_type=role_type,
        name=name,
        limit=limit,
        offset=offset,
    )


# ── Party Directory (BEFORE /{tp_id} to avoid UUID path conflict) ────────────


@router.get("/party-directory", response_model=list[PartyDirectoryEntry])
async def party_directory(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(None, description="Name search string (ILIKE)"),
    subject_type: str | None = Query(
        None,
        description="Filter to one subject type: driver | client | third_party",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    subject_types = [subject_type] if subject_type else None
    return await service.search_party_directory(
        db,
        principal.tenant_id,
        query=q,
        subject_types=subject_types,
        limit=limit,
        offset=offset,
    )


# ── Operational Documents (BEFORE /{tp_id} to avoid path conflict) ────────────


@router.post("/documents", status_code=201)
async def create_document(
    payload: DocumentCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_document(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/documents/expiring")
async def get_expiring_documents(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    days_ahead: int = Query(30, ge=1, le=365),
):
    return await service.get_expiring_documents(db, principal.tenant_id, days_ahead)


@router.get("/documents")
async def list_documents(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    subject_type: Annotated[str | None, Query()] = None,
    subject_id: Annotated[UUID | None, Query()] = None,
    verification_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_documents(
        db,
        principal.tenant_id,
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
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.verify_document(
        db, principal.tenant_id, doc_id, payload, actor_id=principal.user_id
    )


# ── Sub-resource routes BEFORE /{tp_id} to avoid UUID path conflicts ──────────


@router.get("/{tp_id}/roles")
async def list_roles(
    tp_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_roles(db, principal.tenant_id, tp_id)


@router.post("/{tp_id}/roles", status_code=201)
async def create_role(
    tp_id: UUID,
    payload: RoleCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_role(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


@router.put("/{tp_id}/supplier-profile", status_code=200)
async def upsert_supplier_profile(
    tp_id: UUID,
    payload: SupplierProfileCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.upsert_supplier_profile(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


@router.put("/{tp_id}/service-provider-profile", status_code=200)
async def upsert_service_provider_profile(
    tp_id: UUID,
    payload: ServiceProviderProfileCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.upsert_service_provider_profile(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


# ── Single third party (after all sub-resource routes) ───────────────────────


@router.get("/{tp_id}")
async def get_third_party(
    tp_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_third_party(db, principal.tenant_id, tp_id)


@router.patch("/{tp_id}")
async def update_third_party(
    tp_id: UUID,
    payload: ThirdPartyUpdate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.update_third_party(
        db, principal.tenant_id, tp_id, payload, actor_id=principal.user_id
    )


# ── Driver-Vehicle Assignments ────────────────────────────────────────────────


@router.post("/driver-vehicle-assignments", status_code=201)
async def assign_driver_to_vehicle(
    payload: AssignmentCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.assign_driver_to_vehicle(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/driver-vehicle-assignments")
async def list_assignments(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    driver_id: Annotated[UUID | None, Query()] = None,
    vehicle_id: Annotated[UUID | None, Query()] = None,
    current_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_assignments(
        db,
        principal.tenant_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        current_only=current_only,
        limit=limit,
        offset=offset,
    )


@router.delete("/driver-vehicle-assignments/{assignment_id}", status_code=200)
async def unassign_driver_from_vehicle(
    assignment_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.unassign_driver_from_vehicle(
        db, principal.tenant_id, assignment_id, actor_id=principal.user_id
    )


# ── Contacts ──────────────────────────────────────────────────────────────────


@router.post("/{third_party_id}/contacts", status_code=201)
async def create_contact(
    third_party_id: UUID,
    payload: ContactCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="third_party.contact.create",
        entity_type="third_party_contact",
        payload=payload,
        handler=lambda: service.create_contact(
            db, principal.tenant_id, third_party_id, payload, principal.user_id
        ),
    )


@router.get("/{third_party_id}/contacts")
async def list_contacts(
    third_party_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_contacts(db, principal.tenant_id, third_party_id)


@router.delete("/{third_party_id}/contacts/{contact_id}", status_code=204)
async def delete_contact(
    third_party_id: UUID,
    contact_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await service.delete_contact(
        db, principal.tenant_id, third_party_id, contact_id, principal.user_id
    )


# ── Ledger / account ──────────────────────────────────────────────────────────


@router.get("/{third_party_id}/account")
async def get_supplier_account(
    third_party_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    date_from: Annotated[date | None, Query(alias="date_from")] = None,
    date_to: Annotated[date | None, Query(alias="date_to")] = None,
):
    return await service.get_supplier_account(
        db, principal.tenant_id, third_party_id, date_from=date_from, date_to=date_to
    )


@router.get("/{third_party_id}/account/statement.pdf")
async def get_supplier_statement_pdf(
    third_party_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    date_from: Annotated[date | None, Query(alias="date_from")] = None,
    date_to: Annotated[date | None, Query(alias="date_to")] = None,
):
    from sqlalchemy import select

    from app.modules.tenants.models import TenantDocumentProfile
    from app.modules.third_party.exporters import render_supplier_statement
    from app.modules.third_party.models import ThirdParty

    tp_row = await db.execute(
        select(ThirdParty).where(
            ThirdParty.id == third_party_id,
            ThirdParty.tenant_id == principal.tenant_id,
        )
    )
    tp = tp_row.scalar_one_or_none()
    if tp is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Third party not found")

    prof_row = await db.execute(
        select(TenantDocumentProfile).where(
            TenantDocumentProfile.tenant_id == principal.tenant_id
        )
    )
    prof_obj = prof_row.scalar_one_or_none()
    profile = (
        {
            "legal_name": prof_obj.legal_name,
            "address_line1": prof_obj.address_line1,
            "address_line2": prof_obj.address_line2,
            "city": prof_obj.city,
            "phone": prof_obj.phone,
            "email": prof_obj.email,
        }
        if prof_obj
        else None
    )

    account = await service.get_supplier_account(
        db, principal.tenant_id, third_party_id, date_from=date_from, date_to=date_to
    )

    pdf_bytes = render_supplier_statement(
        tp,
        account["entries"],
        date_from=date_from,
        date_to=date_to,
        opening_balance=account.get("opening_balance"),
        total_debits=account["total_debits"],
        total_credits=account["total_credits"],
        balance=account["balance"],
        profile=profile,
    )
    tp_slug = (tp.name or "fornecedor").lower().replace(" ", "-")[:40]
    filename = f"extrato-{tp_slug}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/{third_party_id}/payments", status_code=201)
async def create_payment(
    third_party_id: UUID,
    payload: PaymentCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="third_party.payment.create",
        entity_type="supplier_ledger_entry",
        payload=payload,
        handler=lambda: service.create_payment(
            db, principal.tenant_id, third_party_id, payload, principal.user_id
        ),
    )


# ── Evaluations ───────────────────────────────────────────────────────────────


@router.post("/{third_party_id}/evaluations", status_code=201)
async def create_evaluation(
    third_party_id: UUID,
    payload: EvaluationCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="third_party.evaluation.create",
        entity_type="supplier_evaluation",
        payload=payload,
        handler=lambda: service.create_evaluation(
            db, principal.tenant_id, third_party_id, payload, principal.user_id
        ),
    )


@router.get("/{third_party_id}/evaluations")
async def list_evaluations(
    third_party_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_evaluations(db, principal.tenant_id, third_party_id)
