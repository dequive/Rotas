import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.tokens import create_access_token
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.tenants.models import Tenant
from app.modules.trips.models import (
    DispatchClearance,
    Trip,
    TripCost,
    TripExecutionEvent,
    TripIncident,
)
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import MaintenanceRequest

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Dispatch {suffix}", slug=f"dispatch-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"DSP-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Dispatch {suffix}",
            phone=f"25886{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant.id, vehicle.id, driver.id


async def create_assigned_trip(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    vehicle_id,
    driver_id,
):
    order_response = await client.post(
        "/api/v1/trip-orders",
        headers=headers,
        json={
            "origin": "Maputo",
            "destination": "Quelimane",
            "cargo_type": "Carga contratual",
            "requested_pickup_date": "2026-06-20",
            "requires_load_permit": True,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()

    confirm_response = await client.post(
        f"/api/v1/trip-orders/{order['id']}/confirm",
        headers=headers,
        json={},
    )
    assert confirm_response.status_code == 200

    assign_response = await client.post(
        f"/api/v1/trip-orders/{order['id']}/assign",
        headers=headers,
        json={"vehicle_id": str(vehicle_id), "driver_id": str(driver_id)},
    )
    assert assign_response.status_code == 200
    return assign_response.json()["trip"]


@pytest.mark.asyncio
async def test_dispatch_requires_approved_clearance_and_load_permit() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            blocked_dispatch = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch",
                headers=headers,
                json={},
            )
            assert blocked_dispatch.status_code == 409
            assert blocked_dispatch.json()["error"]["code"] == "dispatch_clearance_required"

            request_response = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=headers,
            )
            assert request_response.status_code == 200
            assert request_response.json()["clearance_status"] == "pending"

            blocked_clearance = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert blocked_clearance.status_code == 200
            assert blocked_clearance.json()["clearance_status"] == "blocked"

            permit_response = await client.post(
                f"/api/v1/trips/{trip['id']}/load-permits",
                headers=headers,
                json={
                    "client_name": "Cliente Dispatch",
                    "permit_number": "LP-DSP-001",
                    "issuer_name": "Cliente Dispatch",
                    "district": "Quelimane",
                },
            )
            assert permit_response.status_code == 200

            approved_clearance = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert approved_clearance.status_code == 200
            assert approved_clearance.json()["clearance_status"] == "approved"

            awaiting_dispatch = await client.get("/api/v1/control-tower", headers=headers)
            assert awaiting_dispatch.status_code == 200
            assert trip["id"] in {
                item["trip_id"] for item in awaiting_dispatch.json()["queues"]["pending_dispatch"]
            }

            dispatch_response = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch",
                headers=headers,
                json={"notes": "Despacho autorizado"},
            )
            assert dispatch_response.status_code == 200
            assert dispatch_response.json()["trip"]["status"] == "dispatched"
            assert dispatch_response.json()["event"]["event_type"] == "dispatched"

            dispatched_tower = await client.get("/api/v1/control-tower", headers=headers)
            assert dispatched_tower.status_code == 200
            assert trip["id"] not in {
                item["trip_id"] for item in dispatched_tower.json()["queues"]["pending_dispatch"]
            }

        async with AsyncSessionLocal() as db:
            clearance_count = await db.scalar(
                select(func.count(DispatchClearance.id)).where(
                    DispatchClearance.tenant_id == tenant_id
                )
            )
            event_count = await db.scalar(
                select(func.count(TripExecutionEvent.id)).where(
                    TripExecutionEvent.tenant_id == tenant_id,
                    TripExecutionEvent.event_type == "dispatched",
                )
            )
            assert clearance_count == 1
            assert event_count == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_start_rejects_a_planned_trip_that_bypassed_dispatch_clearance() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            response = await client.post(
                f"/api/v1/trips/{trip['id']}/start",
                headers=headers,
                json={"km_start": 1200},
            )

            assert response.status_code == 409
            assert response.json()["error"]["code"] == "dispatch_required"

        async with AsyncSessionLocal() as db:
            trip_row = await db.get(Trip, trip["id"])
            assert trip_row is not None
            assert trip_row.status == "planned"
            assert trip_row.km_start is None
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_dispatch_clearance_is_tenant_scoped_and_requires_dispatch_permission() -> None:
    try:
        tenant_a, vehicle_id, driver_id = await create_seed_entities()
        tenant_b, _, _ = await create_seed_entities()
        async with await create_api_client() as client:
            headers_a = auth_headers(tenant_a)
            trip = await create_assigned_trip(client, headers_a, vehicle_id, driver_id)

            cross_tenant = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=auth_headers(tenant_b),
            )
            assert cross_tenant.status_code == 404
            assert cross_tenant.json()["error"]["code"] == "trip_not_found"

            async with AsyncSessionLocal() as db:
                viewer = User(
                    tenant_id=tenant_a,
                    email=f"viewer-{uuid4().hex[:8]}@dispatch.test",
                    password_hash="$argon2id$test",
                    full_name="Viewer Dispatch",
                    role="viewer",
                    is_active=True,
                )
                db.add(viewer)
                await db.commit()
                await db.refresh(viewer)

            viewer_token, _ = create_access_token(
                tenant_id=tenant_a,
                user_id=viewer.id,
                scope="dashboard",
                role="viewer",
                permissions=frozenset({"trips.read"}),
            )
            forbidden = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers={
                    "Authorization": f"Bearer {viewer_token}",
                    "X-Tenant-Id": str(tenant_a),
                },
            )
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "forbidden"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_dispatch_approval_rejects_idempotency_key_payload_reuse() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)
            requested = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=headers,
            )
            assert requested.status_code == 200

            idempotency_headers = {**headers, "Idempotency-Key": f"approve:{trip['id']}"}
            first = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=idempotency_headers,
                json={"vehicle_checked": False},
            )
            assert first.status_code == 200
            assert first.json()["clearance_status"] == "blocked"

            reused = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=idempotency_headers,
                json={"vehicle_checked": True},
            )
            assert reused.status_code == 409
            assert reused.json()["error"]["code"] == "idempotency_key_reused"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_concurrent_dispatch_creates_single_dispatch_event() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as setup_client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(setup_client, headers, vehicle_id, driver_id)

            permit_response = await setup_client.post(
                f"/api/v1/trips/{trip['id']}/load-permits",
                headers=headers,
                json={
                    "client_name": "Cliente Dispatch",
                    "permit_number": "LP-CONCURRENT-001",
                    "issuer_name": "Cliente Dispatch",
                    "district": "Quelimane",
                },
            )
            assert permit_response.status_code == 200

            request_response = await setup_client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=headers,
            )
            assert request_response.status_code == 200

            approved_clearance = await setup_client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert approved_clearance.status_code == 200
            assert approved_clearance.json()["clearance_status"] == "approved"

        async def dispatch() -> httpx.Response:
            async with await create_api_client() as client:
                return await client.post(
                    f"/api/v1/trips/{trip['id']}/dispatch",
                    headers=headers,
                    json={"notes": "Despacho concorrente"},
                )

        responses = await asyncio.gather(dispatch(), dispatch())
        statuses = sorted(response.status_code for response in responses)
        assert statuses == [200, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()["error"]["code"] == "invalid_trip_status"

        async with AsyncSessionLocal() as db:
            trip_row = await db.get(Trip, trip["id"])
            assert trip_row is not None
            assert trip_row.status == "dispatched"
            dispatched_events = await db.scalar(
                select(func.count(TripExecutionEvent.id)).where(
                    TripExecutionEvent.tenant_id == tenant_id,
                    TripExecutionEvent.trip_id == trip["id"],
                    TripExecutionEvent.event_type == "dispatched",
                )
            )
            assert dispatched_events == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_delivery_sla_evaluation_marks_delayed_trip_and_exposes_tower_queue() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)
            planned_arrival = datetime.now(UTC) - timedelta(hours=3)

            async with AsyncSessionLocal() as db:
                trip_row = await db.get(Trip, trip["id"])
                assert trip_row is not None
                trip_row.status = "in_progress"
                trip_row.actual_departure = datetime.now(UTC) - timedelta(hours=8)
                trip_row.planned_arrival = planned_arrival
                await db.commit()

            first_evaluation = await client.post("/api/v1/trips/sla/evaluate", headers=headers)
            assert first_evaluation.status_code == 200
            delayed = first_evaluation.json()
            assert len(delayed) == 1
            assert delayed[0]["id"] == trip["id"]
            assert delayed[0]["status"] == "delayed"

            replay = await client.post("/api/v1/trips/sla/evaluate", headers=headers)
            assert replay.status_code == 200
            assert replay.json()[0]["status"] == "delayed"

            tower = await client.get("/api/v1/control-tower", headers=headers)
            assert tower.status_code == 200
            delayed_queue = tower.json()["queues"]["delayed_trips"]
            assert delayed_queue[0]["trip_id"] == trip["id"]
            assert delayed_queue[0]["delay_minutes"] >= 180

        async with AsyncSessionLocal() as db:
            delayed_event_count = await db.scalar(
                select(func.count(TripExecutionEvent.id)).where(
                    TripExecutionEvent.tenant_id == tenant_id,
                    TripExecutionEvent.trip_id == trip["id"],
                    TripExecutionEvent.event_type == "delayed",
                )
            )
            exception_count = await db.scalar(
                select(func.count(OperationalException.id)).where(
                    OperationalException.tenant_id == tenant_id,
                    OperationalException.entity_id == trip["id"],
                    OperationalException.exception_type == "trip_delivery_sla_breached",
                    OperationalException.status.in_(("open", "acknowledged")),
                )
            )
            assert delayed_event_count == 1
            assert exception_count == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_dispatch_clearance_enforces_cargo_document_policy_by_cargo_type() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, tenant_id)
            assert tenant is not None
            tenant.compliance_policy = {
                "cargo_required_documents_by_type": {
                    "Carga contratual": [
                        "load_permit",
                        "cargo_manifest",
                        "transport_document:client_waybill",
                    ],
                },
            }
            await db.commit()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            request_response = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=headers,
            )
            assert request_response.status_code == 200

            blocked_clearance = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert blocked_clearance.status_code == 200
            blocked_payload = blocked_clearance.json()
            assert blocked_payload["clearance_status"] == "blocked"
            assert "missing_document:cargo_manifest" in blocked_payload["blocked_reason"]
            assert (
                "missing_document:transport_document:client_waybill"
                in blocked_payload["blocked_reason"]
            )

            permit_response = await client.post(
                f"/api/v1/trips/{trip['id']}/load-permits",
                headers=headers,
                json={
                    "client_name": "Cliente Dispatch",
                    "permit_number": "LP-DOC-001",
                    "issuer_name": "Cliente Dispatch",
                    "district": "Quelimane",
                },
            )
            assert permit_response.status_code == 200

            still_blocked = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert still_blocked.status_code == 200
            assert still_blocked.json()["clearance_status"] == "blocked"
            assert "missing_document:load_permit" not in still_blocked.json()["blocked_reason"]

            manifest_response = await client.post(
                f"/api/v1/trips/{trip['id']}/cargo-manifest",
                headers=headers,
                json={
                    "manifest_number": "MAN-DOC-001",
                    "client_name": "Cliente Dispatch",
                    "cargo_description": "Carga contratual",
                    "cargo_type": "Carga contratual",
                    "origin": "Maputo",
                    "destination": "Quelimane",
                },
            )
            assert manifest_response.status_code == 200

            document_response = await client.post(
                f"/api/v1/trips/{trip['id']}/transport-documents",
                headers=headers,
                json={
                    "document_type": "client_waybill",
                    "document_number": "WB-DOC-001",
                    "client_name": "Cliente Dispatch",
                    "origin": "Maputo",
                    "destination": "Quelimane",
                },
            )
            assert document_response.status_code == 200

            approved_clearance = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/approve",
                headers=headers,
                json={
                    "vehicle_checked": True,
                    "driver_checked": True,
                    "documents_checked": True,
                    "load_permit_checked": True,
                    "cargo_checked": True,
                    "fuel_advance_checked": True,
                    "route_risk_checked": True,
                },
            )
            assert approved_clearance.status_code == 200
            assert approved_clearance.json()["clearance_status"] == "approved"
            assert approved_clearance.json()["blocked_reason"] is None
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_operational_close_requires_policy_mandatory_stops_by_cargo_type() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, tenant_id)
            assert tenant is not None
            tenant.compliance_policy = {
                "trip_required_stops_by_cargo_type": {
                    "Carga contratual": ["weighbridge", "client_checkpoint"],
                },
            }
            await db.commit()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            async with AsyncSessionLocal() as db:
                trip_row = await db.get(Trip, trip["id"])
                assert trip_row is not None
                trip_row.status = "arrived"
                trip_row.actual_arrival = datetime.now(UTC)
                await db.commit()

            proof_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof",
                headers=headers,
                json={
                    "document_number": "POD-STOPS-001",
                    "proof_type": "client_discharge_note",
                    "client_type": "company",
                    "delivered_at": "2026-07-02T10:30:00+00:00",
                    "quantity_delivered": 12,
                },
            )
            assert proof_response.status_code == 200
            proof = proof_response.json()

            validation_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/validate",
                headers=headers,
                json={"validation_method": "manual_review", "notes": "Validado."},
            )
            assert validation_response.status_code == 200

            blocked_close = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Tentativa antes das paragens obrigatorias."},
            )
            assert blocked_close.status_code == 409
            assert blocked_close.json()["error"]["code"] == "required_trip_stops_missing"
            assert blocked_close.json()["error"]["details"]["missing_stops"] == [
                "client_checkpoint",
                "weighbridge",
            ]

            weighbridge_stop = await client.post(
                f"/api/v1/trips/{trip['id']}/stops",
                headers=headers,
                json={
                    "stop_type": "weighbridge",
                    "address": "Ponte bascula EN1",
                    "notes": "Peso confirmado.",
                },
            )
            assert weighbridge_stop.status_code == 200

            still_blocked = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Ainda falta checkpoint."},
            )
            assert still_blocked.status_code == 409
            assert still_blocked.json()["error"]["details"]["missing_stops"] == [
                "client_checkpoint"
            ]

            checkpoint_stop = await client.post(
                f"/api/v1/trips/{trip['id']}/stops",
                headers=headers,
                json={
                    "stop_type": "client_checkpoint",
                    "address": "Portao cliente",
                    "notes": "Entrada autorizada pelo cliente.",
                },
            )
            assert checkpoint_stop.status_code == 200

            closed = await client.post(
                f"/api/v1/trips/{trip['id']}/close",
                headers=headers,
                json={"notes": "Paragens obrigatorias cumpridas."},
            )
            assert closed.status_code == 200
            assert closed.json()["status"] == "closed"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_driver_despacho_records_distance_based_travel_allowance_cost() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with AsyncSessionLocal() as db:
            tenant = await db.get(Tenant, tenant_id)
            assert tenant is not None
            tenant.compliance_policy = {
                "driver_travel_allowance_policy": {
                    "table_name": "Tabela de despacho Zambezia 2026",
                    "table_reference": "TD-ZAM-2026",
                    "currency": "MZN",
                    "effective_from": "2026-01-01",
                    "min_long_course_km": 100,
                    "tiers": [
                        {
                            "min_km": 100,
                            "max_km": 300,
                            "amount": 750,
                            "label": "Curto longo curso",
                        },
                        {
                            "min_km": 300,
                            "amount": 1250,
                            "label": "Longo curso nacional",
                            "code": "LC-NAC",
                        },
                    ],
                }
            }
            await db.commit()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            allowance = await client.post(
                f"/api/v1/trips/{trip['id']}/driver-despacho",
                headers={**headers, "Idempotency-Key": "driver-despacho:long:001"},
                json={
                    "distance_km": 320,
                    "request_reference": "driver-despacho:long:001",
                    "notes": "Despacho de longo curso Maputo-Quelimane.",
                },
            )
            assert allowance.status_code == 200
            payload = allowance.json()
            assert payload["cost_type"] == "driver_despacho"
            assert float(payload["amount"]) == 1250
            assert payload["distance_km"] == 320
            assert payload["despacho_table"] == {
                "name": "Tabela de despacho Zambezia 2026",
                "reference": "TD-ZAM-2026",
                "effective_from": "2026-01-01",
                "currency": "MZN",
                "source": "tenant_policy",
                "entry_mode": None,
            }
            assert payload["despacho_tier"]["code"] == "LC-NAC"
            assert payload["despacho_tier"]["label"] == "Longo curso nacional"

            replay = await client.post(
                f"/api/v1/trips/{trip['id']}/driver-despacho",
                headers={**headers, "Idempotency-Key": "driver-despacho:long:001"},
                json={
                    "distance_km": 320,
                    "request_reference": "driver-despacho:long:001",
                    "notes": "Despacho de longo curso Maputo-Quelimane.",
                },
            )
            assert replay.status_code == 200
            assert replay.json()["id"] == payload["id"]

            short_allowance = await client.post(
                f"/api/v1/trips/{trip['id']}/driver-despacho",
                headers={**headers, "Idempotency-Key": "driver-despacho:short:001"},
                json={
                    "distance_km": 50,
                    "request_reference": "driver-despacho:short:001",
                },
            )
            assert short_allowance.status_code == 409
            assert short_allowance.json()["error"]["code"] == "driver_allowance_not_applicable"

        async with AsyncSessionLocal() as db:
            cost_count = await db.scalar(
                select(func.count(TripCost.id)).where(
                    TripCost.tenant_id == tenant_id,
                    TripCost.trip_id == trip["id"],
                    TripCost.cost_type == "driver_despacho",
                )
            )
            trip_row = await db.get(Trip, trip["id"])
            assert trip_row is not None
            assert cost_count == 1
            assert float(trip_row.total_expense_cost) == 1250
            assert float(trip_row.total_transport_cost) == 1250
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_incident_reports_event_and_audit() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()
        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip = await create_assigned_trip(client, headers, vehicle_id, driver_id)

            incident_response = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents",
                headers=headers,
                json={
                    "incident_type": "breakdown",
                    "severity": "high",
                    "description": "Motor perdeu potencia durante a subida.",
                    "delay_minutes": 120,
                },
            )
            assert incident_response.status_code == 200
            incident = incident_response.json()
            assert incident["status"] == "open"
            assert incident["incident_type"] == "breakdown"

            resolve_response = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents/{incident['id']}/resolve",
                headers=headers,
                json={"resolution_notes": "Viatura rebocada e reparacao temporaria concluida."},
            )
            assert resolve_response.status_code == 200
            assert resolve_response.json()["status"] == "resolved"

            maintenance_requests = await client.get(
                "/api/v1/workshop/maintenance-requests",
                headers=headers,
                params={"vehicle_id": str(vehicle_id)},
            )
            assert maintenance_requests.status_code == 200
            maintenance_request = maintenance_requests.json()[0]
            assert maintenance_request["incident_id"] == incident["id"]

            work_order = await client.post(
                "/api/v1/workshop/work-orders",
                headers=headers,
                json={
                    "maintenance_request_id": maintenance_request["id"],
                    "vehicle_id": str(vehicle_id),
                    "planned_work": "Reparar falha mecânica reportada em viagem.",
                },
            )
            assert work_order.status_code == 200
            for action in ("approve", "start", "quality-check"):
                transition = await client.post(
                    f"/api/v1/workshop/work-orders/{work_order.json()['id']}/{action}",
                    headers=headers,
                    json={},
                )
                assert transition.status_code == 200
            closed_work_order = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/close",
                headers=headers,
                json={"actual_cost": 27500, "notes": "Reparação concluída e testada."},
            )
            assert closed_work_order.status_code == 200

        async with AsyncSessionLocal() as db:
            incident_count = await db.scalar(
                select(func.count(TripIncident.id)).where(TripIncident.tenant_id == tenant_id)
            )
            event_count = await db.scalar(
                select(func.count(TripExecutionEvent.id)).where(
                    TripExecutionEvent.tenant_id == tenant_id,
                    TripExecutionEvent.event_type == "incident_reported",
                )
            )
            audit_count = await db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action.in_(("trip.incident_reported", "trip.incident_resolved")),
                )
            )
            maintenance_request = await db.scalar(
                select(MaintenanceRequest).where(
                    MaintenanceRequest.tenant_id == tenant_id,
                    MaintenanceRequest.incident_id == incident["id"],
                )
            )
            workshop_cost = await db.scalar(
                select(TripCost).where(
                    TripCost.tenant_id == tenant_id,
                    TripCost.trip_id == trip["id"],
                    TripCost.source_type == "work_order",
                )
            )
            assert incident_count == 1
            assert event_count == 1
            assert audit_count == 2
            assert maintenance_request is not None
            assert maintenance_request.request_type == "breakdown"
            assert maintenance_request.priority == "high"
            assert workshop_cost is not None
            assert float(workshop_cost.amount) == 27500
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
