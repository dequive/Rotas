"""Generic procurement document PDF generation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, require_permission
from app.modules.documents.exporters import render_purchase_order, render_requisition
from app.modules.documents.schemas import PurchaseOrderRequest, RequisitionRequest
from app.modules.tenants.models import TenantDocumentProfile

router = APIRouter(prefix="/documents", tags=["documents"])


async def _get_profile(db: AsyncSession, tenant_id: object) -> dict | None:
    row = await db.scalar(
        select(TenantDocumentProfile).where(
            TenantDocumentProfile.tenant_id == tenant_id
        )
    )
    if not row:
        return None
    return {
        "legal_name": row.legal_name,
        "address_line1": row.address_line1,
        "address_line2": row.address_line2,
        "city": row.city,
        "phone": row.phone,
        "email": row.email,
    }


@router.post("/purchase-order/pdf", summary="Gerar Ordem de Compra em PDF")
async def generate_purchase_order_pdf(
    payload: PurchaseOrderRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    profile = await _get_profile(db, principal.tenant_id)
    items = [i.model_dump() for i in payload.items]
    pdf_bytes = render_purchase_order(
        reference=payload.reference,
        date=payload.date,
        supplier_name=payload.entity.name,
        supplier_contact=payload.entity.contact,
        supplier_nuit=payload.entity.nuit,
        items=items,
        notes=payload.notes,
        currency=payload.currency,
        payment_terms=payload.payment_terms,
        delivery_deadline=payload.delivery_deadline,
        profile=profile,
    )
    ref_slug = payload.reference[:30].replace("/", "-").replace(" ", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ordem-compra-{ref_slug}.pdf"},
    )


@router.post("/requisition/pdf", summary="Gerar Requisição Interna ou Externa em PDF")
async def generate_requisition_pdf(
    payload: RequisitionRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    profile = await _get_profile(db, principal.tenant_id)
    items = [i.model_dump() for i in payload.items]
    pdf_bytes = render_requisition(
        req_type=payload.type,
        reference=payload.reference,
        date=payload.date,
        entity_name=payload.entity.name,
        entity_contact=payload.entity.contact,
        entity_nuit=payload.entity.nuit,
        requester_department=payload.requester_department,
        items=items,
        notes=payload.notes,
        currency=payload.currency,
        profile=profile,
    )
    kind = "interna" if payload.type == "internal" else "externa"
    ref_slug = payload.reference[:30].replace("/", "-").replace(" ", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=requisicao-{kind}-{ref_slug}.pdf"},
    )
