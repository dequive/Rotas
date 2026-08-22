"""GPS router — webhook ingestion, fleet map, device management, ETA."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.database import get_session_raw
from app.modules.gps import service

router = APIRouter(tags=["gps"])


@router.post(
    "/gps/webhook/{imei}",
    status_code=status.HTTP_200_OK,
    response_model=None,
)
async def gps_webhook(
    imei: str,
    request: Request,
    x_device_signature: str = Header(..., alias="X-Device-Signature"),
    db: AsyncSession = Depends(get_session_raw),
) -> dict | Response:
    """Ingest a GPS position event from a device. No JWT — HMAC-SHA256 auth."""
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return await service.ingest_position(
        db, imei=imei, signature=x_device_signature, body=body, raw_payload=payload
    )


@router.get("/gps/vehicles/latest")
async def get_fleet_positions(
    principal: TenantPrincipal = Depends(require_permission(FLEET_READ)),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Last known position for every vehicle in this tenant's fleet."""
    return await service.get_fleet_positions(db, tenant_id=principal.tenant_id)


@router.post("/gps/devices", status_code=status.HTTP_201_CREATED)
async def register_gps_device(
    body: dict,
    principal: TenantPrincipal = Depends(require_permission(FLEET_WRITE)),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Register a GPS device IMEI and get back the device_secret for HMAC signing."""
    return await service.register_device(
        db,
        tenant_id=principal.tenant_id,
        vehicle_id=UUID(body["vehicle_id"]),
        imei=body["imei"],
    )


@router.get("/trips/{trip_id}/eta")
async def get_trip_eta(
    trip_id: UUID,
    principal: TenantPrincipal = Depends(require_permission(FLEET_READ)),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """ETA for an in-progress trip via Haversine distance from last GPS position."""
    result = await service.get_trip_eta(db, tenant_id=principal.tenant_id, trip_id=trip_id)
    if result is None:
        return {"eta_minutes": None, "reason": "no_position_data"}
    return result
