"""Customer tracking portal service — token generation + public payload assembly."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.gps.models import TrackingToken, VehicleLastPosition
from app.modules.gps.service import serialize_last_position


def serialize_token(t: TrackingToken) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "trip_id": str(t.trip_id),
        "token": t.token,
        "expires_at": t.expires_at.isoformat(),
        "created_at": t.created_at.isoformat(),
    }


async def create_tracking_token(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    trip_id: UUID,
    expires_hours: int = 72,
) -> dict[str, Any]:
    from app.modules.trips.models import Trip

    trip = await db.scalar(select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id))
    if not trip:
        raise ApiError("trip_not_found", "Trip not found", status_code=status.HTTP_404_NOT_FOUND)
    if trip.status not in ("in_progress", "planned"):
        raise ApiError(
            "trip_not_trackable",
            "Tracking only available for active trips",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    token_val = secrets.token_urlsafe(32)
    token = TrackingToken(
        tenant_id=tenant_id,
        trip_id=trip_id,
        token=token_val,
        expires_at=datetime.now(UTC) + timedelta(hours=expires_hours),
        created_by=user_id,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return serialize_token(token)


async def get_public_tracking_payload(db: AsyncSession, token_val: str) -> dict[str, Any]:
    """Return public (no-auth) tracking payload. Used by /track/{token} page."""
    token = await db.scalar(select(TrackingToken).where(TrackingToken.token == token_val))
    if not token:
        raise ApiError(
            "token_not_found",
            "Tracking link not found or expired",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    now = datetime.now(UTC)
    if token.expires_at < now:
        raise ApiError(
            "token_expired", "This tracking link has expired", status_code=status.HTTP_410_GONE
        )

    from app.modules.cargo.models import DeliveryProof
    from app.modules.drivers.models import Driver
    from app.modules.trips.models import Trip
    from app.modules.vehicles.models import Vehicle

    trip = await db.scalar(select(Trip).where(Trip.id == token.trip_id))
    driver = await db.scalar(select(Driver).where(Driver.id == trip.driver_id)) if trip else None
    vehicle = (
        await db.scalar(select(Vehicle).where(Vehicle.id == trip.vehicle_id)) if trip else None
    )
    last_pos = (
        await db.scalar(
            select(VehicleLastPosition).where(VehicleLastPosition.vehicle_id == trip.vehicle_id)
        )
        if trip
        else None
    )

    # Latest delivery proof photo
    (
        await db.scalar(
            select(DeliveryProof)
            .where(DeliveryProof.trip_id == token.trip_id)
            .order_by(DeliveryProof.created_at.desc())
            .limit(1)
        )
        if trip
        else None
    )

    return {
        "trip_id": str(token.trip_id),
        "status": trip.status if trip else "unknown",
        "origin": trip.origin if trip else None,
        "destination": trip.destination if trip else None,
        "driver_name": driver.full_name if driver else None,
        "vehicle_plate": vehicle.plate if vehicle else None,
        "last_position": serialize_last_position(last_pos) if last_pos else None,
        "delivery_proof_photo_url": None,  # TODO: resolve file URL via files module
        "expires_at": token.expires_at.isoformat(),
        "generated_at": now.isoformat(),
    }


async def list_tracking_tokens(
    db: AsyncSession,
    tenant_id: UUID,
    trip_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    q = select(TrackingToken).where(TrackingToken.tenant_id == tenant_id)
    if trip_id:
        q = q.where(TrackingToken.trip_id == trip_id)
    rows = await db.scalars(q.order_by(TrackingToken.created_at.desc()).limit(limit).offset(offset))
    return [serialize_token(t) for t in rows]
