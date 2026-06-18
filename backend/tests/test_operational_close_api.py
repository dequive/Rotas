import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip, TripExecutionEvent
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_seed_entities():
    from uuid import uuid4

    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Close {suffix}", slug=f"close-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"CLO-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Close {suffix}",
            phone=f"25887{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant.id, vehicle.id, driver.id


async def create_trip(client: httpx.AsyncClient, headers: dict[str, str], vehicle_id, driver_id):
    response = await client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "vehicle_id": str(vehicle_id),
            "driver_id": str(driver_id),
            "origin": "Nacala",
            "destination": "Pemba",
            "cargo_type": "Carga geral",
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_operational_close_requires_validated_pod_or_waiver() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_trip(client, headers, vehicle_id, driver_id)

            start_response = await client.post(
                f"/api/v1/trips/{trip['id']}/start",
                headers=headers,
                json={"km_start": 1200},
            )
            assert start_response.status_code == 200

            complete_response = await client.post(
                f"/api/v1/trips/{trip['id']}/complete",
                headers=headers,
                json={"km_end": 2500, "recipient_name": "Cliente Individual"},
            )
            assert complete_response.status_code == 200
            assert complete_response.json()["status"] == "arrived"

            close_response = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Tentativa sem POD"},
            )
            assert close_response.status_code == 409
            assert close_response.json()["error"]["code"] == "validated_pod_required"

            proof_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof",
                headers=headers,
                json={
                    "document_number": "POD-CLOSE-001",
                    "proof_type": "client_discharge_note",
                    "client_type": "company",
                    "delivered_at": "2026-06-22T13:00:00+00:00",
                    "quantity_delivered": 1,
                },
            )
            assert proof_response.status_code == 200
            proof = proof_response.json()

            close_with_pending_proof = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "POD ainda nao validado"},
            )
            assert close_with_pending_proof.status_code == 409

            validation_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/validate",
                headers=headers,
                json={"validation_method": "manual_review"},
            )
            assert validation_response.status_code == 200

            trip_cost_payload = {
                "cost_type": "toll",
                "description": "Portagem de rota.",
                "amount": 350,
                "request_reference": "close-flow:toll:001",
                "incurred_at": "2026-06-22T12:00:00+00:00",
            }
            cost_response = await client.post(
                f"/api/v1/trips/{trip['id']}/costs",
                headers=headers,
                json=trip_cost_payload,
            )
            assert cost_response.status_code == 200
            replay_response = await client.post(
                f"/api/v1/trips/{trip['id']}/costs",
                headers=headers,
                json=trip_cost_payload,
            )
            assert replay_response.status_code == 200
            assert replay_response.json()["id"] == cost_response.json()["id"]

            close_response = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers={**headers, "Idempotency-Key": "trip-close:validated-pod:001"},
                json={"notes": "Fecho operacional aprovado"},
            )
            assert close_response.status_code == 200
            assert close_response.json()["status"] == "closed"
            assert close_response.json()["closed_at"] is not None
            assert float(close_response.json()["total_expense_cost"]) == 350
            assert float(close_response.json()["total_transport_cost"]) == 350
            assert float(close_response.json()["actual_margin"]) == -350
            close_replay = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers={**headers, "Idempotency-Key": "trip-close:validated-pod:001"},
                json={"notes": "Fecho operacional aprovado"},
            )
            assert close_replay.status_code == 200
            assert close_replay.json()["closed_at"] == close_response.json()["closed_at"]

            billing_queue = await client.get("/api/v1/billing/billable-trips", headers=headers)
            assert billing_queue.status_code == 200
            assert trip["id"] in {item["trip_id"] for item in billing_queue.json()}

        async with AsyncSessionLocal() as db:
            trip_row = await db.get(Trip, trip["id"])
            assert trip_row is not None
            assert trip_row.status == "closed"
            audit_count = await db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action == "trip.closed",
                )
            )
            event_count = await db.scalar(
                select(func.count(TripExecutionEvent.id)).where(
                    TripExecutionEvent.tenant_id == tenant_id,
                    TripExecutionEvent.event_type == "completed",
                )
            )
            assert audit_count == 1
            assert event_count == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_operational_close_blocks_open_high_incident_and_allows_no_pod_waiver() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_trip(client, headers, vehicle_id, driver_id)

            start_response = await client.post(
                f"/api/v1/trips/{trip['id']}/start",
                headers=headers,
                json={"km_start": 1000},
            )
            assert start_response.status_code == 200

            complete_response = await client.post(
                f"/api/v1/trips/{trip['id']}/complete",
                headers=headers,
                json={"km_end": 1800, "recipient_name": "Cliente Individual"},
            )
            assert complete_response.status_code == 200
            incident_response = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents",
                headers={**headers, "Idempotency-Key": "trip-incident:client-delay:001"},
                json={
                    "incident_type": "client_delay",
                    "severity": "high",
                    "description": "Cliente reteve a descarga para conferencia.",
                },
            )
            assert incident_response.status_code == 200
            incident = incident_response.json()
            incident_replay = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents",
                headers={**headers, "Idempotency-Key": "trip-incident:client-delay:001"},
                json={
                    "incident_type": "client_delay",
                    "severity": "high",
                    "description": "Cliente reteve a descarga para conferencia.",
                },
            )
            assert incident_replay.status_code == 200
            assert incident_replay.json()["id"] == incident["id"]

            close_with_incident = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Ainda ha incidente aberto"},
            )
            assert close_with_incident.status_code == 409
            assert close_with_incident.json()["error"]["code"] == "open_blocking_incident"

            resolve_response = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents/{incident['id']}/resolve",
                headers=headers,
                json={"resolution_notes": "Cliente autorizou fecho sem documento formal."},
            )
            assert resolve_response.status_code == 200

            waiver_response = await client.post(
                "/api/v1/operations/waivers",
                headers=headers,
                json={
                    "entity_type": "trip",
                    "entity_id": trip["id"],
                    "waiver_type": "no_pod",
                    "reason": "Cliente individual sem documento formal.",
                    "risk_level": "medium",
                },
            )
            assert waiver_response.status_code == 200
            assert waiver_response.json()["status"] == "active"

            close_response = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Fecho com waiver no_pod"},
            )
            assert close_response.status_code == 200
            assert close_response.json()["status"] == "closed"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
