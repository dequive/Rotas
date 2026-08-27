from uuid import uuid4

import pytest

from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle


@pytest.mark.asyncio
async def test_work_order_detail_is_aggregated_and_tenant_scoped(
    db, tenant_id, auth_headers, async_client
):
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"DET-{uuid4().hex[:6].upper()}",
        brand="Toyota",
        model="Hilux",
        category="ligeiro",
        fuel_type="gasoleo",
    )
    other_tenant = Tenant(name="Tenant isolado", slug=f"isolated-{uuid4().hex[:8]}")
    db.add_all([vehicle, other_tenant])
    await db.commit()

    request = await async_client.post(
        "/api/v1/workshop/maintenance-requests",
        headers={**auth_headers, "Idempotency-Key": f"detail:{uuid4()}"},
        json={
            "vehicle_id": str(vehicle.id),
            "request_type": "corrective",
            "priority": "normal",
            "description": "Ruído na suspensão dianteira.",
            "odometer_reading": 72000,
        },
    )
    assert request.status_code == 200
    order = await async_client.post(
        "/api/v1/workshop/work-orders",
        headers=auth_headers,
        json={
            "maintenance_request_id": request.json()["id"],
            "vehicle_id": str(vehicle.id),
            "diagnosis": "Casquilho com folga.",
            "planned_work": "Substituir casquilho e testar.",
            "estimated_cost": 3200,
        },
    )
    assert order.status_code == 200

    detail = await async_client.get(
        f"/api/v1/workshop/work-orders/{order.json()['id']}", headers=auth_headers
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["work_order"]["id"] == order.json()["id"]
    assert payload["vehicle"]["plate"] == vehicle.plate
    assert payload["client"]["is_fleet_owned"] is True
    assert payload["tasks"] == []
    assert payload["parts_issued"] == []
    assert payload["blockers"] == {"incomplete_tasks": 0, "unreturned_tools": 0}

    isolated = await async_client.get(
        f"/api/v1/workshop/work-orders/{order.json()['id']}",
        headers={"Authorization": "Bearer test-token", "X-Tenant-Id": str(other_tenant.id)},
    )
    assert isolated.status_code == 404
