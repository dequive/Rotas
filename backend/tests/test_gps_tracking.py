"""Phase 12 — GPS ingestion + customer tracking tests.

GPS-01  Webhook with valid HMAC stores position + upserts vehicle_last_position
GPS-02  Webhook with invalid HMAC returns 401
GPS-03  Unknown IMEI returns 401
GPS-04  get_fleet_positions returns last known positions for tenant
GPS-05  create_tracking_token generates token for in_progress trip
GPS-06  get_public_tracking_payload returns trip status + driver + position
GPS-07  Expired tracking token returns 410
GPS-08  ETA returns None when no position exists
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.drivers.models import Driver
from app.modules.gps import service as gps_service
from app.modules.gps.models import GpsDevice, TrackingToken, VehicleLastPosition
from app.modules.tracking import service as tracking_service
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_vehicle(db, tenant_id):
    v = Vehicle(tenant_id=tenant_id, plate=f"GPS-{uuid4().hex[:6].upper()}", status="active")
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(tenant_id=tenant_id, full_name=f"Driver {uuid4().hex[:6]}", status="active")
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, vehicle, driver, status="in_progress"):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Beira",
        status=status,
    )
    db.add(t)
    await db.flush()
    return t


async def _make_device(db, tenant_id, vehicle):
    secret = secrets.token_hex(16)
    d = GpsDevice(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        imei=f"35{uuid4().hex[:13]}",
        device_secret=secret,
        is_active=True,
    )
    db.add(d)
    await db.flush()
    return d


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gps01_valid_webhook_stores_position(db, tenant_id):
    """GPS-01: Valid HMAC webhook stores GpsPosition and upserts VehicleLastPosition."""
    vehicle = await _make_vehicle(db, tenant_id)
    device = await _make_device(db, tenant_id, vehicle)
    await db.commit()

    payload = {"lat": -25.9, "lon": 32.6, "speed": 80, "timestamp": datetime.now(UTC).isoformat()}
    import json

    body = json.dumps(payload).encode()
    sig = _sign(device.device_secret, body)

    result = await gps_service.ingest_position(
        db, imei=device.imei, signature=sig, body=body, raw_payload=payload
    )

    assert result["accepted"] is True
    assert result["vehicle_id"] == str(vehicle.id)

    from sqlalchemy import select

    pos = await db.scalar(
        select(VehicleLastPosition).where(VehicleLastPosition.vehicle_id == vehicle.id)
    )
    assert pos is not None
    assert abs(pos.lat - (-25.9)) < 0.001
    assert abs(pos.lon - 32.6) < 0.001


@pytest.mark.asyncio
async def test_gps02_invalid_hmac_rejected(db, tenant_id):
    """GPS-02: Invalid HMAC signature returns 401 ApiError."""
    from app.core.errors import ApiError

    vehicle = await _make_vehicle(db, tenant_id)
    device = await _make_device(db, tenant_id, vehicle)
    await db.commit()

    import json

    payload = {"lat": -25.9, "lon": 32.6}
    body = json.dumps(payload).encode()

    with pytest.raises(ApiError) as exc_info:
        await gps_service.ingest_position(
            db, imei=device.imei, signature="badhex", body=body, raw_payload=payload
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_signature"


@pytest.mark.asyncio
async def test_gps03_unknown_imei_rejected(db, tenant_id):
    """GPS-03: Unknown IMEI returns 401 ApiError."""
    import json

    from app.core.errors import ApiError

    payload = {"lat": -25.9, "lon": 32.6}
    body = json.dumps(payload).encode()

    with pytest.raises(ApiError) as exc_info:
        await gps_service.ingest_position(
            db, imei="000000000000000", signature="any", body=body, raw_payload=payload
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "device_not_found"


@pytest.mark.asyncio
async def test_gps04_get_fleet_positions(db, tenant_id):
    """GPS-04: get_fleet_positions returns all last-known positions for tenant."""
    vehicle = await _make_vehicle(db, tenant_id)
    now = datetime.now(UTC)
    pos = VehicleLastPosition(
        vehicle_id=vehicle.id,
        tenant_id=tenant_id,
        lat=-26.0,
        lon=32.7,
        speed_kmh=Decimal("60.0"),
        recorded_at=now,
        updated_at=now,
    )
    db.add(pos)
    await db.commit()

    results = await gps_service.get_fleet_positions(db, tenant_id=tenant_id)
    assert len(results) >= 1
    vehicle_ids = [r["vehicle_id"] for r in results]
    assert str(vehicle.id) in vehicle_ids


@pytest.mark.asyncio
async def test_gps05_create_tracking_token(db, tenant_id):
    """GPS-05: create_tracking_token returns a token for an in_progress trip."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="in_progress")
    await db.commit()

    result = await tracking_service.create_tracking_token(
        db, tenant_id=tenant_id, user_id=uuid4(), trip_id=trip.id
    )

    assert result["trip_id"] == str(trip.id)
    assert len(result["token"]) >= 32
    assert "expires_at" in result


@pytest.mark.asyncio
async def test_gps06_public_tracking_payload(db, tenant_id):
    """GPS-06: Public payload includes trip status, driver name, last position."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="in_progress")
    await db.commit()

    token_result = await tracking_service.create_tracking_token(
        db, tenant_id=tenant_id, user_id=uuid4(), trip_id=trip.id
    )
    token_val = token_result["token"]

    payload = await tracking_service.get_public_tracking_payload(db, token_val=token_val)

    assert payload["status"] == "in_progress"
    assert payload["driver_name"] == driver.full_name
    assert payload["vehicle_plate"] == vehicle.plate


@pytest.mark.asyncio
async def test_gps07_expired_token_returns_410(db, tenant_id):
    """GPS-07: Expired tracking token raises ApiError 410."""
    from app.core.errors import ApiError

    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    await db.flush()

    expired_token = TrackingToken(
        tenant_id=tenant_id,
        trip_id=trip.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(expired_token)
    await db.commit()

    with pytest.raises(ApiError) as exc_info:
        await tracking_service.get_public_tracking_payload(db, token_val=expired_token.token)

    assert exc_info.value.status_code == 410
    assert exc_info.value.code == "token_expired"


@pytest.mark.asyncio
async def test_gps08_eta_no_position_returns_none(db, tenant_id):
    """GPS-08: ETA returns None when vehicle has no GPS position."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="in_progress")
    await db.commit()

    result = await gps_service.get_trip_eta(db, tenant_id=tenant_id, trip_id=trip.id)

    assert result is None
