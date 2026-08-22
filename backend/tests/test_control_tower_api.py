from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.cargo.models import DeliveryProof
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.tenants.models import Tenant
from app.modules.trips.models import DispatchClearance, Trip
from app.modules.vehicles.models import Vehicle

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
        tenant = Tenant(name=f"Tenant Tower {suffix}", slug=f"tower-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"TWR-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Tower {suffix}",
            phone=f"25888{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant.id, vehicle.id, driver.id


@pytest.mark.asyncio
async def test_control_tower_exposes_operational_queues_and_counts() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            trip_response = await client.post(
                "/api/v1/trips",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle_id),
                    "driver_id": str(driver_id),
                    "origin": "Tete",
                    "destination": "Beira",
                    "cargo_type": "Carga geral",
                    "requires_load_permit": True,
                },
            )
            assert trip_response.status_code == 200
            trip = trip_response.json()

            clearance_request = await client.post(
                f"/api/v1/trips/{trip['id']}/dispatch-clearance/request",
                headers=headers,
            )
            assert clearance_request.status_code == 200

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

            incident_response = await client.post(
                f"/api/v1/trips/{trip['id']}/incidents",
                headers=headers,
                json={
                    "incident_type": "document_issue",
                    "severity": "medium",
                    "description": "Load Permit ainda nao entregue pelo cliente.",
                },
            )
            assert incident_response.status_code == 200

            proof_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof",
                headers=headers,
                json={
                    "document_number": "POD-TOWER-001",
                    "proof_type": "client_discharge_note",
                    "client_type": "company",
                    "delivered_at": "2026-06-25T09:30:00+00:00",
                    "quantity_delivered": 1,
                },
            )
            assert proof_response.status_code == 200

            waiver_response = await client.post(
                "/api/v1/operations/waivers",
                headers=headers,
                json={
                    "entity_type": "trip",
                    "entity_id": trip["id"],
                    "waiver_type": "missing_document",
                    "reason": "Cliente prometeu enviar Load Permit no fecho do dia.",
                    "risk_level": "medium",
                },
            )
            assert waiver_response.status_code == 200

            async with AsyncSessionLocal() as db:
                tenant_row = await db.get(Tenant, tenant_id)
                assert tenant_row is not None
                tenant_row.compliance_policy = {
                    "vehicle_required_documents": ["insurance"],
                    "driver_required_documents": ["driving_license"],
                    "document_expiry_warning_days": 30,
                }
                vehicle_row = await db.get(Vehicle, vehicle_id)
                assert vehicle_row is not None
                vehicle_row.documents = {
                    "insurance_valid_until": (
                        datetime.now(UTC).date() + timedelta(days=10)
                    ).isoformat()
                }
                driver_row = await db.get(Driver, driver_id)
                assert driver_row is not None
                driver_row.license_valid_until = datetime.now(UTC).date() + timedelta(days=15)
                await ensure_exception(
                    db,
                    tenant_id,
                    entity_type="trip",
                    entity_id=trip["id"],
                    exception_type="missing_load_permit",
                    severity="high",
                    title="Load Permit pendente",
                    message="Documento obrigatório ainda não recebido.",
                    source_type="dispatch_clearance",
                )
                trip_row = await db.get(Trip, trip["id"])
                assert trip_row is not None
                trip_row.status = "closed"
                trip_row.total_transport_cost = Decimal("12000")
                trip_row.actual_revenue = Decimal("9000")
                trip_row.actual_margin = Decimal("-3000")
                trip_row.costs_reconciled_at = datetime.now(UTC)
                close_candidate = Trip(
                    tenant_id=tenant_id,
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    origin="Maputo",
                    destination="Xai-Xai",
                    cargo_type="Carga geral",
                    status="delivered",
                    billing_status="billable",
                    actual_arrival=datetime.now(UTC),
                )
                db.add(close_candidate)
                await db.flush()
                close_candidate_id = close_candidate.id
                despacho_candidate = Trip(
                    tenant_id=tenant_id,
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    origin="Maputo",
                    destination="Quelimane",
                    cargo_type="Carga geral",
                    status="closed",
                    km_start=12000,
                    km_end=12680,
                )
                db.add(despacho_candidate)
                await db.flush()
                despacho_candidate_id = despacho_candidate.id
                pending_dispatch_trip = Trip(
                    tenant_id=tenant_id,
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    origin="Nampula",
                    destination="Nacala",
                    cargo_type="Carga geral",
                    status="dispatch_pending",
                )
                db.add(pending_dispatch_trip)
                await db.flush()
                pending_dispatch_trip_id = pending_dispatch_trip.id
                pending_clearance = DispatchClearance(
                    tenant_id=tenant_id,
                    trip_id=pending_dispatch_trip_id,
                    vehicle_checked=True,
                    driver_checked=True,
                    documents_checked=True,
                    clearance_status="pending",
                )
                validated_close_proof = DeliveryProof(
                    tenant_id=tenant_id,
                    trip_id=close_candidate_id,
                    document_number="POD-CLOSE-TOWER-001",
                    delivered_at=datetime(2026, 6, 25, 11, 30, tzinfo=UTC),
                    status="validated",
                )
                template = ChecklistTemplate(
                    tenant_id=tenant_id,
                    name="Pre-partida",
                    type="pre_partida",
                    items=[],
                )
                db.add(template)
                await db.flush()
                failed_checklist = Checklist(
                    tenant_id=tenant_id,
                    vehicle_id=vehicle_id,
                    driver_id=driver_id,
                    template_id=template.id,
                    type="pre_partida",
                    status="failed",
                    responses={},
                    completed_at=datetime.now(UTC),
                )
                disputed_proof = DeliveryProof(
                    tenant_id=tenant_id,
                    trip_id=trip["id"],
                    document_number="POD-DISPUTED-TOWER-001",
                    delivered_at=datetime(2026, 6, 25, 10, 30, tzinfo=UTC),
                    status="disputed",
                )
                db.add_all(
                    [pending_clearance, validated_close_proof, failed_checklist, disputed_proof]
                )
                await db.commit()

            clearances = await client.get(
                "/api/v1/trips/dispatch-clearances",
                headers=headers,
                params={"status": "blocked"},
            )
            assert clearances.status_code == 200
            assert len(clearances.json()) == 1

            incidents = await client.get(
                "/api/v1/trips/incidents",
                headers=headers,
                params={"status": "open"},
            )
            assert incidents.status_code == 200
            assert len(incidents.json()) == 1

            events = await client.get(
                "/api/v1/trips/events",
                headers=headers,
                params={"event_type": "incident_reported"},
            )
            assert events.status_code == 200
            assert len(events.json()) == 1

            tower_response = await client.get("/api/v1/control-tower", headers=headers)
            assert tower_response.status_code == 200
            tower = tower_response.json()
            assert tower["summary"]["dispatch_blocked"] == 1
            assert tower["summary"]["incidents_open"] == 1
            assert tower["summary"]["delivery_proofs_pending_validation"] == 1
            assert tower["summary"]["active_waivers"] == 1
            assert tower["summary"]["operational_exceptions_open"] == 1
            assert tower["summary"]["alerts_active"] == 1
            assert tower["summary"]["costs_reconciled_trips"] == 1
            assert tower["summary"]["transport_cost_total"] == 12000
            assert tower["summary"]["contract_revenue_total"] == 9000
            assert tower["summary"]["margin_total"] == -3000
            assert tower["summary"]["negative_margin_trips"] == 1
            assert tower["summary"]["vehicle_documents_expiring"] == 1
            assert tower["summary"]["driver_documents_expiring"] == 1
            assert tower["queues"]["blocked_dispatch"][0]["trip_id"] == trip["id"]
            assert tower["queues"]["pending_dispatch"][0]["trip_id"] == str(
                pending_dispatch_trip_id
            )
            assert tower["queues"]["open_incidents"][0]["trip_id"] == trip["id"]
            assert tower["queues"]["pending_delivery_validation"][0]["trip_id"] == trip["id"]
            assert tower["queues"]["operational_exceptions"][0]["entity_id"] == trip["id"]
            assert tower["queues"]["alerts"][0]["entity_id"] == trip["id"]
            assert tower["queues"]["negative_margin_trips"][0]["trip_id"] == trip["id"]
            assert tower["queues"]["negative_margin_trips"][0]["margin"] == -3000
            assert tower["queues"]["driver_despacho_pending"][0]["trip_id"] == str(
                despacho_candidate_id
            )
            assert tower["queues"]["driver_despacho_pending"][0]["distance_km"] == 680
            assert tower["queues"]["failed_checklists"][0]["vehicle_id"] == str(vehicle_id)
            assert tower["queues"]["disputed_delivery_proofs"][0]["trip_id"] == trip["id"]
            assert tower["queues"]["operational_close_candidates"][0]["trip_id"] == str(
                close_candidate_id
            )
            assert tower["queues"]["operational_close_candidates"][0]["readiness"] == "ready"
            assert tower["queues"]["vehicle_documents_expiring"][0]["document_type"] == (
                "insurance"
            )
            assert tower["queues"]["driver_documents_expiring"][0]["document_type"] == (
                "driving_license"
            )
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
