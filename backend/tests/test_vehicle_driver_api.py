from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver
from app.modules.files.models import File
from app.modules.fuel.models import FuelLog
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_tenant(
    max_vehicles: int | None = 5,
    max_drivers: int | None = 5,
) -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Tenant Fleet Setup {suffix}",
            slug=f"fleet-setup-{suffix}",
            max_vehicles=max_vehicles,
            max_drivers=max_drivers,
        )
        db.add(tenant)
        await db.flush()
        # SQLAlchemy applies the trial-plan defaults during INSERT. Reassigning
        # after the flush lets this factory represent an explicit unlimited
        # plan (persisted NULL), which is distinct from an omitted limit.
        tenant.max_vehicles = max_vehicles
        tenant.max_drivers = max_drivers
        await db.commit()
        await db.refresh(tenant)
        return tenant


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_vehicle_crud_and_plate_conflict_are_tenant_scoped() -> None:
    tenant = await create_tenant()
    other_tenant = await create_tenant()

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/vehicles",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "vehicle:create:abc-123"},
            json={
                "plate": "ABC-123-MZ",
                "brand": "Toyota",
                "model": "Dyna",
                "year": 2020,
                "category": "pesado",
                "fuel_type": "gasoleo",
                "current_km": 45000,
            },
        )
        assert response.status_code == 200
        vehicle = response.json()
        assert vehicle["plate"] == "ABC-123-MZ"
        assert vehicle["status"] == "active"
        replay_response = await client.post(
            "/api/v1/vehicles",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "vehicle:create:abc-123"},
            json={
                "plate": "ABC-123-MZ",
                "brand": "Toyota",
                "model": "Dyna",
                "year": 2020,
                "category": "pesado",
                "fuel_type": "gasoleo",
                "current_km": 45000,
            },
        )
        assert replay_response.status_code == 200
        assert replay_response.json()["id"] == vehicle["id"]

        duplicate_response = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(tenant.id),
            json={"plate": "ABC-123-MZ", "category": "pesado"},
        )
        assert duplicate_response.status_code == 409

        other_tenant_response = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(other_tenant.id),
            json={"plate": "ABC-123-MZ", "category": "pesado"},
        )
        assert other_tenant_response.status_code == 200

        list_response = await client.get(
            "/api/v1/vehicles",
            headers=auth_headers(tenant.id),
            params={"search": "Dyna"},
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [vehicle["id"]]

        patch_response = await client.patch(
            f"/api/v1/vehicles/{vehicle['id']}",
            headers=auth_headers(tenant.id),
            json={"current_km": 45500, "status": "maintenance"},
        )
        assert patch_response.status_code == 200
        patched = patch_response.json()
        assert patched["current_km"] == 45500
        assert patched["status"] == "maintenance"

        qr_response = await client.get(
            f"/api/v1/vehicles/{vehicle['id']}/qr-code",
            headers=auth_headers(tenant.id),
        )
        assert qr_response.status_code == 200
        assert qr_response.json()["deep_link"].endswith(f"{vehicle['id']}/checklist")

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == UUID(vehicle["id"]),
            )
        )
        assert set(audit_rows.scalars()) == {
            "vehicle.created",
            "vehicle.updated",
            "vehicle.qr_code_issued",
        }


@pytest.mark.asyncio
async def test_driver_crud_and_phone_conflict_are_tenant_scoped() -> None:
    tenant = await create_tenant()
    other_tenant = await create_tenant()

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/drivers",
            headers=auth_headers(tenant.id),
            json={
                "full_name": "Ana Mucavele",
                "phone": "258840001111",
                "email": "ana@example.test",
                "license_number": "C-001",
                "license_category": "C",
                "employment_type": "efectivo",
            },
        )
        assert response.status_code == 200
        driver = response.json()
        assert driver["full_name"] == "Ana Mucavele"
        assert driver["status"] == "active"

        duplicate_response = await client.post(
            "/api/v1/drivers",
            headers=auth_headers(tenant.id),
            json={"full_name": "Outra Ana", "phone": "258840001111"},
        )
        assert duplicate_response.status_code == 409

        other_tenant_response = await client.post(
            "/api/v1/drivers",
            headers=auth_headers(other_tenant.id),
            json={"full_name": "Ana Outro Tenant", "phone": "258840001111"},
        )
        assert other_tenant_response.status_code == 200

        list_response = await client.get(
            "/api/v1/drivers",
            headers=auth_headers(tenant.id),
            params={"search": "Mucavele"},
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [driver["id"]]

        patch_response = await client.patch(
            f"/api/v1/drivers/{driver['id']}",
            headers=auth_headers(tenant.id),
            json={"status": "suspended", "emergency_contact_name": "Paulo Mucavele"},
        )
        assert patch_response.status_code == 200
        patched = patch_response.json()
        assert patched["status"] == "suspended"
        assert patched["emergency_contact_name"] == "Paulo Mucavele"

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == UUID(driver["id"]),
            )
        )
        assert set(audit_rows.scalars()) == {"driver.created", "driver.updated"}


@pytest.mark.asyncio
async def test_assignment_compliance_blocks_can_be_overridden_by_waiver() -> None:
    tenant = await create_tenant()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        expired_vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"EXP-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            documents={
                "required_documents": ["insurance"],
                "insurance_valid_until": "2020-01-01",
            },
        )
        expired_driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Expired Driver {suffix}",
            phone=f"25887{suffix[:7]}",
            license_valid_until=date(2020, 1, 1),
        )
        compliant_vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"OK-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        compliant_driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Compliant Driver {suffix}",
            phone=f"25888{suffix[:7]}",
        )
        db.add_all([expired_vehicle, expired_driver, compliant_vehicle, compliant_driver])
        await db.commit()
        await db.refresh(expired_vehicle)
        await db.refresh(expired_driver)
        await db.refresh(compliant_vehicle)
        await db.refresh(compliant_driver)

    async with await create_api_client() as client:
        vehicle_block = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(expired_vehicle.id),
                "driver_id": str(compliant_driver.id),
                "origin": "Maputo",
                "destination": "Xai-Xai",
                "cargo_type": "Carga geral",
            },
        )
        assert vehicle_block.status_code == 409
        assert vehicle_block.json()["error"]["code"] == "vehicle_compliance_blocked"

        vehicle_waiver = await client.post(
            "/api/v1/operations/waivers",
            headers=auth_headers(tenant.id),
            json={
                "entity_type": "vehicle",
                "entity_id": str(expired_vehicle.id),
                "waiver_type": "expired_warning",
                "reason": "Seguro renovado fisicamente, documento digital pendente.",
                "risk_level": "medium",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )
        assert vehicle_waiver.status_code == 200

        vehicle_override = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(expired_vehicle.id),
                "driver_id": str(compliant_driver.id),
                "origin": "Maputo",
                "destination": "Xai-Xai",
                "cargo_type": "Carga geral",
            },
        )
        assert vehicle_override.status_code == 200

        driver_block = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(compliant_vehicle.id),
                "driver_id": str(expired_driver.id),
                "origin": "Maputo",
                "destination": "Matola",
                "cargo_type": "Carga geral",
            },
        )
        assert driver_block.status_code == 409
        assert driver_block.json()["error"]["code"] == "driver_compliance_blocked"

        driver_waiver = await client.post(
            "/api/v1/operations/waivers",
            headers=auth_headers(tenant.id),
            json={
                "entity_type": "driver",
                "entity_id": str(expired_driver.id),
                "waiver_type": "expired_warning",
                "reason": "Renovacao INATTER em curso com comprovativo administrativo.",
                "risk_level": "high",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )
        assert driver_waiver.status_code == 200

        driver_override = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(compliant_vehicle.id),
                "driver_id": str(expired_driver.id),
                "origin": "Maputo",
                "destination": "Matola",
                "cargo_type": "Carga geral",
            },
        )
        assert driver_override.status_code == 200


@pytest.mark.asyncio
async def test_tenant_compliance_policy_requires_missing_documents() -> None:
    tenant = await create_tenant()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant_row = await db.get(Tenant, tenant.id)
        assert tenant_row is not None
        tenant_row.compliance_policy = {
            "vehicle_required_documents": ["insurance"],
            "driver_required_documents": ["driving_license"],
        }
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"POL-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            documents={},
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Policy Driver {suffix}",
            phone=f"25889{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(vehicle)
        await db.refresh(driver)

    async with await create_api_client() as client:
        vehicle_block = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Marracuene",
                "cargo_type": "Carga geral",
            },
        )
        assert vehicle_block.status_code == 409
        assert vehicle_block.json()["error"]["code"] == "vehicle_compliance_blocked"
        assert vehicle_block.json()["error"]["details"]["violations"][0]["code"] == (
            "missing_document"
        )

    async with AsyncSessionLocal() as db:
        vehicle_row = await db.get(Vehicle, vehicle.id)
        assert vehicle_row is not None
        vehicle_row.documents = {"insurance_valid_until": "2030-01-01"}
        await db.commit()

    async with await create_api_client() as client:
        driver_block = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Marracuene",
                "cargo_type": "Carga geral",
            },
        )
        assert driver_block.status_code == 409
        assert driver_block.json()["error"]["code"] == "driver_compliance_blocked"
        assert driver_block.json()["error"]["details"]["violations"][0]["document_type"] == (
            "driving_license"
        )


@pytest.mark.asyncio
async def test_vehicle_and_driver_availability_summaries_explain_blockers_and_warnings() -> None:
    tenant = await create_tenant()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant_row = await db.get(Tenant, tenant.id)
        assert tenant_row is not None
        tenant_row.compliance_policy = {
            "vehicle_required_documents": ["insurance"],
            "driver_required_documents": ["driving_license"],
            "document_expiry_warning_days": 30,
        }
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"AVL-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            documents={"insurance_valid_until": "2020-01-01"},
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Availability Driver {suffix}",
            phone=f"25892{suffix[:7]}",
            license_valid_until=datetime.now(UTC).date(),
        )
        db.add_all([vehicle, driver])
        await db.flush()
        trip = Trip(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            origin="Maputo",
            destination="Beira",
            cargo_type="Carga geral",
            status="planned",
        )
        db.add(trip)
        await db.commit()
        await db.refresh(vehicle)
        await db.refresh(driver)
        await db.refresh(trip)

    async with await create_api_client() as client:
        vehicle_summary = await client.get(
            f"/api/v1/vehicles/{vehicle.id}/availability",
            headers=auth_headers(tenant.id),
        )
        assert vehicle_summary.status_code == 200
        vehicle_payload = vehicle_summary.json()
        assert vehicle_payload["available"] is False
        assert {item["code"] for item in vehicle_payload["blockers"]} == {
            "vehicle_compliance_blocked",
            "vehicle_assignment_conflict",
        }
        assert vehicle_payload["compliance_violations"][0]["document_type"] == "insurance"

        driver_summary = await client.get(
            f"/api/v1/drivers/{driver.id}/availability",
            headers=auth_headers(tenant.id),
        )
        assert driver_summary.status_code == 200
        driver_payload = driver_summary.json()
        assert driver_payload["available"] is False
        assert {item["code"] for item in driver_payload["blockers"]} == {
            "driver_assignment_conflict"
        }
        assert driver_payload["warnings"][0]["document_type"] == "driving_license"

        waiver_response = await client.post(
            "/api/v1/operations/waivers",
            headers=auth_headers(tenant.id),
            json={
                "entity_type": "vehicle",
                "entity_id": str(vehicle.id),
                "waiver_type": "expired_warning",
                "reason": "Renovacao comprovada fisicamente.",
                "risk_level": "medium",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )
        assert waiver_response.status_code == 200

        vehicle_without_trip = await client.get(
            f"/api/v1/vehicles/{vehicle.id}/availability",
            headers=auth_headers(tenant.id),
            params={"exclude_trip_id": str(trip.id)},
        )
        assert vehicle_without_trip.status_code == 200
        vehicle_without_trip_payload = vehicle_without_trip.json()
        assert vehicle_without_trip_payload["available"] is True
        assert vehicle_without_trip_payload["blockers"] == []
        assert vehicle_without_trip_payload["active_waivers"][0]["waiver_type"] == (
            "expired_warning"
        )

        driver_without_trip = await client.get(
            f"/api/v1/drivers/{driver.id}/availability",
            headers=auth_headers(tenant.id),
            params={"exclude_trip_id": str(trip.id)},
        )
        assert driver_without_trip.status_code == 200
        driver_without_trip_payload = driver_without_trip.json()
        assert driver_without_trip_payload["available"] is True
        assert driver_without_trip_payload["warnings"][0]["code"] == "document_expiring"


@pytest.mark.asyncio
async def test_document_renewal_links_files_and_unblocks_assignment() -> None:
    tenant = await create_tenant()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant_row = await db.get(Tenant, tenant.id)
        assert tenant_row is not None
        tenant_row.compliance_policy = {
            "vehicle_required_documents": ["insurance"],
            "driver_required_documents": ["driving_license"],
        }
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"REN-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            documents={"insurance_valid_until": "2020-01-01"},
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Renew Driver {suffix}",
            phone=f"25890{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(vehicle)
        await db.refresh(driver)

    async with await create_api_client() as client:
        blocked = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Boane",
                "cargo_type": "Carga geral",
            },
        )
        assert blocked.status_code == 409

        vehicle_file = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "insurance", "entity_type": "vehicle_document"},
            files={"upload": ("insurance.pdf", b"insurance-renewal", "application/pdf")},
        )
        assert vehicle_file.status_code == 200
        vehicle_file_id = vehicle_file.json()["id"]
        vehicle_renewal = await client.post(
            f"/api/v1/vehicles/{vehicle.id}/documents/insurance/renew",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "vehicle-doc-renew:001"},
            json={
                "valid_until": "2031-01-01",
                "file_id": vehicle_file_id,
                "reference": "INS-2031",
                "notes": "Renovacao anual.",
            },
        )
        assert vehicle_renewal.status_code == 200
        assert vehicle_renewal.json()["documents"]["insurance"]["file_id"] == vehicle_file_id
        vehicle_replay = await client.post(
            f"/api/v1/vehicles/{vehicle.id}/documents/insurance/renew",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "vehicle-doc-renew:001"},
            json={
                "valid_until": "2031-01-01",
                "file_id": vehicle_file_id,
                "reference": "INS-2031",
                "notes": "Renovacao anual.",
            },
        )
        assert vehicle_replay.status_code == 200
        assert vehicle_replay.json()["documents"]["insurance"]["reference"] == "INS-2031"

        driver_file = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "driving_license", "entity_type": "driver_document"},
            files={"upload": ("inatter.pdf", b"inatter-renewal", "application/pdf")},
        )
        assert driver_file.status_code == 200
        driver_file_id = driver_file.json()["id"]
        driver_renewal = await client.post(
            f"/api/v1/drivers/{driver.id}/documents/driving_license/renew",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "driver-doc-renew:001"},
            json={
                "valid_until": "2031-01-01",
                "file_id": driver_file_id,
                "reference": "INATTER-2031",
            },
        )
        assert driver_renewal.status_code == 200
        assert driver_renewal.json()["license_valid_until"] == "2031-01-01"
        assert driver_renewal.json()["documents"]["driving_license"]["file_id"] == driver_file_id

        unblocked = await client.post(
            "/api/v1/trips",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Boane",
                "cargo_type": "Carga geral",
            },
        )
        assert unblocked.status_code == 200

        tower_response = await client.get("/api/v1/control-tower", headers=auth_headers(tenant.id))
        assert tower_response.status_code == 200
        tower = tower_response.json()
        assert tower["queues"]["vehicle_documents_expiring"] == []
        assert tower["queues"]["driver_documents_expiring"] == []

    async with AsyncSessionLocal() as db:
        vehicle_file_row = await db.get(File, UUID(vehicle_file_id))
        assert vehicle_file_row is not None
        assert vehicle_file_row.entity_id == vehicle.id
        driver_file_row = await db.get(File, UUID(driver_file_id))
        assert driver_file_row is not None
        assert driver_file_row.entity_id == driver.id
        audit_rows = await db.execute(
            select(AuditLog.action).where(AuditLog.tenant_id == tenant.id)
        )
        audit_actions = set(audit_rows.scalars())
        assert "vehicle.document_renewed" in audit_actions
        assert "driver.document_renewed" in audit_actions


@pytest.mark.asyncio
async def test_vehicle_limit_returns_403_with_upgrade_url() -> None:
    """Creating a vehicle past max_vehicles returns 403 with upgrade_url in details."""
    tenant = await create_tenant(max_vehicles=1)

    async with await create_api_client() as client:
        first_response = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(tenant.id),
            json={"plate": f"LIM-{uuid4().hex[:6].upper()}", "category": "pesado"},
        )
        assert first_response.status_code == 200

        limit_response = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(tenant.id),
            json={"plate": f"LIM-{uuid4().hex[:6].upper()}", "category": "pesado"},
        )
        assert limit_response.status_code == 403
        assert "upgrade_url" in limit_response.json().get("error", {}).get("details", {})


@pytest.mark.asyncio
async def test_no_limit_when_max_null() -> None:
    """When Tenant.max_vehicles is None, vehicles can be created past default limit."""
    tenant = await create_tenant(max_vehicles=None)

    async with await create_api_client() as client:
        for _ in range(6):
            response = await client.post(
                "/api/v1/vehicles",
                headers=auth_headers(tenant.id),
                json={
                    "plate": f"UNL-{uuid4().hex[:6].upper()}",
                    "category": "pesado",
                },
            )
            assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_vehicle_and_driver_histories_are_detailed_and_separate() -> None:
    tenant = await create_tenant()
    other_tenant = await create_tenant()
    now = datetime.now(UTC)
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"HST-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            current_km=1000,
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"History Driver {suffix}",
            phone=f"25891{suffix[:7]}",
        )
        template = ChecklistTemplate(
            tenant_id=tenant.id,
            name="Pre-departure",
            type="pre_departure",
            items=[],
        )
        db.add_all([vehicle, driver, template])
        await db.flush()
        trip = Trip(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            origin="Maputo",
            destination="Beira",
            cargo_type="Carga geral",
            status="delivered",
            actual_departure=now,
            km_start=1000,
            km_end=2100,
        )
        fuel_log = FuelLog(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            fuel_date=now,
            station_name="Posto Matola",
            fuel_type="gasoleo",
            liters=120,
            total_cost=9000,
            km_at_refuel=1500,
        )
        checklist = Checklist(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            template_id=template.id,
            type="pre_departure",
            status="passed",
            responses={},
            completed_at=now,
        )
        db.add_all([trip, fuel_log, checklist])
        await db.commit()
        vehicle_id = vehicle.id
        driver_id = driver.id

    async with await create_api_client() as client:
        vehicle_history = await client.get(
            f"/api/v1/vehicles/{vehicle_id}/history",
            headers=auth_headers(tenant.id),
        )
        assert vehicle_history.status_code == 200
        vehicle_payload = vehicle_history.json()
        assert vehicle_payload["vehicle"]["id"] == str(vehicle_id)
        vehicle_sources = {item["source"] for item in vehicle_payload["items"]}
        assert {"trips", "fuel", "checklists"}.issubset(vehicle_sources)
        vehicle_trip = next(item for item in vehicle_payload["items"] if item["source"] == "trips")
        assert vehicle_trip["details"]["driver_id"] == str(driver_id)

        driver_history = await client.get(
            f"/api/v1/drivers/{driver_id}/history",
            headers=auth_headers(tenant.id),
        )
        assert driver_history.status_code == 200
        driver_payload = driver_history.json()
        assert driver_payload["driver"]["id"] == str(driver_id)
        driver_sources = {item["source"] for item in driver_payload["items"]}
        assert {"trips", "fuel", "checklists"}.issubset(driver_sources)
        driver_trip = next(item for item in driver_payload["items"] if item["source"] == "trips")
        assert driver_trip["details"]["vehicle_id"] == str(vehicle_id)

        other_tenant_vehicle_history = await client.get(
            f"/api/v1/vehicles/{vehicle_id}/history",
            headers=auth_headers(other_tenant.id),
        )
        assert other_tenant_vehicle_history.status_code == 404
