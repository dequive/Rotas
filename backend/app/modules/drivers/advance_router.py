"""HTTP endpoints for driver cash advances (despacho)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.drivers import advance_service

router = APIRouter(prefix="/trips", tags=["advances"])


class IssueAdvanceRequest(BaseModel):
    driver_id: UUID
    amount_mzn: Decimal = Field(..., gt=0, description="Advance amount in MZN, must be positive")
    allowance_mzn: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Allowance (Subsídio)"
    )
    expenses_mzn: Decimal = Field(default=Decimal("0.00"), ge=0, description="Operational Expenses")
    notes: str | None = None

    @model_validator(mode="after")
    def validate_amounts(self) -> IssueAdvanceRequest:
        if self.allowance_mzn + self.expenses_mzn != self.amount_mzn:
            raise ValueError("O montante total deve ser igual à soma do subsídio e das despesas.")
        return self


@router.post("/{trip_id}/advance", status_code=status.HTTP_201_CREATED)
async def issue_advance(
    trip_id: UUID,
    payload: IssueAdvanceRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Issue a cash advance (despacho) for a trip.

    Requires Idempotency-Key header to prevent double-posting from the UI.
    Trip must be in 'planned' or 'in_progress' status.
    One non-voided advance per trip maximum.
    """
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="driver_advance.issue",
        entity_type="driver_advance",
        payload=payload,
        handler=lambda: advance_service.issue_advance(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            trip_id=trip_id,
            driver_id=payload.driver_id,
            amount_mzn=payload.amount_mzn,
            allowance_mzn=payload.allowance_mzn,
            expenses_mzn=payload.expenses_mzn,
            notes=payload.notes,
            request_reference=str(idempotency_key) if idempotency_key else None,
        ),
    )


@router.get("/{trip_id}/advance")
async def get_trip_advance(
    trip_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(None, alias="status"),
):
    """Get advances for a trip (most recent non-voided first)."""
    return await advance_service.list_advances(
        db,
        tenant_id=principal.tenant_id,
        trip_id=trip_id,
        status_filter=status_filter,
        limit=10,
        offset=0,
    )


@router.delete("/{trip_id}/advance/{advance_id}")
async def void_advance(
    trip_id: UUID,
    advance_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Void an issued advance. Cannot void a settled advance."""
    return await advance_service.void_advance(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        advance_id=advance_id,
    )
