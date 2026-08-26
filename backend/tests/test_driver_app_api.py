import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.tokens import create_access_token
from app.modules.cargo.models import CargoManifest, DeliveryProof, LoadPermit, TransportDocument
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver, DriverAdvance, DriverDevice
from app.modules.files import service as files_service
from app.modules.fuel.models import FuelLog
from app.modules.operational_exceptions.models import OperationalException
from app.modules.sync.models import IdempotencyKey, SyncEvent
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip, TripCost, TripStop
from app.modules.vehicles.models import Vehicle


@pytest.fixture
async def driver_app_context(db, tenant_id):
    suffix = uuid4().hex[:8]
    device_id = f"driver-device-{suffix}"
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Driver App Test",
        phone="840000000",
        status="active",
    )
    other_driver = Driver(
        tenant_id=tenant_id,
        full_name="Other Driver",
        phone="840000001",
        status="active",
    )
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"DRV-{suffix[:4]}",
        brand="Toyota",
        model="Dyna",
        status="active",
        current_km=1200,
    )
    template = ChecklistTemplate(
        tenant_id=tenant_id,
        name="Pre partida padrao",
        type="pre_partida",
        is_active=True,
        items=[
            {
                "id": "oil",
                "label": "Nivel de oleo",
                "type": "boolean",
                "is_blocking": True,
            }
        ],
    )
    db.add_all([driver, other_driver, vehicle, template])
    await db.flush()

    device = DriverDevice(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        device_name="ROTAS App",
        is_active=True,
    )
    db.add(device)
    await db.commit()

    token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        scope="driver_app",
    )

    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(tenant_id),
        },
        "driver": driver,
        "other_driver": other_driver,
        "vehicle": vehicle,
        "template": template,
        "device_id": device_id,
    }


@pytest.mark.asyncio
async def test_driver_bootstrap_uses_driver_contract(async_client, driver_app_context):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["profile"]["driver_id"] == str(driver_app_context["driver"].id)
    assert data["activeTrip"] is None
    assert [template["name"] for template in data["checklistTemplates"]] == [
        driver_app_context["template"].name
    ]
    assert data["vehicles"] == []


@pytest.mark.asyncio
async def test_driver_trip_contract_omits_manager_financial_fields(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Beira",
        status="planned",
        billing_status="pending_delivery_proof",
        total_fuel_cost=1000,
        total_expense_cost=2000,
        total_transport_cost=3000,
        actual_revenue=5000,
        actual_margin=2000,
    )
    db.add(assigned_trip)
    await db.commit()

    responses = [
        await async_client.get(
            "/api/v1/driver/active-trip",
            headers=driver_app_context["headers"],
        ),
        await async_client.get(
            "/api/v1/driver/bootstrap",
            headers=driver_app_context["headers"],
        ),
    ]
    forbidden_fields = {
        "tenant_id",
        "contract_id",
        "billing_status",
        "billing_document_id",
        "total_fuel_cost",
        "total_expense_cost",
        "total_transport_cost",
        "actual_revenue",
        "actual_margin",
        "costs_reconciled_at",
    }
    active_trip = responses[0].json()
    bootstrap_trip = responses[1].json()["activeTrip"]

    assert all(response.status_code == 200 for response in responses)
    assert active_trip["id"] == str(assigned_trip.id)
    assert bootstrap_trip == active_trip
    assert forbidden_fields.isdisjoint(active_trip)


@pytest.mark.asyncio
async def test_driver_lists_only_own_assigned_non_draft_trips(
    async_client, db, tenant_id, driver_app_context
):
    own_assigned = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Beira",
        status="planned",
        actual_revenue=9000,
    )
    own_delivered = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Beira",
        destination="Nampula",
        status="delivered",
    )
    own_draft = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Rascunho",
        destination="Oculto",
        status="draft",
    )
    own_closed = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Concluida",
        destination="Historico",
        status="closed",
    )
    foreign_assigned = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Outro",
        destination="Motorista",
        status="delivered",
    )
    db.add_all(
        [own_assigned, own_delivered, own_draft, own_closed, foreign_assigned]
    )
    await db.commit()

    first_page = await async_client.get(
        "/api/v1/driver/trips?limit=1&offset=0",
        headers=driver_app_context["headers"],
    )
    second_page = await async_client.get(
        "/api/v1/driver/trips?limit=1&offset=1",
        headers=driver_app_context["headers"],
    )

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert first_page.json()["total"] == 2
    assert second_page.json()["total"] == 2
    listed_ids = {
        first_page.json()["items"][0]["id"],
        second_page.json()["items"][0]["id"],
    }
    assert listed_ids == {str(own_assigned.id), str(own_delivered.id)}
    assert first_page.json()["limit"] == 1
    assert second_page.json()["offset"] == 1
    assert "actual_revenue" not in first_page.json()["items"][0]


@pytest.mark.asyncio
async def test_driver_history_only_contains_own_closed_or_cancelled_trips(
    async_client, db, tenant_id, driver_app_context
):
    own_closed = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
    )
    own_cancelled = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Xai-Xai",
        status="cancelled",
    )
    own_draft = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Rascunho",
        destination="Oculto",
        status="draft",
    )
    foreign_closed = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Outro",
        destination="Motorista",
        status="closed",
    )
    db.add_all([own_closed, own_cancelled, own_draft, foreign_closed])
    await db.commit()

    response = await async_client.get(
        "/api/v1/driver/trips/history?limit=20&offset=0",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {
        str(own_closed.id),
        str(own_cancelled.id),
    }
    assert {item["status"] for item in body["items"]} == {"closed", "cancelled"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/driver/trips",
        "/api/v1/driver/trips/history",
        "/api/v1/driver/records/checklists",
        "/api/v1/driver/records/fuel",
        "/api/v1/driver/records/expenses",
        "/api/v1/driver/records/advances",
    ],
)
async def test_dashboard_token_cannot_list_driver_resources(
    async_client, viewer_headers, path
):
    response = await async_client.get(path, headers=viewer_headers)

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_scope_required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/driver/trips",
        "/api/v1/driver/records/checklists",
        "/api/v1/driver/records/fuel",
        "/api/v1/driver/records/expenses",
        "/api/v1/driver/records/advances",
    ],
)
async def test_driver_lists_reject_unbounded_page_size(
    async_client, driver_app_context, path
):
    response = await async_client.get(
        f"{path}?limit=101",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/driver/records/checklists",
        "/api/v1/driver/records/fuel",
        "/api/v1/driver/records/expenses",
        "/api/v1/driver/records/advances",
    ],
)
async def test_driver_record_lists_reject_another_drivers_trip_filter(
    async_client, db, tenant_id, driver_app_context, path
):
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Outro",
        destination="Motorista",
        status="closed",
    )
    db.add(foreign_trip)
    await db.commit()

    response = await async_client.get(
        f"{path}?trip_id={foreign_trip.id}",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "driver_trip_not_found"


@pytest.mark.asyncio
async def test_driver_lists_only_own_checklist_records_with_public_contract(
    async_client, db, tenant_id, driver_app_context
):
    own_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
    )
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Boane",
        status="closed",
    )
    db.add_all([own_trip, foreign_trip])
    await db.flush()
    own_record = Checklist(
        tenant_id=tenant_id,
        trip_id=own_trip.id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        template_id=driver_app_context["template"].id,
        type="pre_partida",
        status="completed",
        responses={"oil": True},
        started_at=datetime(2026, 8, 20, 6, tzinfo=UTC),
        completed_at=datetime(2026, 8, 20, 6, 5, tzinfo=UTC),
    )
    foreign_record = Checklist(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        template_id=driver_app_context["template"].id,
        type="pre_partida",
        status="completed",
        responses={"oil": False},
    )
    db.add_all([own_record, foreign_record])
    await db.commit()

    response = await async_client.get(
        f"/api/v1/driver/records/checklists?trip_id={own_trip.id}&limit=1&offset=0",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "items": [
            {
                "id": str(own_record.id),
                "trip_id": str(own_trip.id),
                "vehicle_id": str(driver_app_context["vehicle"].id),
                "checklist_type": "pre_partida",
                "status": "completed",
                "started_at": "2026-08-20T06:00:00Z",
                "completed_at": "2026-08-20T06:05:00Z",
                "created_at": own_record.created_at.isoformat().replace("+00:00", "Z"),
            }
        ],
        "total": 1,
        "limit": 1,
        "offset": 0,
    }
    assert "tenant_id" not in body["items"][0]
    assert "driver_id" not in body["items"][0]
    assert "responses" not in body["items"][0]


@pytest.mark.asyncio
async def test_driver_lists_only_own_fuel_records_with_public_contract(
    async_client, db, tenant_id, driver_app_context
):
    own_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Xai-Xai",
        status="closed",
    )
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Namaacha",
        status="closed",
    )
    db.add_all([own_trip, foreign_trip])
    await db.flush()
    own_record = FuelLog(
        tenant_id=tenant_id,
        trip_id=own_trip.id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        fuel_date=datetime(2026, 8, 20, 7, tzinfo=UTC),
        station_name="Posto Maputo",
        fuel_type="gasoleo",
        liters=50,
        price_per_liter=90,
        total_cost=4500,
        km_at_refuel=1250,
        payment_reference="internal-reference",
        is_verified=True,
    )
    foreign_record = FuelLog(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        fuel_date=datetime(2026, 8, 20, 8, tzinfo=UTC),
        fuel_type="gasoleo",
        liters=40,
        total_cost=3600,
        km_at_refuel=1300,
    )
    db.add_all([own_record, foreign_record])
    await db.commit()

    response = await async_client.get(
        f"/api/v1/driver/records/fuel?trip_id={own_trip.id}&limit=1&offset=0",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["items"] == [
        {
            "id": str(own_record.id),
            "trip_id": str(own_trip.id),
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "fuel_date": "2026-08-20T07:00:00Z",
            "station_name": "Posto Maputo",
            "fuel_type": "gasoleo",
            "liters": "50.00",
            "total_cost": "4500.00",
            "km_at_refuel": 1250,
            "has_receipt": False,
            "is_verified": True,
            "is_flagged": False,
            "created_at": own_record.created_at.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert "price_per_liter" not in body["items"][0]
    assert "payment_reference" not in body["items"][0]
    assert "verified_by_user_id" not in body["items"][0]


@pytest.mark.asyncio
async def test_driver_record_history_keeps_unlinked_legacy_facts_visible(
    async_client, db, tenant_id, driver_app_context
):
    checklist = Checklist(
        tenant_id=tenant_id,
        trip_id=None,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        template_id=driver_app_context["template"].id,
        type="pre_partida",
        status="completed",
        responses={"oil": True},
    )
    fuel = FuelLog(
        tenant_id=tenant_id,
        trip_id=None,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        fuel_date=datetime(2026, 8, 18, 7, tzinfo=UTC),
        fuel_type="gasoleo",
        liters=20,
        total_cost=1800,
        km_at_refuel=1100,
    )
    db.add_all([checklist, fuel])
    await db.commit()

    checklist_response = await async_client.get(
        "/api/v1/driver/records/checklists",
        headers=driver_app_context["headers"],
    )
    fuel_response = await async_client.get(
        "/api/v1/driver/records/fuel",
        headers=driver_app_context["headers"],
    )

    assert checklist_response.status_code == 200, checklist_response.text
    assert fuel_response.status_code == 200, fuel_response.text
    assert checklist_response.json()["total"] == 1
    assert fuel_response.json()["total"] == 1
    assert checklist_response.json()["items"][0]["trip_id"] is None
    assert fuel_response.json()["items"][0]["trip_id"] is None


@pytest.mark.asyncio
async def test_driver_lists_only_own_driver_paid_expenses(
    async_client, db, tenant_id, driver_app_context
):
    own_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Chokwe",
        status="closed",
    )
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Marracuene",
        status="closed",
    )
    db.add_all([own_trip, foreign_trip])
    await db.flush()
    own_expense = TripCost(
        tenant_id=tenant_id,
        trip_id=own_trip.id,
        cost_type="toll",
        description="Portagem",
        amount=250,
        currency="MZN",
        paid_by="driver",
        payment_method="cash",
        request_reference=f"driver-expense:{uuid4()}",
        source_type="driver_app",
        source_id=driver_app_context["driver"].id,
        driver_id=driver_app_context["driver"].id,
        driver_visibility="visible",
        recorded_by_type="driver",
        incurred_at=datetime(2026, 8, 20, 9, tzinfo=UTC),
    )
    internal_cost = TripCost(
        tenant_id=tenant_id,
        trip_id=own_trip.id,
        cost_type="insurance",
        description="Custo interno",
        amount=1000,
        currency="MZN",
        paid_by="company",
        request_reference=f"internal:{uuid4()}",
        source_type="manual",
        driver_id=driver_app_context["driver"].id,
        driver_visibility="hidden",
        recorded_by_type="manager",
        incurred_at=datetime(2026, 8, 20, 8, tzinfo=UTC),
    )
    foreign_expense = TripCost(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        cost_type="toll",
        amount=300,
        currency="MZN",
        paid_by="driver",
        request_reference=f"driver-expense:{uuid4()}",
        source_type="driver_app",
        source_id=driver_app_context["other_driver"].id,
        driver_id=driver_app_context["other_driver"].id,
        driver_visibility="visible",
        recorded_by_type="driver",
        incurred_at=datetime(2026, 8, 20, 10, tzinfo=UTC),
    )
    db.add_all([own_expense, internal_cost, foreign_expense])
    await db.commit()

    response = await async_client.get(
        f"/api/v1/driver/records/expenses?trip_id={own_trip.id}&limit=20&offset=0",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"] == [
        {
            "id": str(own_expense.id),
            "trip_id": str(own_trip.id),
            "expense_type": "toll",
            "description": "Portagem",
            "amount": "250.00",
            "currency": "MZN",
            "payment_method": "cash",
            "has_receipt": False,
            "entry_type": "original",
            "corrects_id": None,
            "correction_reason": None,
            "recorded_by_type": "driver",
            "incurred_at": "2026-08-20T09:00:00Z",
            "created_at": own_expense.created_at.isoformat().replace("+00:00", "Z"),
        }
    ]
    assert "request_reference" not in body["items"][0]
    assert "source_type" not in body["items"][0]


@pytest.mark.asyncio
async def test_driver_lists_only_own_dispatch_advances_with_public_contract(
    async_client, db, tenant_id, driver_app_context
):
    own_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Inhambane",
        status="closed",
    )
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Bilene",
        status="closed",
    )
    db.add_all([own_trip, foreign_trip])
    await db.flush()
    own_advance = DriverAdvance(
        tenant_id=tenant_id,
        trip_id=own_trip.id,
        driver_id=driver_app_context["driver"].id,
        amount_mzn=5000,
        allowance_mzn=2000,
        expenses_mzn=3000,
        currency="MZN",
        status="settled",
        notes="Despacho da viagem",
        request_reference=f"advance:{uuid4()}",
        issued_at=datetime(2026, 8, 19, 16, tzinfo=UTC),
    )
    foreign_advance = DriverAdvance(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        driver_id=driver_app_context["other_driver"].id,
        amount_mzn=4000,
        allowance_mzn=1500,
        expenses_mzn=2500,
        currency="MZN",
        status="issued",
        request_reference=f"advance:{uuid4()}",
    )
    db.add_all([own_advance, foreign_advance])
    await db.commit()

    response = await async_client.get(
        f"/api/v1/driver/records/advances?trip_id={own_trip.id}&limit=20&offset=0",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"] == [
        {
            "id": str(own_advance.id),
            "trip_id": str(own_trip.id),
            "total_amount": "5000.00",
            "allowance_amount": "2000.00",
            "expense_amount": "3000.00",
            "currency": "MZN",
            "status": "settled",
            "issued_at": "2026-08-19T16:00:00Z",
        }
    ]
    assert "notes" not in body["items"][0]
    assert "issued_by" not in body["items"][0]
    assert "request_reference" not in body["items"][0]


@pytest.mark.asyncio
async def test_driver_document_status_matches_tenant_requirements(
    async_client, db, tenant_id, driver_app_context
):
    tenant = await db.get(Tenant, tenant_id)
    tenant.compliance_policy = {
        "cargo_required_documents": [
            "load_permit",
            "cargo_manifest",
            "transport_document:guia_de_transporte",
        ]
    }
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="planned",
    )
    db.add(trip)
    await db.flush()
    load_permit = LoadPermit(
        tenant_id=tenant_id,
        trip_id=trip.id,
        permit_number="LP-001",
        status="valid",
    )
    manifest = CargoManifest(
        tenant_id=tenant_id,
        trip_id=trip.id,
        manifest_number="MAN-001",
        status="issued",
    )
    db.add_all([load_permit, manifest])
    await db.commit()

    incomplete = await async_client.get(
        f"/api/v1/driver/trips/{trip.id}/documents",
        headers=driver_app_context["headers"],
    )

    assert incomplete.status_code == 200, incomplete.text
    body = incomplete.json()
    assert body["complete"] is False
    assert body["missing_required"] == ["transport_document:guia_de_transporte"]
    assert {item["document_type"] for item in body["requirements"]} == {
        "load_permit",
        "cargo_manifest",
        "transport_document:guia_de_transporte",
    }
    assert {item["document_type"] for item in body["documents"]} == {
        "load_permit",
        "cargo_manifest",
    }

    guide = TransportDocument(
        tenant_id=tenant_id,
        trip_id=trip.id,
        document_type="guia_de_transporte",
        document_number="GT-001",
        status="valid",
    )
    db.add(guide)
    await db.commit()

    complete = await async_client.get(
        f"/api/v1/driver/trips/{trip.id}/documents",
        headers=driver_app_context["headers"],
    )

    assert complete.status_code == 200, complete.text
    assert complete.json()["complete"] is True
    assert complete.json()["missing_required"] == []

    already_available = await async_client.post(
        f"/api/v1/driver/trips/{trip.id}/document-requests",
        headers=driver_app_context["headers"],
        json={"document_type": "transport_document:guia_de_transporte"},
    )
    not_required = await async_client.post(
        f"/api/v1/driver/trips/{trip.id}/document-requests",
        headers=driver_app_context["headers"],
        json={"document_type": "transport_document:dav"},
    )
    assert already_available.status_code == 409, already_available.text
    assert already_available.json()["error"]["code"] == (
        "driver_document_already_available"
    )
    assert not_required.status_code == 422, not_required.text
    assert not_required.json()["error"]["code"] == "driver_document_not_required"


@pytest.mark.asyncio
async def test_driver_can_request_only_an_own_missing_document_idempotently(
    async_client, db, tenant_id, driver_app_context, auth_headers
):
    tenant = await db.get(Tenant, tenant_id)
    tenant.compliance_policy = {
        "cargo_required_documents": ["transport_document:guia_de_transporte"]
    }
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="planned",
    )
    db.add(trip)
    await db.commit()
    headers = {
        **driver_app_context["headers"],
        "Idempotency-Key": str(uuid4()),
    }
    payload = {
        "document_type": "transport_document:guia_de_transporte",
        "note": "Necessário antes da saída.",
    }

    async def post_request(key: str):
        return await async_client.post(
            f"/api/v1/driver/trips/{trip.id}/document-requests",
            headers={**driver_app_context["headers"], "Idempotency-Key": key},
            json=payload,
        )

    created, concurrent = await asyncio.gather(
        post_request(headers["Idempotency-Key"]),
        post_request(str(uuid4())),
    )
    replay = await async_client.post(
        f"/api/v1/driver/trips/{trip.id}/document-requests",
        headers=headers,
        json=payload,
    )

    assert created.status_code == 201, created.text
    assert concurrent.status_code == 201, concurrent.text
    assert replay.status_code == 201, replay.text
    assert concurrent.json() == created.json()
    assert replay.json() == created.json()
    assert created.json()["document_type"] == payload["document_type"]
    assert created.json()["status"] == "open"

    other_device_id = f"other-driver-doc-device-{uuid4().hex[:8]}"
    same_driver_device_id = f"same-driver-doc-device-{uuid4().hex[:8]}"
    db.add_all(
        [
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["other_driver"].id,
                device_id=other_device_id,
                device_name="Other Driver Document App",
                is_active=True,
            ),
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["driver"].id,
                device_id=same_driver_device_id,
                device_name="Second Driver Document App",
                is_active=True,
            ),
        ]
    )
    await db.commit()
    other_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["other_driver"].id,
        device_id=other_device_id,
        scope="driver_app",
    )
    same_driver_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["driver"].id,
        device_id=same_driver_device_id,
        scope="driver_app",
    )
    for token in (other_token, same_driver_token):
        cross_owner_replay = await async_client.post(
            f"/api/v1/driver/trips/{trip.id}/document-requests",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": str(tenant_id),
                "Idempotency-Key": headers["Idempotency-Key"],
            },
            json=payload,
        )
        assert cross_owner_replay.status_code == 409, cross_owner_replay.text
        assert cross_owner_replay.json()["error"]["code"] == (
            "idempotency_owner_mismatch"
        )

    assert (
        await db.scalar(
            select(func.count(OperationalException.id)).where(
                OperationalException.tenant_id == tenant_id,
                OperationalException.entity_id == trip.id,
                OperationalException.exception_type.like("driver_doc_request:%"),
            )
        )
        == 1
    )
    request_item = await db.scalar(
        select(OperationalException).where(
            OperationalException.tenant_id == tenant_id,
            OperationalException.entity_id == trip.id,
            OperationalException.exception_type.like("driver_doc_request:%"),
        )
    )
    issued = await async_client.post(
        f"/api/v1/trips/{trip.id}/transport-documents",
        headers=auth_headers,
        json={
            "document_type": "guia_de_transporte",
            "document_number": "GT-001",
        },
    )
    assert issued.status_code == 200, issued.text
    await db.refresh(request_item)
    assert request_item.status == "resolved"

    refreshed = await async_client.get(
        f"/api/v1/driver/trips/{trip.id}/documents",
        headers=driver_app_context["headers"],
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["complete"] is True
    assert refreshed.json()["requests"][0]["status"] == "resolved"


@pytest.mark.asyncio
async def test_driver_cannot_request_document_for_closed_or_foreign_trip(
    async_client, db, tenant_id, driver_app_context
):
    tenant = await db.get(Tenant, tenant_id)
    tenant.compliance_policy = {"cargo_required_documents": ["load_permit"]}
    closed_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
    )
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
    )
    db.add_all([closed_trip, foreign_trip])
    await db.commit()
    payload = {"document_type": "load_permit"}

    closed_response = await async_client.post(
        f"/api/v1/driver/trips/{closed_trip.id}/document-requests",
        headers=driver_app_context["headers"],
        json=payload,
    )
    foreign_response = await async_client.post(
        f"/api/v1/driver/trips/{foreign_trip.id}/document-requests",
        headers=driver_app_context["headers"],
        json=payload,
    )
    foreign_read = await async_client.get(
        f"/api/v1/driver/trips/{foreign_trip.id}/documents",
        headers=driver_app_context["headers"],
    )

    assert closed_response.status_code == 409, closed_response.text
    assert closed_response.json()["error"]["code"] == "driver_trip_read_only"
    assert foreign_response.status_code == 404, foreign_response.text
    assert foreign_read.status_code == 404, foreign_read.text
    assert (
        await db.scalar(
            select(func.count(OperationalException.id)).where(
                OperationalException.tenant_id == tenant_id,
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_cannot_use_manager_document_issuance_endpoint(
    async_client, db, tenant_id, driver_app_context
):
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="planned",
    )
    db.add(trip)
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/transport-documents",
        headers=driver_app_context["headers"],
        json={
            "document_type": "guia_de_transporte",
            "document_number": "GT-FORBIDDEN",
        },
    )

    assert response.status_code == 403, response.text
    assert (
        await db.scalar(
            select(func.count(TransportDocument.id)).where(
                TransportDocument.trip_id == trip.id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_downloads_only_a_file_attached_to_an_own_trip_document(
    async_client, db, tenant_id, driver_app_context, auth_headers, monkeypatch
):
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
    )
    db.add(trip)
    await db.flush()
    attached = await files_service.save_generated_file(
        db,
        tenant_id,
        content=b"driver-owned-document",
        filename="guia.pdf",
        mime_type="application/pdf",
        file_type="transport_document",
        entity_type="transport_document",
        entity_id=trip.id,
    )
    unrelated = await files_service.save_generated_file(
        db,
        tenant_id,
        content=b"unrelated-document",
        filename="unrelated.pdf",
        mime_type="application/pdf",
        file_type="transport_document",
        entity_type="transport_document",
        entity_id=uuid4(),
    )
    db.add(
        TransportDocument(
            tenant_id=tenant_id,
            trip_id=trip.id,
            document_type="guia_de_transporte",
            document_number="GT-DOWNLOAD",
            status="valid",
            file_id=attached.id,
        )
    )
    other_device_id = f"other-driver-download-{uuid4().hex[:8]}"
    db.add(
        DriverDevice(
            tenant_id=tenant_id,
            driver_id=driver_app_context["other_driver"].id,
            device_id=other_device_id,
            device_name="Other Driver Download App",
            is_active=True,
        )
    )
    await db.commit()
    other_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["other_driver"].id,
        device_id=other_device_id,
        scope="driver_app",
    )
    path = f"/api/v1/driver/trips/{trip.id}/documents/{attached.id}/download"

    owned = await async_client.get(path, headers=driver_app_context["headers"])
    unrelated_response = await async_client.get(
        f"/api/v1/driver/trips/{trip.id}/documents/{unrelated.id}/download",
        headers=driver_app_context["headers"],
    )
    foreign = await async_client.get(
        path,
        headers={
            "Authorization": f"Bearer {other_token}",
            "X-Tenant-Id": str(tenant_id),
        },
    )
    manager = await async_client.get(path, headers=auth_headers)

    assert owned.status_code == 200, owned.text
    assert owned.content == b"driver-owned-document"
    assert owned.headers["content-type"] == "application/pdf"
    assert "guia.pdf" in owned.headers["content-disposition"]
    assert unrelated_response.status_code == 404, unrelated_response.text
    assert foreign.status_code == 404, foreign.text
    assert manager.status_code == 403, manager.text

    async def r2_download_url(storage_key: str) -> str:
        assert storage_key == attached.storage_key
        return "https://objects.example.test/driver-document?signature=temporary"

    attached.storage_provider = "r2"
    monkeypatch.setattr(files_service._storage, "get_file_url", r2_download_url)
    await db.commit()
    r2_response = await async_client.get(
        path,
        headers=driver_app_context["headers"],
        follow_redirects=False,
    )
    assert r2_response.status_code == 307, r2_response.text
    assert r2_response.headers["location"] == (
        "https://objects.example.test/driver-document?signature=temporary"
    )


@pytest.mark.asyncio
async def test_dashboard_token_cannot_use_driver_contract(async_client, viewer_headers):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=viewer_headers,
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_scope_required"


@pytest.mark.asyncio
async def test_driver_cannot_list_general_fleet(async_client, driver_app_context):
    response = await async_client.get(
        "/api/v1/driver/vehicles",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_cannot_create_trip(
    async_client, db, tenant_id, driver_app_context
):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
            "cargo_type": "geral",
            "load_state": "loaded",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"
    assert await db.scalar(select(func.count(Trip.id)).where(Trip.tenant_id == tenant_id)) == 0


@pytest.mark.asyncio
async def test_driver_cannot_create_trip_for_another_driver(async_client, driver_app_context):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["other_driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_trip_creation_is_forbidden_before_payload_validation(
    async_client, driver_app_context
):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["driver"].id),
            "origin": "   ",
            "destination": "Matola",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_sync_rejects_another_authenticated_device(
    async_client, driver_app_context
):
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={"device_id": "another-device", "operations": []},
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_device_mismatch"


@pytest.mark.asyncio
async def test_driver_sync_refuses_manager_owned_operations(
    async_client, db, tenant_id, driver_app_context
):
    operations = [
        (
            "trip",
            {
                "vehicleId": str(driver_app_context["vehicle"].id),
                "driverId": str(driver_app_context["driver"].id),
                "origin": "Maputo",
                "destination": "Matola",
            },
        ),
        ("load_permit", {"tripId": str(uuid4()), "permitNumber": "LP-001"}),
        ("cargo_manifest", {"tripId": str(uuid4()), "manifestNumber": "MAN-001"}),
        (
            "transport_document",
            {"tripId": str(uuid4()), "documentType": "guia_remessa"},
        ),
    ]
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": f"forbidden-{entity_type}",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": entity_type,
                    "payload": payload,
                }
                for entity_type, payload in operations
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert [result["error_code"] for result in response.json()["results"]] == [
        "driver_operation_forbidden",
    ] * len(operations)
    assert await db.scalar(select(func.count(Trip.id)).where(Trip.tenant_id == tenant_id)) == 0


@pytest.mark.asyncio
async def test_driver_sync_bootstrap_only_advertises_driver_owned_operations(
    async_client, driver_app_context
):
    response = await async_client.get(
        "/api/v1/sync/bootstrap",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    assert set(response.json()["supported_entity_types"]) == {
        "checklist",
        "fuel_log",
        "trip_stop",
        "delivery_proof",
        "trip_cost",
    }


@pytest.mark.asyncio
async def test_driver_sync_cannot_write_to_another_drivers_trip(
    async_client, db, tenant_id, driver_app_context
):
    other_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(other_trip)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-stop",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "trip_stop",
                    "payload": {
                        "tripId": str(other_trip.id),
                        "stopType": "rest",
                        "address": "Matola",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_trip_forbidden"
    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == other_trip.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_sync_cannot_add_operations_to_a_closed_trip(
    async_client, db, tenant_id, driver_app_context
):
    closed_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
        billing_status="pending_delivery_proof",
    )
    db.add(closed_trip)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "closed-trip-stop",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "trip_stop",
                    "payload": {
                        "tripId": str(closed_trip.id),
                        "stopType": "rest",
                        "address": "Matola",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_trip_not_active"
    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == closed_trip.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_sync_cannot_submit_another_drivers_fuel_log(
    async_client, db, driver_app_context
):
    reference = f"foreign-driver-{uuid4()}"
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["other_driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1000,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_identity_mismatch"
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 0


@pytest.mark.asyncio
async def test_driver_sync_cannot_use_an_unassigned_vehicle(
    async_client, db, driver_app_context
):
    reference = f"unassigned-vehicle-{uuid4()}"
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "unassigned-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1000,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_vehicle_forbidden"
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 0


@pytest.mark.asyncio
async def test_driver_sync_accepts_own_assigned_vehicle(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(assigned_trip)
    await db.commit()
    reference = f"assigned-vehicle-{uuid4()}"

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "assigned-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "tripId": str(assigned_trip.id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1300,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "processed"
    assert result["error_code"] is None
    persisted_log = await db.scalar(
        select(FuelLog).where(FuelLog.payment_reference == reference)
    )
    assert persisted_log is not None
    assert persisted_log.trip_id == assigned_trip.id


@pytest.mark.asyncio
async def test_driver_sync_links_checklist_to_the_assigned_trip(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(assigned_trip)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "assigned-checklist",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "checklist",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "tripId": str(assigned_trip.id),
                        "templateId": str(driver_app_context["template"].id),
                        "type": driver_app_context["template"].type,
                        "responses": {"oil": True},
                        "complete": True,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "processed"
    checklist = await db.get(Checklist, UUID(result["server_id"]))
    assert checklist is not None
    assert checklist.trip_id == assigned_trip.id


@pytest.mark.asyncio
async def test_driver_sync_cannot_attach_fuel_to_another_drivers_trip(
    async_client, db, tenant_id, driver_app_context
):
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(foreign_trip)
    await db.commit()
    reference = f"foreign-trip-fuel-{uuid4()}"

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-trip-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "tripId": str(foreign_trip.id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1300,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_trip_forbidden"
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 0


@pytest.mark.asyncio
async def test_driver_sync_cannot_update_another_drivers_fuel_log(
    async_client, db, tenant_id, driver_app_context
):
    foreign_log = FuelLog(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        fuel_date=datetime.now(UTC),
        liters=30,
        total_cost=3000,
        km_at_refuel=1300,
        payment_reference=f"foreign-update-{uuid4()}",
    )
    db.add(foreign_log)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-fuel-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "fuel_log",
                    "payload": {
                        "serverId": str(foreign_log.id),
                        "liters": 99,
                        "totalCost": 9900,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_operation_forbidden"
    await db.refresh(foreign_log)
    assert float(foreign_log.liters) == 30
    assert float(foreign_log.total_cost) == 3000


@pytest.mark.asyncio
async def test_driver_sync_cannot_rewrite_own_submitted_fuel_facts(
    async_client, db, tenant_id, driver_app_context
):
    own_log = FuelLog(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        fuel_date=datetime.now(UTC),
        liters=30,
        total_cost=3000,
        km_at_refuel=1300,
        station_name="Posto original",
        payment_reference=f"immutable-fuel-{uuid4()}",
    )
    db.add(own_log)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "rewrite-own-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "fuel_log",
                    "payload": {
                        "serverId": str(own_log.id),
                        "liters": 99,
                        "totalCost": 9900,
                        "stationName": "Posto reescrito",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_operation_forbidden"
    await db.refresh(own_log)
    assert float(own_log.liters) == 30
    assert float(own_log.total_cost) == 3000
    assert own_log.station_name == "Posto original"


@pytest.mark.asyncio
async def test_driver_sync_cannot_update_another_drivers_operational_records(
    async_client, db, tenant_id, driver_app_context
):
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    foreign_checklist = Checklist(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        template_id=driver_app_context["template"].id,
        type=driver_app_context["template"].type,
        status="in_progress",
        responses={},
    )
    db.add_all([foreign_trip, foreign_checklist])
    await db.flush()
    foreign_stop = TripStop(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        stop_type="rest",
        address="Matola",
        notes="original stop",
        stopped_at=datetime.now(UTC),
    )
    foreign_proof = DeliveryProof(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        delivered_at=datetime.now(UTC),
        notes="original proof",
        status="pending",
    )
    db.add_all([foreign_stop, foreign_proof])
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-checklist-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "checklist",
                    "payload": {
                        "serverId": str(foreign_checklist.id),
                        "responses": {"oil": True},
                    },
                },
                {
                    "local_id": "foreign-stop-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "trip_stop",
                    "payload": {
                        "serverId": str(foreign_stop.id),
                        "notes": "tampered stop",
                    },
                },
                {
                    "local_id": "foreign-proof-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "delivery_proof",
                    "payload": {
                        "serverId": str(foreign_proof.id),
                        "notes": "tampered proof",
                    },
                },
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert [result["error_code"] for result in response.json()["results"]] == [
        "driver_record_forbidden",
        "driver_record_forbidden",
        "driver_record_forbidden",
    ]
    await db.refresh(foreign_checklist)
    await db.refresh(foreign_stop)
    await db.refresh(foreign_proof)
    assert foreign_checklist.responses == {}
    assert foreign_stop.notes == "original stop"
    assert foreign_proof.notes == "original proof"


@pytest.mark.asyncio
async def test_driver_sync_rejects_idempotent_replay_from_another_owner_or_device(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    other_device_id = f"other-driver-device-{uuid4().hex[:8]}"
    same_driver_device_id = f"same-driver-device-{uuid4().hex[:8]}"
    db.add_all(
        [
            assigned_trip,
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["other_driver"].id,
                device_id=other_device_id,
                device_name="Other Driver App",
                is_active=True,
            ),
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["driver"].id,
                device_id=same_driver_device_id,
                device_name="Second Driver App",
                is_active=True,
            ),
        ]
    )
    await db.commit()

    other_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["other_driver"].id,
        device_id=other_device_id,
        scope="driver_app",
    )
    same_driver_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["driver"].id,
        device_id=same_driver_device_id,
        scope="driver_app",
    )
    key = str(uuid4())
    operation = {
        "local_id": "owned-stop-replay",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip_stop",
        "payload": {
            "tripId": str(assigned_trip.id),
            "stopType": "rest",
            "address": "Matola",
        },
    }

    first = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={"device_id": driver_app_context["device_id"], "operations": [operation]},
    )
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "processed"

    for token, device_id, operations in (
        (other_token, other_device_id, [operation, operation]),
        (same_driver_token, same_driver_device_id, [operation]),
    ):
        replay = await async_client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": str(tenant_id),
            },
            json={"device_id": device_id, "operations": operations},
        )
        assert replay.status_code == 200, replay.text
        for result in replay.json()["results"]:
            assert result["status"] == "conflict"
            assert result["error_code"] == "idempotency_owner_mismatch"
            assert result["server_id"] is None

    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == assigned_trip.id)
        )
        == 1
    )
    mismatch_events = (
        await db.scalars(
            select(SyncEvent).where(
                SyncEvent.tenant_id == tenant_id,
                SyncEvent.idempotency_key == key,
                SyncEvent.error_code == "idempotency_owner_mismatch",
            )
        )
    ).all()
    assert len(mismatch_events) == 3
    assert {event.driver_id for event in mismatch_events} == {
        driver_app_context["driver"].id,
        driver_app_context["other_driver"].id,
    }
    assert {event.device_id for event in mismatch_events} == {
        other_device_id,
        same_driver_device_id,
    }
    assert all(event.server_id is None for event in mismatch_events)


@pytest.mark.asyncio
async def test_driver_sync_concurrent_key_consumption_accepts_exactly_one_device(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Marracuene",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    second_device_id = f"racing-device-{uuid4().hex[:8]}"
    db.add_all(
        [
            assigned_trip,
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["driver"].id,
                device_id=second_device_id,
                device_name="Racing Driver App",
                is_active=True,
            ),
        ]
    )
    await db.commit()

    second_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["driver"].id,
        device_id=second_device_id,
        scope="driver_app",
    )
    key = str(uuid4())
    operation = {
        "local_id": "concurrent-owned-stop",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip_stop",
        "payload": {
            "tripId": str(assigned_trip.id),
            "stopType": "rest",
            "address": "Marracuene",
        },
    }

    async def post(token: str, device_id: str):
        return await async_client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": str(tenant_id),
            },
            json={"device_id": device_id, "operations": [operation]},
        )

    responses = await asyncio.gather(
        post(
            driver_app_context["headers"]["Authorization"].removeprefix("Bearer "),
            driver_app_context["device_id"],
        ),
        post(second_token, second_device_id),
    )
    assert all(response.status_code == 200 for response in responses)
    results = [response.json()["results"][0] for response in responses]
    assert sorted(result["status"] for result in results) == ["conflict", "processed"]
    conflict = next(result for result in results if result["status"] == "conflict")
    assert conflict["error_code"] == "idempotency_owner_mismatch"
    assert conflict["server_id"] is None

    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == assigned_trip.id)
        )
        == 1
    )
    stored = await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.idempotency_key == key,
        )
    )
    assert stored is not None
    assert stored.driver_id == driver_app_context["driver"].id
    assert stored.device_id in {driver_app_context["device_id"], second_device_id}
