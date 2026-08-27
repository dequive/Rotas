from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.main import app
from app.modules.trips.exporters import render_trip_report


def test_trip_report_accepts_orm_shaped_vehicle_and_driver() -> None:
    trip = SimpleNamespace(
        id=uuid4(),
        origin="Maputo",
        destination="Matola",
        status="closed",
        waybill_number="GR-2026-0001",
        actual_departure=datetime(2026, 7, 26, 8, 0, tzinfo=UTC),
        actual_arrival=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
        distance_km=18,
        total_fuel_cost=100,
        total_expense_cost=50,
        total_transport_cost=25,
        actual_revenue=500,
    )
    vehicle = SimpleNamespace(plate="ABC-12-34")
    driver = SimpleNamespace(full_name="Motorista Teste")

    pdf = render_trip_report(trip, vehicle=vehicle, driver=driver)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1_000


def test_dispatch_clearance_operations_publish_success_schemas() -> None:
    paths = app.openapi()["paths"]
    operations = (
        ("/api/v1/trips/{trip_id}/dispatch-clearance/request", "post"),
        ("/api/v1/trips/dispatch-clearances", "get"),
        ("/api/v1/trips/{trip_id}/dispatch-clearance/approve", "post"),
    )

    for path, method in operations:
        response = paths[path][method]["responses"]["200"]
        schema = response["content"]["application/json"]["schema"]
        assert schema, f"{method.upper()} {path} must publish a typed success schema"
