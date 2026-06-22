"""Tracking router — token management + public tracking endpoint."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.database import get_session_raw
from app.modules.tracking import service

router = APIRouter(tags=["tracking"])


@router.post("/tracking-tokens", status_code=status.HTTP_201_CREATED)
async def create_token(
    body: dict,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a shareable customer tracking link for an active trip."""
    require_permission(principal, FLEET_WRITE)
    return await service.create_tracking_token(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        trip_id=UUID(body["trip_id"]),
        expires_hours=int(body.get("expires_hours", 72)),
    )


@router.get("/tracking-tokens")
async def list_tokens(
    trip_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    require_permission(principal, FLEET_READ)
    return await service.list_tracking_tokens(
        db, tenant_id=principal.tenant_id, trip_id=trip_id, limit=limit, offset=offset
    )


@router.get("/public/track/{token}")
async def public_track(
    token: str,
    db: AsyncSession = Depends(get_session_raw),
) -> dict:
    """Public endpoint — no auth. Returns shipment status + last position for customer."""
    return await service.get_public_tracking_payload(db, token_val=token)
