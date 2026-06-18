from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal, import_all_models
from app.modules.billing import service as billing_service
from app.modules.billing.models import BillingDocument
from app.modules.billing.schemas import BillingDocumentCreate, IssueBillingDocumentRequest
from app.modules.cargo import service as cargo_service
from app.modules.cargo.models import DeliveryProof
from app.modules.cargo.schemas import (
    CargoManifestCreate,
    DeliveryProofCreate,
    LoadPermitCreate,
    TransportDocumentCreate,
    ValidateDeliveryProofRequest,
)
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips import service as trip_service
from app.modules.trips.models import Trip
from app.modules.trips.schemas import StartTripRequest, TripCostCreate, TripCreate
from app.modules.vehicles.models import Vehicle
from scripts.seed_pilot import CONTRACT_REFERENCE, DRIVER_PHONE, TENANT_SLUG, VEHICLE_PLATE, seed

LOAD_PERMIT_NUMBER = "LP-DEMO-001"
MANIFEST_NUMBER = "MC-DEMO-001"
TRANSPORT_GUIDE_NUMBER = "GT-DEMO-001"
DISCHARGE_DOCUMENT_NUMBER = "GD-DEMO-001"


def as_id(value: Any) -> str | None:
    return str(value) if value is not None else None


async def load_seed_entities():
    await seed()

    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        if tenant is None:
            raise RuntimeError("Pilot tenant was not created.")

        vehicle = await db.scalar(
            select(Vehicle).where(
                Vehicle.tenant_id == tenant.id,
                Vehicle.plate == VEHICLE_PLATE,
            )
        )
        driver = await db.scalar(
            select(Driver).where(
                Driver.tenant_id == tenant.id,
                Driver.phone == DRIVER_PHONE,
            )
        )
        contract = await db.scalar(
            select(Contract).where(
                Contract.tenant_id == tenant.id,
                Contract.contract_reference == CONTRACT_REFERENCE,
            )
        )
        if vehicle is None or driver is None or contract is None:
            raise RuntimeError("Pilot vehicle, driver or contract is missing.")

        return tenant.id, vehicle.id, driver.id, contract.id


async def find_existing_demo_trip(db, tenant_id):
    proof = await db.scalar(
        select(DeliveryProof).where(
            DeliveryProof.tenant_id == tenant_id,
            DeliveryProof.document_number == DISCHARGE_DOCUMENT_NUMBER,
        )
    )
    if proof is None:
        return None
    return await db.get(Trip, proof.trip_id)


async def ensure_trip(db, tenant_id, vehicle_id, driver_id, contract_id):
    existing_trip = await find_existing_demo_trip(db, tenant_id)
    if existing_trip is not None:
        return existing_trip

    trip = await trip_service.create_trip(
        db,
        tenant_id,
        TripCreate(
            contract_id=contract_id,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            origin="Maputo",
            destination="Beira",
            cargo_type="Produtos manufaturados",
            cargo_class="manufactured_goods",
            load_state="loaded_empty",
            requires_load_permit=True,
            requires_cargo_manifest=True,
            planned_departure=datetime(2026, 6, 10, 7, 30, tzinfo=UTC),
            planned_arrival=datetime(2026, 6, 11, 18, 0, tzinfo=UTC),
        ),
    )
    trip_id = trip["id"]

    await cargo_service.create_load_permit(
        db,
        tenant_id,
        trip_id,
        LoadPermitCreate(
            contract_id=contract_id,
            client_name="Cliente Industrial Piloto",
            permit_number=LOAD_PERMIT_NUMBER,
            issuer_name="Cliente Industrial Piloto",
            district="Beira",
            origin="Maputo",
            destination="Beira",
            valid_from=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
            valid_until=datetime(2026, 6, 12, 23, 59, tzinfo=UTC),
            leg_type="outbound",
            load_state="loaded",
            notes="Autorizacao de carregamento emitida pelo cliente para demo.",
        ),
    )
    await cargo_service.create_cargo_manifest(
        db,
        tenant_id,
        trip_id,
        CargoManifestCreate(
            contract_id=contract_id,
            manifest_number=MANIFEST_NUMBER,
            client_name="Cliente Industrial Piloto",
            shipper_name="Cliente Industrial Piloto",
            recipient_name="Armazem Beira",
            cargo_description="Produtos manufaturados diversos",
            cargo_type="Produtos manufaturados",
            cargo_class="manufactured_goods",
            package_count=24,
            gross_weight=12000,
            origin="Maputo",
            destination="Beira",
            issued_at=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
        ),
    )
    await cargo_service.create_transport_document(
        db,
        tenant_id,
        trip_id,
        TransportDocumentCreate(
            contract_id=contract_id,
            document_type="transport_guide",
            document_number=TRANSPORT_GUIDE_NUMBER,
            issuer="Cliente Industrial Piloto",
            client_name="Cliente Industrial Piloto",
            issued_at=datetime(2026, 6, 10, 8, 15, tzinfo=UTC),
            origin="Maputo",
            destination="Beira",
            district="Beira",
            notes="Guia de transporte associada ao Load Permit demo.",
        ),
    )
    await trip_service.start_trip(
        db,
        tenant_id,
        trip_id,
        StartTripRequest(
            km_start=125000,
            actual_departure=datetime(2026, 6, 10, 8, 30, tzinfo=UTC),
        ),
    )
    await trip_service.create_cost(
        db,
        tenant_id,
        trip_id,
        TripCostCreate(
            cost_type="portagem",
            description="Portagem e taxas de rota demo",
            amount=750,
            currency="MZN",
            paid_by="company",
            payment_method="cash",
            request_reference="demo:trip-cost:portagem",
            incurred_at=datetime(2026, 6, 10, 13, 0, tzinfo=UTC),
        ),
    )
    proof = await cargo_service.create_delivery_proof(
        db,
        tenant_id,
        trip_id,
        DeliveryProofCreate(
            contract_id=contract_id,
            load_permit_number=LOAD_PERMIT_NUMBER,
            document_number=DISCHARGE_DOCUMENT_NUMBER,
            proof_type="client_discharge_note",
            client_type="company",
            receiver_name="Supervisor Armazem Beira",
            receiver_contact="258840000003",
            delivery_location="Beira",
            delivered_at=datetime(2026, 6, 11, 16, 45, tzinfo=UTC),
            cargo_condition="intact",
            quantity_delivered=24,
            notes="Guia de descarga carimbada pelo cliente.",
        ),
    )
    await cargo_service.validate_delivery_proof(
        db,
        tenant_id,
        trip_id,
        proof["id"],
        None,
        ValidateDeliveryProofRequest(
            validation_method="manual_review",
            notes="Validado para demo piloto.",
        ),
    )
    return await db.get(Trip, trip_id)


async def ensure_billing_document(db, tenant_id, contract_id, trip):
    if trip.billing_document_id:
        document = await db.get(BillingDocument, trip.billing_document_id)
        if document is not None:
            if document.status == "draft":
                return await billing_service.issue_document(
                    db,
                    tenant_id,
                    document.id,
                    IssueBillingDocumentRequest(
                        issued_at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
                    ),
                )
            return await billing_service.get_document(db, tenant_id, document.id)

    if trip.billing_status != "billable":
        raise RuntimeError(f"Demo trip is not billable: {trip.billing_status}")

    document = await billing_service.create_document(
        db,
        tenant_id,
        BillingDocumentCreate(
            contract_id=contract_id,
            client_name="Cliente Industrial Piloto",
            contract_reference=CONTRACT_REFERENCE,
            billing_period_start=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            billing_period_end=datetime(2026, 7, 1, 0, 0, tzinfo=UTC),
            trip_ids=[trip.id],
        ),
    )
    return await billing_service.issue_document(
        db,
        tenant_id,
        document["id"],
        IssueBillingDocumentRequest(
            issued_at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
        ),
    )


async def demo() -> dict[str, Any]:
    import_all_models()
    tenant_id, vehicle_id, driver_id, contract_id = await load_seed_entities()

    async with AsyncSessionLocal() as db:
        trip = await ensure_trip(db, tenant_id, vehicle_id, driver_id, contract_id)
        if trip is None:
            raise RuntimeError("Demo trip was not created.")

        document = await ensure_billing_document(db, tenant_id, contract_id, trip)
        trip = await db.get(Trip, trip.id)

        return {
            "tenant_id": as_id(tenant_id),
            "vehicle_id": as_id(vehicle_id),
            "driver_id": as_id(driver_id),
            "contract_id": as_id(contract_id),
            "trip": {
                "id": as_id(trip.id if trip else None),
                "status": trip.status if trip else None,
                "billing_status": trip.billing_status if trip else None,
            },
            "billing_document": {
                "id": as_id(document["id"]),
                "status": document["status"],
                "total_amount": str(document["total_amount"]),
                "items": len(document["items"]),
            },
            "load_permit_number": LOAD_PERMIT_NUMBER,
            "manifest_number": MANIFEST_NUMBER,
            "discharge_document_number": DISCHARGE_DOCUMENT_NUMBER,
        }


async def main() -> None:
    result = await demo()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
