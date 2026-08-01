from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.billing import service as billing_service
from app.modules.billing.schemas import BillingDocumentCreate, IssueBillingDocumentRequest
from app.modules.cargo import service as cargo_service
from app.modules.cargo.schemas import (
    DeliveryProofCreate,
    LoadPermitCreate,
    ValidateDeliveryProofRequest,
)
from app.modules.contracts import service as contract_service
from app.modules.contracts.schemas import ContractCreate, ContractPatch
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.tenants.models import Tenant
from app.modules.trips import service as trips_service
from app.modules.trips.models import Trip
from app.modules.trips.schemas import (
    AssociateContractRequest,
    CompleteTripRequest,
    StartTripRequest,
    TripCreate,
)
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


async def create_seed_entities(db: AsyncSession):
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Tenant {suffix}", slug=f"tenant-{suffix}")
    db.add(tenant)
    await db.flush()

    vehicle = Vehicle(
        tenant_id=tenant.id,
        plate=f"RT-{suffix}",
        category="pesado",
        fuel_type="gasoleo",
    )
    driver = Driver(
        tenant_id=tenant.id,
        full_name=f"Motorista {suffix}",
        phone="258840000000",
    )
    db.add_all([vehicle, driver])
    await db.commit()
    await db.refresh(tenant)
    await db.refresh(vehicle)
    await db.refresh(driver)
    return tenant, vehicle, driver


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_trip_first_flow_reaches_billing_document() -> None:
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

            contract = await contract_service.create_contract(
                db,
                tenant.id,
                ContractCreate(
                    client_name="Cliente Industrial",
                    contract_reference=f"CTR-{uuid4().hex[:8]}",
                    default_unit_price=12500,
                ),
            )
            contract = await contract_service.patch_contract(
                db,
                tenant.id,
                contract["id"],
                ContractPatch(notes="Contrato validado para piloto."),
            )

            trip = await trips_service.create_trip(
                db,
                tenant.id,
                TripCreate(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    origin="Matola",
                    destination="Chimoio",
                    cargo_type="Produtos manufaturados",
                    load_state="loaded_empty",
                    requires_load_permit=True,
                ),
            )
            assert trip["contract_id"] is None
            assert trip["billing_status"] == "pending_delivery_proof"

            trip = await trips_service.associate_contract(
                db,
                tenant.id,
                trip["id"],
                AssociateContractRequest(contract_id=contract["id"]),
            )
            assert trip["contract_id"] == contract["id"]

            await cargo_service.create_load_permit(
                db,
                tenant.id,
                trip["id"],
                LoadPermitCreate(
                    contract_id=contract["id"],
                    client_name="Cliente Industrial",
                    permit_number="LP-001",
                    district="Chimoio",
                    issuer_name="Cliente Industrial",
                ),
            )

            await trips_service.start_trip(
                db,
                tenant.id,
                trip["id"],
                StartTripRequest(km_start=1000, actual_departure=dt("2026-06-01T08:00:00")),
            )

            await trips_service.complete_trip(
                db,
                tenant.id,
                trip["id"],
                CompleteTripRequest(km_end=1800, actual_arrival=dt("2026-06-03T14:00:00")),
            )

            proof = await cargo_service.create_delivery_proof(
                db,
                tenant.id,
                trip["id"],
                DeliveryProofCreate(
                    contract_id=contract["id"],
                    load_permit_number="LP-001",
                    document_number="GD-001",
                    proof_type="client_discharge_note",
                    client_type="company",
                    delivered_at=dt("2026-06-03T15:00:00"),
                    quantity_delivered=1,
                ),
            )
            assert proof["status"] == "pending"
            assert proof["trip_billing_status"] == "pending_delivery_validation"

            validated = await cargo_service.validate_delivery_proof(
                db,
                tenant.id,
                trip["id"],
                proof["id"],
                None,
                ValidateDeliveryProofRequest(validation_method="manual_review"),
            )
            assert validated["trip_billing_status"] == "billable"

            candidates = await billing_service.list_billable_trips(
                db,
                tenant.id,
                contract_reference=contract["contract_reference"],
                period_start=dt("2026-06-01T00:00:00"),
                period_end=dt("2026-07-01T00:00:00"),
            )
            assert candidates[0]["candidate_status"] == "billable"
            assert candidates[0]["vehicle_plate"] == vehicle.plate
            assert candidates[0]["amount"] == 12500

            billing_document = await billing_service.create_document(
                db,
                tenant.id,
                BillingDocumentCreate(
                    contract_id=contract["id"],
                    client_name="Cliente Industrial",
                    contract_reference=contract["contract_reference"],
                    billing_period_start=dt("2026-06-01T00:00:00"),
                    billing_period_end=dt("2026-07-01T00:00:00"),
                    trip_ids=[trip["id"]],
                    client_nuit="400123456",
                ),
            )
            assert billing_document["total_amount"] == 12500
            assert billing_document["status"] == "draft"

            draft_document = await billing_service.get_document(
                db,
                tenant.id,
                billing_document["id"],
            )
            assert draft_document["items"][0]["status"] == "draft"

            draft_trip = await db.get(Trip, trip["id"])
            assert draft_trip is not None
            assert draft_trip.billing_status == "billing_draft"
            assert draft_trip.billed_at is None

            issued_document = await billing_service.issue_document(
                db,
                tenant.id,
                billing_document["id"],
                IssueBillingDocumentRequest(issued_at=dt("2026-06-30T12:00:00")),
            )
            assert issued_document["status"] == "issued"
            assert issued_document["items"][0]["status"] == "billed"

            issued_trip = await db.get(Trip, trip["id"])
            assert issued_trip is not None
            assert issued_trip.billing_status == "billed"
            assert issued_trip.billed_at == dt("2026-06-30T12:00:00")

            audit_rows = await db.execute(
                select(AuditLog.action).where(AuditLog.tenant_id == tenant.id)
            )
            audit_actions = set(audit_rows.scalars())
            assert {
                "cargo.load_permit_created",
                "cargo.delivery_proof_created",
                "cargo.delivery_proof_validated",
                "contract.created",
                "contract.updated",
                "billing.document_created",
                "billing.item_created",
                "billing.document_issued",
                "billing.item_billed",
                "trip.billing_finalized",
            }.issubset(audit_actions)

            permit_audit = await db.scalar(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.action == "cargo.load_permit_created",
                )
            )
            assert permit_audit is not None
            permit_values = permit_audit.new_values
            assert permit_values is not None
            assert permit_values["client_name"] == "Cliente Industrial"
            assert permit_values["district"] == "Chimoio"
            assert permit_values["issuer_name"] == "Cliente Industrial"

            proof_audit = await db.scalar(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.action == "cargo.delivery_proof_created",
                )
            )
            assert proof_audit is not None
            proof_values = proof_audit.new_values
            assert proof_values is not None
            assert proof_values["load_permit_number"] == "LP-001"
            assert proof_values["cargo_condition"] == "intact"
            assert proof_values["quantity_delivered"] == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_api_trip_first_flow_respects_billing_issue_boundary() -> None:
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

        async with await create_api_client() as client:
            headers = auth_headers(tenant.id)
            reference = f"CTR-{uuid4().hex[:8]}"

            contract_response = await client.post(
                "/api/v1/contracts/",
                headers=headers,
                json={
                    "client_name": "Cliente API",
                    "contract_reference": reference,
                    "default_unit_price": 8800,
                },
            )
            assert contract_response.status_code == 200
            contract = contract_response.json()

            trip_response = await client.post(
                "/api/v1/trips",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle.id),
                    "driver_id": str(driver.id),
                    "origin": "Beira",
                    "destination": "Nacala",
                    "cargo_type": "Produtos manufaturados",
                    "load_state": "loaded_loaded",
                    "requires_load_permit": True,
                    "requires_cargo_manifest": True,
                },
            )
            assert trip_response.status_code == 200
            trip = trip_response.json()
            assert trip["contract_id"] is None
            assert trip["billing_status"] == "pending_delivery_proof"

            associate_response = await client.post(
                f"/api/v1/trips/{trip['id']}/associate-contract",
                headers=headers,
                json={"contract_id": contract["id"]},
            )
            assert associate_response.status_code == 200

            permit_response = await client.post(
                f"/api/v1/trips/{trip['id']}/load-permits",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "client_name": "Cliente API",
                    "permit_number": "LP-API-001",
                    "issuer_name": "Cliente API",
                    "district": "Nacala",
                    "load_state": "loaded",
                },
            )
            assert permit_response.status_code == 200

            manifest_response = await client.post(
                f"/api/v1/trips/{trip['id']}/cargo-manifest",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "manifest_number": "MC-API-001",
                    "client_name": "Cliente API",
                    "cargo_description": "Produtos manufaturados",
                    "cargo_type": "manufactured_goods",
                    "package_count": 12,
                    "origin": "Beira",
                    "destination": "Nacala",
                },
            )
            assert manifest_response.status_code == 200

            start_response = await client.post(
                f"/api/v1/trips/{trip['id']}/start",
                headers=headers,
                json={"km_start": 1000, "actual_departure": "2026-07-01T06:00:00+00:00"},
            )
            assert start_response.status_code == 200

            complete_response = await client.post(
                f"/api/v1/trips/{trip['id']}/complete",
                headers=headers,
                json={"km_end": 2400, "actual_arrival": "2026-07-02T09:00:00+00:00"},
            )
            assert complete_response.status_code == 200

            proof_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "load_permit_number": "LP-API-001",
                    "document_number": "GD-API-001",
                    "proof_type": "client_discharge_note",
                    "client_type": "company",
                    "delivered_at": "2026-07-02T10:30:00+00:00",
                    "quantity_delivered": 12,
                },
            )
            assert proof_response.status_code == 200
            proof = proof_response.json()
            assert proof["trip_billing_status"] == "pending_delivery_validation"

            candidates_before_validation = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-07-01T00:00:00+00:00",
                    "period_end": "2026-08-01T00:00:00+00:00",
                    "status": "billable",
                },
            )
            assert candidates_before_validation.status_code == 200
            assert candidates_before_validation.json() == []

            validation_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/validate",
                headers=headers,
                json={"validation_method": "manual_review"},
            )
            assert validation_response.status_code == 200
            assert validation_response.json()["trip_billing_status"] == "billable"

            candidates_response = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-07-01T00:00:00+00:00",
                    "period_end": "2026-08-01T00:00:00+00:00",
                },
            )
            assert candidates_response.status_code == 200
            candidates = candidates_response.json()
            assert len(candidates) == 1
            assert candidates[0]["candidate_status"] == "billable"
            assert candidates[0]["vehicle_plate"] == vehicle.plate

            async with AsyncSessionLocal() as db:
                trip_row = await db.get(Trip, UUID(trip["id"]))
                assert trip_row is not None
                trip_row.total_transport_cost = Decimal("12400")
                trip_row.actual_revenue = Decimal("8800")
                trip_row.actual_margin = Decimal("-3600")
                trip_row.costs_reconciled_at = dt("2026-07-03T12:00:00")
                await db.commit()

            blocked_document_response = await client.post(
                "/api/v1/billing/documents",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "client_name": "Cliente API",
                    "contract_reference": reference,
                    "billing_period_start": "2026-07-01T00:00:00+00:00",
                    "billing_period_end": "2026-08-01T00:00:00+00:00",
                    "trip_ids": [trip["id"]],
                },
            )
            assert blocked_document_response.status_code == 409
            assert (
                blocked_document_response.json()["error"]["code"]
                == "negative_margin_requires_approval"
            )

            waiver_response = await client.post(
                "/api/v1/operations/waivers",
                headers={**headers, "Idempotency-Key": f"margin-approval:{trip['id']}"},
                json={
                    "entity_type": "trip",
                    "entity_id": trip["id"],
                    "waiver_type": "negative_margin_approved",
                    "risk_level": "high",
                    "reason": "Margem negativa aprovada pela gestão operacional.",
                },
            )
            assert waiver_response.status_code == 200
            assert waiver_response.json()["waiver_type"] == "negative_margin_approved"

            document_response = await client.post(
                "/api/v1/billing/documents",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "client_name": "Cliente API",
                    "contract_reference": reference,
                    "billing_period_start": "2026-07-01T00:00:00+00:00",
                    "billing_period_end": "2026-08-01T00:00:00+00:00",
                    "trip_ids": [trip["id"]],
                    "client_nuit": "400123456",
                },
            )
            assert document_response.status_code == 200
            document = document_response.json()
            assert document["status"] == "draft"
            assert document["items"][0]["status"] == "draft"

            documents_response = await client.get(
                "/api/v1/billing/documents",
                headers=headers,
                params={"period_start": "2026-07-01T00:00:00+00:00"},
            )
            assert documents_response.status_code == 200
            documents_body = documents_response.json()
            # list_documents now returns {items, total}
            documents = documents_body["items"]
            assert len(documents) == 1
            assert documents_body["total"] == 1
            assert documents[0]["id"] == document["id"]
            assert documents[0]["status"] == "draft"
            assert documents[0]["item_count"] == 1
            assert float(documents[0]["total_amount"]) == 8800

            draft_export_response = await client.get(
                f"/api/v1/billing/documents/{document['id']}/export",
                headers=headers,
            )
            assert draft_export_response.status_code == 409

            trip_after_draft = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-07-01T00:00:00+00:00",
                    "period_end": "2026-08-01T00:00:00+00:00",
                    "status": "billed",
                },
            )
            assert trip_after_draft.status_code == 200
            assert trip_after_draft.json() == []

            issued_response = await client.post(
                f"/api/v1/billing/documents/{document['id']}/issue",
                headers={**headers, "Idempotency-Key": "billing-issue:api-flow:001"},
                json={"issued_at": "2026-07-31T12:00:00+00:00"},
            )
            assert issued_response.status_code == 200
            issued = issued_response.json()
            assert issued["status"] == "issued"
            assert issued["items"][0]["status"] == "billed"
            issued_replay = await client.post(
                f"/api/v1/billing/documents/{document['id']}/issue",
                headers={**headers, "Idempotency-Key": "billing-issue:api-flow:001"},
                json={"issued_at": "2026-07-31T12:00:00+00:00"},
            )
            assert issued_replay.status_code == 200
            assert issued_replay.json()["id"] == issued["id"]

            export_response = await client.get(
                f"/api/v1/billing/documents/{document['id']}/export",
                headers=headers,
                params={"export_format": "pdf"},
            )
            assert export_response.status_code == 200
            export_payload = export_response.json()
            assert export_payload["status"] == "generated"
            assert export_payload["content_type"] == "application/pdf"
            assert export_payload["filename"].endswith(".pdf")
            assert export_payload["file_id"] is not None
            assert export_payload["size_bytes"] > 500
            export_replay_response = await client.get(
                f"/api/v1/billing/documents/{document['id']}/export",
                headers=headers,
                params={"export_format": "pdf"},
            )
            assert export_replay_response.status_code == 200
            assert export_replay_response.json()["file_id"] == export_payload["file_id"]

            download_response = await client.get(
                export_payload["download_url"],
                headers=headers,
            )
            assert download_response.status_code == 200
            assert download_response.content.startswith(b"%PDF")

            xlsx_response = await client.get(
                f"/api/v1/billing/documents/{document['id']}/export",
                headers=headers,
                params={"export_format": "xlsx"},
            )
            assert xlsx_response.status_code == 200
            xlsx_payload = xlsx_response.json()
            assert xlsx_payload["status"] == "generated"
            assert xlsx_payload["filename"].endswith(".xlsx")
            assert xlsx_payload["content_type"].endswith("spreadsheetml.sheet")

            xlsx_download_response = await client.get(
                xlsx_payload["download_url"],
                headers=headers,
            )
            assert xlsx_download_response.status_code == 200
            assert xlsx_download_response.content.startswith(b"PK")

            billed_trips_response = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-07-01T00:00:00+00:00",
                    "period_end": "2026-08-01T00:00:00+00:00",
                    "status": "billed",
                },
            )
            assert billed_trips_response.status_code == 200
            billed_trips = billed_trips_response.json()
            assert len(billed_trips) == 1
            assert billed_trips[0]["candidate_status"] == "billed"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_delivery_proof_dispute_blocks_validation_and_billing() -> None:
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

        async with await create_api_client() as client:
            headers = auth_headers(tenant.id)
            reference = f"CTR-DISP-{uuid4().hex[:8]}"
            contract_response = await client.post(
                "/api/v1/contracts/",
                headers=headers,
                json={
                    "client_name": "Cliente Disputa",
                    "contract_reference": reference,
                    "default_unit_price": 9200,
                },
            )
            assert contract_response.status_code == 200
            contract = contract_response.json()

            trip_response = await client.post(
                "/api/v1/trips",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "vehicle_id": str(vehicle.id),
                    "driver_id": str(driver.id),
                    "origin": "Maputo",
                    "destination": "Maxixe",
                    "cargo_type": "Carga contratual",
                    "load_state": "loaded_empty",
                },
            )
            assert trip_response.status_code == 200
            trip = trip_response.json()

            start_resp = await client.post(
                f"/api/v1/trips/{trip['id']}/start",
                headers=headers,
                json={"km_start": 200, "actual_departure": "2026-09-01T06:00:00+00:00"},
            )
            assert start_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/trips/{trip['id']}/complete",
                headers=headers,
                json={"km_end": 500, "actual_arrival": "2026-09-02T09:00:00+00:00"},
            )
            assert complete_resp.status_code == 200

            proof_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof",
                headers=headers,
                json={
                    "contract_id": contract["id"],
                    "document_number": "GD-DISPUTE-001",
                    "proof_type": "client_discharge_note",
                    "client_type": "company",
                    "delivered_at": "2026-09-02T10:30:00+00:00",
                    "quantity_delivered": 1,
                },
            )
            assert proof_response.status_code == 200
            proof = proof_response.json()

            dispute_payload = {
                "reason": "Quantidade descarregada nao confere com a guia do cliente.",
                "dispute_type": "quantity_mismatch",
                "notes": "Gestor precisa confirmar com o cliente antes de cobrar.",
            }
            dispute_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/dispute",
                headers={**headers, "Idempotency-Key": "delivery-proof:dispute:001"},
                json=dispute_payload,
            )
            assert dispute_response.status_code == 200
            disputed = dispute_response.json()
            assert disputed["status"] == "disputed"
            assert disputed["trip_billing_status"] == "delivery_disputed"

            dispute_replay = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/dispute",
                headers={**headers, "Idempotency-Key": "delivery-proof:dispute:001"},
                json=dispute_payload,
            )
            assert dispute_replay.status_code == 200
            assert dispute_replay.json()["id"] == disputed["id"]

            validation_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/validate",
                headers=headers,
                json={"validation_method": "manual_review"},
            )
            assert validation_response.status_code == 409
            assert validation_response.json()["error"]["code"] == "delivery_proof_disputed"

            candidates_response = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-09-01T00:00:00+00:00",
                    "period_end": "2026-10-01T00:00:00+00:00",
                    "status": "delivery_disputed",
                },
            )
            assert candidates_response.status_code == 200
            candidates = candidates_response.json()
            assert len(candidates) == 1
            assert candidates[0]["candidate_status"] == "delivery_disputed"

            resolve_response = await client.post(
                f"/api/v1/trips/{trip['id']}/delivery-proof/{proof['id']}/resolve-dispute",
                headers={**headers, "Idempotency-Key": "delivery-proof:resolve-dispute:001"},
                json={
                    "outcome": "validated",
                    "resolution_notes": "Cliente confirmou a quantidade correta.",
                    "validation_method": "client_confirmation",
                },
            )
            assert resolve_response.status_code == 200
            resolved = resolve_response.json()
            assert resolved["status"] == "validated"
            assert resolved["trip_billing_status"] == "billable"

            billable_response = await client.get(
                "/api/v1/billing/billable-trips",
                headers=headers,
                params={
                    "contract_reference": reference,
                    "period_start": "2026-09-01T00:00:00+00:00",
                    "period_end": "2026-10-01T00:00:00+00:00",
                    "status": "billable",
                },
            )
            assert billable_response.status_code == 200
            assert billable_response.json()[0]["candidate_status"] == "billable"

        async with AsyncSessionLocal() as db:
            exception = await db.scalar(
                select(OperationalException).where(
                    OperationalException.tenant_id == tenant.id,
                    OperationalException.entity_id == UUID(proof["id"]),
                    OperationalException.exception_type == "delivery_proof_disputed",
                )
            )
            assert exception is not None
            assert exception.status == "resolved"
            exception_context = exception.context
            assert exception_context is not None
            assert exception_context["trip_id"] == trip["id"]

            audit_rows = await db.execute(
                select(AuditLog.action).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.entity_id == UUID(proof["id"]),
                )
            )
            assert {
                "cargo.delivery_proof_created",
                "cargo.delivery_proof_disputed",
                "cargo.delivery_dispute_resolved",
                "operational_exception.created",
                "operational_exception.resolved",
            }.issubset(set(audit_rows.scalars()))
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_sm03_accept_delivery_proof_reaches_billing() -> None:
    """accept_delivery_proof (SM-03) must not dead-end at create_document."""
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

            contract = await contract_service.create_contract(
                db,
                tenant.id,
                ContractCreate(
                    client_name="Cliente SM03",
                    contract_reference=f"SM03-{uuid4().hex[:8]}",
                    default_unit_price=10000,
                ),
            )

            trip = await trips_service.create_trip(
                db,
                tenant.id,
                TripCreate(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    origin="Maputo",
                    destination="Beira",
                    cargo_type="Carga contratual",
                    load_state="loaded_empty",
                ),
            )
            trip = await trips_service.associate_contract(
                db,
                tenant.id,
                trip["id"],
                AssociateContractRequest(contract_id=contract["id"]),
            )

            await trips_service.start_trip(
                db,
                tenant.id,
                trip["id"],
                StartTripRequest(km_start=500, actual_departure=dt("2026-07-01T08:00:00")),
            )
            # complete_trip sets km_end — required by list_billable_trips guard
            await trips_service.complete_trip(
                db,
                tenant.id,
                trip["id"],
                CompleteTripRequest(km_end=1200, actual_arrival=dt("2026-07-03T18:00:00")),
            )

            proof_data = await cargo_service.create_delivery_proof(
                db,
                tenant.id,
                trip["id"],
                DeliveryProofCreate(
                    contract_id=contract["id"],
                    document_number=f"GD-SM03-{uuid4().hex[:6]}",
                    proof_type="client_discharge_note",
                    client_type="company",
                    delivered_at=dt("2026-07-03T15:00:00"),
                    quantity_delivered=1,
                ),
            )

            # Create a real user so the accepted_by FK constraint is satisfied
            manager_user = User(
                tenant_id=tenant.id,
                email=f"manager-sm03-{uuid4().hex[:6]}@test.com",
                password_hash="hashed",
                full_name="Gestor SM03",
                role="manager",
            )
            db.add(manager_user)
            await db.flush()

            # SM-03: accept (not validate) the proof
            from app.modules.cargo.service import accept_delivery_proof

            await accept_delivery_proof(
                db, proof_id=proof_data["id"], tenant_id=tenant.id, user_id=manager_user.id
            )
            await db.commit()

            # create_document must find the accepted proof — not raise delivery_proof_required
            billing_document = await billing_service.create_document(
                db,
                tenant.id,
                BillingDocumentCreate(
                    contract_id=contract["id"],
                    client_name="Cliente SM03",
                    contract_reference=contract["contract_reference"],
                    billing_period_start=dt("2026-07-01T00:00:00"),
                    billing_period_end=dt("2026-08-01T00:00:00"),
                    trip_ids=[trip["id"]],
                    client_nuit="400000001",
                ),
            )
            assert billing_document["status"] == "draft"
            assert len(billing_document["items"]) == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_list_billable_trips_excludes_trips_without_km_end() -> None:
    """Trips with billing_status='billable' but no km_end must not appear as candidates."""
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

            contract = await contract_service.create_contract(
                db,
                tenant.id,
                ContractCreate(
                    client_name="Cliente KmEnd",
                    contract_reference=f"KMEND-{uuid4().hex[:8]}",
                    default_unit_price=9000,
                ),
            )

            trip = await trips_service.create_trip(
                db,
                tenant.id,
                TripCreate(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    origin="Matola",
                    destination="Nacala",
                    cargo_type="Carga geral",
                    load_state="loaded_empty",
                ),
            )
            trip = await trips_service.associate_contract(
                db,
                tenant.id,
                trip["id"],
                AssociateContractRequest(contract_id=contract["id"]),
            )
            await trips_service.start_trip(
                db,
                tenant.id,
                trip["id"],
                StartTripRequest(km_start=0, actual_departure=dt("2026-08-01T07:00:00")),
            )

            proof_data = await cargo_service.create_delivery_proof(
                db,
                tenant.id,
                trip["id"],
                DeliveryProofCreate(
                    contract_id=contract["id"],
                    document_number=f"GD-KMEND-{uuid4().hex[:6]}",
                    proof_type="client_discharge_note",
                    client_type="company",
                    delivered_at=dt("2026-08-03T14:00:00"),
                    quantity_delivered=1,
                ),
            )
            # create_delivery_proof sets trip.status='delivered'; validate sets billing_status='billable'
            await cargo_service.validate_delivery_proof(
                db,
                tenant.id,
                trip["id"],
                proof_data["id"],
                None,
                ValidateDeliveryProofRequest(validation_method="manual_review"),
            )
            # billing_status is now 'billable' but km_end is None (complete_trip never called)
            from app.modules.trips.models import Trip as TripModel

            row = await db.get(TripModel, trip["id"])
            assert row is not None
            assert row.billing_status == "billable"
            assert row.km_end is None  # confirm pre-condition

            candidates = await billing_service.list_billable_trips(
                db,
                tenant.id,
                contract_reference=contract["contract_reference"],
                period_start=dt("2026-08-01T00:00:00"),
                period_end=dt("2026-09-01T00:00:00"),
            )
            assert candidates == [], "Trip without km_end must not appear as billing candidate"

            # Set km_end directly on the ORM row (complete_trip would reject non-in_progress status)
            row.km_end = 800
            await db.commit()

            candidates_after = await billing_service.list_billable_trips(
                db,
                tenant.id,
                contract_reference=contract["contract_reference"],
                period_start=dt("2026-08-01T00:00:00"),
                period_end=dt("2026-09-01T00:00:00"),
            )
            assert len(candidates_after) == 1
            assert candidates_after[0]["candidate_status"] == "billable"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_patch_trip_and_stop_produce_audit_logs() -> None:
    """patch_trip and patch_stop must each produce an AuditLog with old/new values."""
    try:
        async with AsyncSessionLocal() as db:
            tenant, vehicle, driver = await create_seed_entities(db)

            from app.modules.trips.models import TripStop as TripStopModel
            from app.modules.trips.schemas import TripPatch, TripStopPatch

            trip = await trips_service.create_trip(
                db,
                tenant.id,
                TripCreate(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    origin="Maputo",
                    destination="Tete",
                    cargo_type="Cimento",
                    load_state="loaded_empty",
                ),
            )

            await trips_service.patch_trip(
                db,
                tenant.id,
                trip["id"],
                TripPatch(destination="Chimoio"),
            )

            audit_trip = await db.scalar(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.action == "trip.patched",
                    AuditLog.entity_id == trip["id"],
                )
            )
            assert audit_trip is not None
            assert audit_trip.old_values is not None
            assert audit_trip.new_values is not None
            assert audit_trip.old_values["destination"] == "Tete"
            assert audit_trip.new_values["destination"] == "Chimoio"

            # Create a trip stop and patch it
            stop = TripStopModel(
                tenant_id=tenant.id,
                trip_id=trip["id"],
                stop_type="rest",
                location={"name": "Inchope"},
                stopped_at=dt("2026-06-15T10:00:00"),
            )
            db.add(stop)
            await db.commit()
            await db.refresh(stop)

            await trips_service.patch_stop(
                db,
                tenant.id,
                stop.id,
                TripStopPatch(location={"name": "Gorongosa"}),
            )

            audit_stop = await db.scalar(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.action == "trip_stop.patched",
                    AuditLog.entity_id == stop.id,
                )
            )
            assert audit_stop is not None
            assert audit_stop.old_values is not None
            assert audit_stop.new_values is not None
            assert audit_stop.old_values["location"] == {"name": "Inchope"}
            assert audit_stop.new_values["location"] == {"name": "Gorongosa"}
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
