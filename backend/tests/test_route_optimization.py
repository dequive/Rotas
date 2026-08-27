import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.gps.models import GpsDevice
from app.modules.operational_exceptions.models import OperationalException
from app.modules.trips.models import Trip
from app.modules.trips.routing import (
    calculate_haversine_fallback,
    check_route_deviation,
    haversine_distance_km,
    optimize_waypoint_sequence,
    perpendicular_distance_km,
)


def test_haversine_distance():
    # Maputo to Beira (~720km)
    maputo = (-25.9692, 32.5732)
    beira = (-19.8436, 34.8389)
    dist = haversine_distance_km(maputo[0], maputo[1], beira[0], beira[1])
    assert 700.0 <= dist <= 750.0


def test_optimize_waypoints_greedy():
    origin = {"lat": -25.9692, "lon": 32.5732}  # Maputo
    destination = {"lat": -19.8436, "lon": 34.8389}  # Beira

    stops = [
        {"id": "stop_beira_near", "location": {"lat": -20.0, "lon": 34.7}},
        {"id": "stop_xai_xai", "location": {"lat": -25.0444, "lon": 33.6444}},
        {"id": "stop_maxixe", "location": {"lat": -23.8597, "lon": 35.3472}},
    ]

    ordered = optimize_waypoint_sequence(origin, destination, stops)
    assert len(ordered) == 3
    # Xai-Xai should be first stop after Maputo
    assert ordered[0]["id"] == "stop_xai_xai"
    assert ordered[0]["sequence_number"] == 1
    assert ordered[1]["id"] == "stop_maxixe"
    assert ordered[1]["sequence_number"] == 2
    assert ordered[2]["id"] == "stop_beira_near"
    assert ordered[2]["sequence_number"] == 3


def test_perpendicular_distance_and_deviation():
    # Straight horizontal segment from (-25.0, 32.0) to (-25.0, 34.0)
    seg_a = (-25.0, 32.0)
    seg_b = (-25.0, 34.0)

    # Point 2km north
    p_near = (-24.982, 33.0)
    dist_near = perpendicular_distance_km(p_near, seg_a, seg_b)
    assert dist_near < 3.0
    assert not check_route_deviation(p_near, [seg_a, seg_b], threshold_km=5.0)

    # Point 10km north (~0.09 degrees lat)
    p_far = (-24.90, 33.0)
    dist_far = perpendicular_distance_km(p_far, seg_a, seg_b)
    assert dist_far > 8.0
    assert check_route_deviation(p_far, [seg_a, seg_b], threshold_km=5.0)


def test_haversine_fallback():
    waypoints = [
        {"lat": -25.9692, "lon": 32.5732},
        {"lat": -25.0444, "lon": 33.6444},
    ]
    res = calculate_haversine_fallback(waypoints)
    assert res["source"] == "haversine_fallback"
    assert res["distance_km"] > 0
    assert len(res["geometry"]) == 2


@pytest.mark.asyncio
async def test_gps_ingestion_creates_deviation_alert(db: AsyncSession, tenant_id: uuid.UUID):
    from app.modules.drivers.models import Driver
    from app.modules.vehicles.models import Vehicle

    vehicle_id = uuid.uuid4()
    driver_id = uuid.uuid4()
    imei = f"test-imei-{uuid.uuid4().hex[:8]}"
    secret = "secret123"

    vehicle = Vehicle(id=vehicle_id, tenant_id=tenant_id, plate="ABC-123-MC", brand="Volvo", model="FH", year=2022)
    driver = Driver(id=driver_id, tenant_id=tenant_id, full_name="Test Driver", license_number="12345")
    db.add(vehicle)
    db.add(driver)
    await db.flush()

    # Create GpsDevice
    device = GpsDevice(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        imei=imei,
        device_secret=secret,
        is_active=True,
    )
    db.add(device)

    # Create Active Trip with route geometry along lat=-25.0, lon=32.0 to 34.0
    trip = Trip(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin="Maputo",
        origin_location={"lat": -25.0, "lon": 32.0},
        destination="Maxixe",
        destination_location={"lat": -25.0, "lon": 34.0},
        status="in_progress",
        route_geometry=[[-25.0, 32.0], [-25.0, 34.0]],
    )
    db.add(trip)
    await db.commit()

    # Ingest position 15km off route (lat=-24.8, lon=33.0)
    import hashlib
    import hmac
    import json
    body_dict = {"lat": -24.8, "lon": 33.0, "speed": 60, "heading": 90}
    body_bytes = json.dumps(body_dict).encode()
    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/gps/webhook/{imei}",
            content=body_bytes,
            headers={"Content-Type": "application/json", "X-Device-Signature": sig},
        )
        assert resp.status_code == 200

    # Verify exception created
    ex = await db.scalar(
        select(OperationalException).where(
            OperationalException.tenant_id == tenant_id,
            OperationalException.entity_type == "trip",
            OperationalException.entity_id == trip.id,
            OperationalException.exception_type == "route_deviation",
        )
    )
    assert ex is not None
    assert ex.severity == "high"
