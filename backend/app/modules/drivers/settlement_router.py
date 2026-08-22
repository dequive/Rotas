"""HTTP endpoints for trip settlements (liquidação do despacho)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.openapi_responses import PDF_RESPONSE
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.drivers import settlement_service
from app.modules.drivers.models import TripSettlement

router = APIRouter(prefix="/trips", tags=["settlements"])


class RejectSettlementRequest(BaseModel):
    reason: str


class SettlementResponse(BaseModel):
    """Mirrors `settlement_service.serialize_settlement`."""

    id: UUID
    tenant_id: UUID
    trip_id: UUID
    advance_id: UUID | None = None
    total_costs_mzn: Decimal
    advance_amount_mzn: Decimal
    balance_mzn: Decimal
    status: str
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    pdf_file_id: UUID | None = None
    settled_at: datetime | None = None


async def _get_settlement(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> TripSettlement:
    s = await db.scalar(
        select(TripSettlement).where(
            TripSettlement.trip_id == trip_id,
            TripSettlement.tenant_id == tenant_id,
        )
    )
    if not s:
        raise ApiError(
            "settlement_not_found",
            "No settlement found for this trip.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return s


@router.post(
    "/{trip_id}/settlement",
    status_code=status.HTTP_200_OK,
    response_model=SettlementResponse,
)
async def compute_settlement(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Compute or retrieve the financial settlement for a completed trip.

    Idempotent: calling multiple times returns the same settlement.
    Trip must be in 'completed' status.
    """
    return await settlement_service.compute_settlement(
        db,
        tenant_id=principal.tenant_id,
        trip_id=trip_id,
    )


@router.get("/{trip_id}/settlement", response_model=SettlementResponse)
async def get_settlement(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Get the settlement for a trip."""
    s = await _get_settlement(db, principal.tenant_id, trip_id)
    return settlement_service.serialize_settlement(s)


@router.post("/{trip_id}/settlement/approve", response_model=SettlementResponse)
async def approve_settlement(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Approve a pending settlement."""
    s = await _get_settlement(db, principal.tenant_id, trip_id)
    return await settlement_service.approve_settlement(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        settlement_id=s.id,
    )


@router.post("/{trip_id}/settlement/reject", response_model=SettlementResponse)
async def reject_settlement(
    trip_id: UUID,
    payload: RejectSettlementRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Reject a pending settlement with a reason."""
    s = await _get_settlement(db, principal.tenant_id, trip_id)
    return await settlement_service.reject_settlement(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        settlement_id=s.id,
        reason=payload.reason,
    )


@router.get("/{trip_id}/settlement/pdf", responses=PDF_RESPONSE)
async def download_settlement_pdf(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Download the settlement PDF. Generates it if not yet generated."""
    s = await _get_settlement(db, principal.tenant_id, trip_id)
    pdf_bytes = await settlement_service.generate_settlement_pdf(
        db,
        tenant_id=principal.tenant_id,
        settlement_id=s.id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="despacho-{trip_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
