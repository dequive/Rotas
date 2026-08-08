"""GPS ingestion service — webhook processing, HMAC auth, position storage."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.gps.models import GpsDevice, GpsPosition, VehicleLastPosition

# ── Serializers ───────────────────────────────────────────────────────────────


def serialize_device(d: GpsDevice) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "tenant_id": str(d.tenant_id),
        "vehicle_id": str(d.vehicle_id),
        "imei": d.imei,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat(),
    }


def serialize_last_position(p: VehicleLastPosition) -> dict[str, Any]:
    staleness_seconds = (datetime.now(UTC) - p.recorded_at).total_seconds()
    return {
        "vehicle_id": str(p.vehicle_id),
        "tenant_id": str(p.tenant_id),
        "lat": p.lat,
        "lon": p.lon,
        "speed_kmh": str(p.speed_kmh) if p.speed_kmh is not None else None,
        "heading_deg": p.heading_deg,
        "recorded_at": p.recorded_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "is_stale": staleness_seconds > 300,
        "staleness_seconds": int(staleness_seconds),
    }


# ── HMAC validation ───────────────────────────────────────────────────────────


def verify_device_signature(device_secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(device_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Normalization ─────────────────────────────────────────────────────────────


def normalize_position(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize GPS device payload to internal schema.

    Supports Teltonika FMB (lat/lon/speed/angle) and Coban GT06 (latitude/longitude/speed/course).
    Falls back to direct field access if neither matches.
    """
    lat = raw.get("lat") or raw.get("latitude") or raw.get("Lat") or raw.get("LAT")
    lon = (
        raw.get("lon") or raw.get("lng") or raw.get("longitude") or raw.get("Lon") or raw.get("LON")
    )
    speed = raw.get("speed") or raw.get("Speed") or raw.get("spd")
    heading = raw.get("angle") or raw.get("heading") or raw.get("course") or raw.get("Heading")
    accuracy = raw.get("accuracy") or raw.get("hdop")
    ts = raw.get("timestamp") or raw.get("recorded_at") or raw.get("time") or raw.get("dt")

    if lat is None or lon is None:
        raise ApiError(
            "invalid_position",
            "Payload missing lat/lon fields",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    recorded_at: datetime
    if isinstance(ts, (int, float)):
        recorded_at = datetime.fromtimestamp(ts, tz=UTC)
    elif isinstance(ts, str):
        try:
            recorded_at = datetime.fromisoformat(ts)
            if recorded_at.tzinfo is None:
                recorded_at = recorded_at.replace(tzinfo=UTC)
        except ValueError:
            recorded_at = datetime.now(UTC)
    else:
        recorded_at = datetime.now(UTC)

    return {
        "lat": float(lat),
        "lon": float(lon),
        "speed_kmh": Decimal(str(speed)) if speed is not None else None,
        "heading_deg": int(heading) if heading is not None else None,
        "accuracy_m": Decimal(str(accuracy)) if accuracy is not None else None,
        "recorded_at": recorded_at,
    }


# ── Public API ────────────────────────────────────────────────────────────────


async def ingest_position(
    db: AsyncSession,
    imei: str,
    signature: str,
    body: bytes,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate HMAC, normalize payload, store position, upsert vehicle_last_position."""
    device = await db.scalar(
        select(GpsDevice).where(GpsDevice.imei == imei, GpsDevice.is_active == True)  # noqa: E712
    )
    if not device:
        raise ApiError(
            "device_not_found",
            "IMEI not registered or inactive",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not verify_device_signature(device.device_secret, body, signature):
        raise ApiError(
            "invalid_signature",
            "X-Device-Signature mismatch",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    norm = normalize_position(raw_payload)

    pos = GpsPosition(
        id=uuid.uuid4(),
        tenant_id=device.tenant_id,
        vehicle_id=device.vehicle_id,
        device_id=device.id,
        raw_payload=raw_payload,
        **norm,
    )
    db.add(pos)

    # Upsert vehicle_last_position
    stmt = (
        pg_insert(VehicleLastPosition)
        .values(
            vehicle_id=device.vehicle_id,
            tenant_id=device.tenant_id,
            lat=norm["lat"],
            lon=norm["lon"],
            speed_kmh=norm["speed_kmh"],
            heading_deg=norm["heading_deg"],
            recorded_at=norm["recorded_at"],
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["vehicle_id"],
            set_={
                "lat": norm["lat"],
                "lon": norm["lon"],
                "speed_kmh": norm["speed_kmh"],
                "heading_deg": norm["heading_deg"],
                "recorded_at": norm["recorded_at"],
                "updated_at": datetime.now(UTC),
            },
            where=text("vehicle_last_position.recorded_at < EXCLUDED.recorded_at"),
        )
    )
    await db.execute(stmt)
    await db.commit()

    return {"accepted": True, "vehicle_id": str(device.vehicle_id)}


async def get_fleet_positions(db: AsyncSession, tenant_id: UUID) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(VehicleLastPosition).where(VehicleLastPosition.tenant_id == tenant_id)
    )
    return [serialize_last_position(r) for r in rows]


async def register_device(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    imei: str,
) -> dict[str, Any]:
    existing = await db.scalar(select(GpsDevice).where(GpsDevice.imei == imei))
    if existing:
        raise ApiError(
            "imei_exists", "IMEI already registered", status_code=status.HTTP_409_CONFLICT
        )

    device = GpsDevice(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        imei=imei,
        device_secret=secrets.token_hex(32),
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    result = serialize_device(device)
    result["device_secret"] = device.device_secret
    return result


async def get_trip_eta(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> dict[str, Any] | None:
    """Haversine ETA from last position to trip destination via known_routes."""
    from app.modules.trips.models import Trip

    trip = await db.scalar(select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id))
    if not trip:
        raise ApiError("trip_not_found", "Trip not found", status_code=status.HTTP_404_NOT_FOUND)

    pos = await db.scalar(
        select(VehicleLastPosition).where(VehicleLastPosition.vehicle_id == trip.vehicle_id)
    )
    if not pos:
        return None

    staleness = (datetime.now(UTC) - pos.recorded_at).total_seconds()
    if staleness > 300 or (pos.speed_kmh is None or pos.speed_kmh == 0):
        return {
            "eta_minutes": None,
            "reason": "stale_or_stopped",
            "last_position": serialize_last_position(pos),
        }

    # Destination from known_routes or trip.destination string
    from app.modules.trips.models import KnownRoute

    route = await db.scalar(
        select(KnownRoute).where(
            KnownRoute.tenant_id == tenant_id,
            KnownRoute.origin == trip.origin,
            KnownRoute.destination == trip.destination,
        )
    )

    destination_lat = getattr(route, "destination_lat", None)
    destination_lon = getattr(route, "destination_lon", None)
    if destination_lat is not None and destination_lon is not None:
        dest_lat, dest_lon = float(destination_lat), float(destination_lon)
    else:
        return {
            "eta_minutes": None,
            "reason": "destination_coordinates_unknown",
            "last_position": serialize_last_position(pos),
        }

    # Haversine distance in km
    R = 6371.0
    lat1, lon1 = math.radians(pos.lat), math.radians(pos.lon)
    lat2, lon2 = math.radians(dest_lat), math.radians(dest_lon)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance_km = R * 2 * math.asin(math.sqrt(a))

    speed = float(pos.speed_kmh)
    eta_minutes = int((distance_km / speed) * 60) if speed > 0 else None

    return {
        "eta_minutes": eta_minutes,
        "distance_km": round(distance_km, 2),
        "speed_kmh": str(pos.speed_kmh),
        "last_position": serialize_last_position(pos),
        "reason": None,
    }
