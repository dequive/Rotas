import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.core.errors import ApiError
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.reception_schemas import ReceptionCreate, VehicleReleaseCreate
from app.modules.workshop.reception_service import (
    create_reception,
    get_vehicle_intervention_history,
    release_vehicle,
)


@pytest.mark.asyncio
async def test_empty_vehicle_intervention_history(db, tenant_id):
    """Teste #1: Viatura recém-criada sem histórico devolve HTTP 200 com listas vazias."""
    vehicle = Vehicle(tenant_id=tenant_id, plate="NEW-001", current_km=1500)
    db.add(vehicle)
    await db.flush()

    history = await get_vehicle_intervention_history(db, tenant_id, vehicle.id)

    assert history["vehicle_id"] == vehicle.id
    assert history["plate"] == "NEW-001"
    assert history["current_odometer_km"] == 1500
    assert history["receptions"] == []
    assert history["work_orders"] == []
    assert history["parts_used"] == []
    assert history["warranties"] == []


@pytest.mark.asyncio
async def test_reception_contact_fields_and_individual_client_type(db, tenant_id, test_user):
    """Teste #2: Criação de recepção com campos de contacto e cliente default individual."""
    client = Client(tenant_id=tenant_id, trading_name="João Muchanga", nuit="123456789", client_type="individual")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="CUST-888", ownership_type="customer", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    payload = ReceptionCreate(
        vehicle_id=vehicle.id,
        client_id=client.id,
        odometer_at_reception=25000,
        delivered_by_name="Carlos Muchanga (Irmão)",
        delivered_by_phone="+258840001122",
        pickup_authorized_by_name="João Muchanga",
        pickup_authorized_by_phone="+258849990000",
    )

    reception = await create_reception(db, tenant_id, payload, actor_id=test_user.id)

    assert reception["delivered_by_name"] == "Carlos Muchanga (Irmão)"
    assert reception["pickup_authorized_by_name"] == "João Muchanga"
    assert reception["status"] == "received"


@pytest.mark.asyncio
async def test_unauthorized_pickup_person_raises_409(db, tenant_id, test_user):
    """Teste #3: Levantamento por pessoa não autorizada dispara HTTP 409 unauthorized_pickup_person."""
    vehicle = Vehicle(tenant_id=tenant_id, plate="SEC-999")
    db.add(vehicle)
    await db.flush()

    rec_payload = ReceptionCreate(
        vehicle_id=vehicle.id,
        pickup_authorized_by_name="Dra. Maria Santos",
    )
    reception = await create_reception(db, tenant_id, rec_payload, actor_id=test_user.id)

    # Tentativa de levantamento por pessoa com nome diferente sem override
    release_payload = VehicleReleaseCreate(
        odometer_at_release=25100,
        picked_up_by_name="Pedro Sitoe",
        override_unauthorized_pickup=False,
    )

    with pytest.raises(ApiError) as exc_info:
        await release_vehicle(db, tenant_id, reception["id"], release_payload, actor_id=test_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "unauthorized_pickup_person"


@pytest.mark.asyncio
async def test_authorized_release_with_override_and_reason(db, tenant_id, test_user):
    """Teste #4: Levantamento com override de autorização de emergência grava o motivo e fecha a recepção."""
    vehicle = Vehicle(tenant_id=tenant_id, plate="OVR-777")
    db.add(vehicle)
    await db.flush()

    rec_payload = ReceptionCreate(
        vehicle_id=vehicle.id,
        pickup_authorized_by_name="Empresa TransLog Lda",
    )
    reception = await create_reception(db, tenant_id, rec_payload, actor_id=test_user.id)

    # Override válido de autorização
    release_payload = VehicleReleaseCreate(
        odometer_at_release=25200,
        picked_up_by_name="Fernando Motorista",
        override_unauthorized_pickup=True,
        override_reason="Autorização telefónica confirmada pelo Diretor de Operações às 14:30.",
    )

    release = await release_vehicle(db, tenant_id, reception["id"], release_payload, actor_id=test_user.id)

    assert release["picked_up_by_name"] == "Fernando Motorista"
    assert release["override_unauthorized_pickup"] is True
    assert release["override_reason"] == "Autorização telefónica confirmada pelo Diretor de Operações às 14:30."


@pytest.mark.asyncio
async def test_vehicle_intervention_history_populated_data(db, tenant_id, test_user):
    """Teste #5: Histórico populado com recepções, OS concluída, peças montadas e garantias ativas."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from app.modules.workshop.models import MaintenancePartUsed, SparePartInventory, WorkOrder
    from app.modules.workshop.warranty_models import ServiceWarranty

    vehicle = Vehicle(tenant_id=tenant_id, plate="POP-100", current_km=48500)
    db.add(vehicle)
    await db.flush()

    # 1. Recepção
    rec_payload = ReceptionCreate(
        vehicle_id=vehicle.id,
        odometer_at_reception=45000,
        reported_issues="Mudança de óleo e pastilhas",
    )
    await create_reception(db, tenant_id, rec_payload, actor_id=test_user.id)

    # 2. Ordem de Serviço Concluída
    wo = WorkOrder(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        work_order_number="OS-2026-0099",
        planned_work="Mudança de óleo",
        status="closed",
    )
    db.add(wo)
    await db.flush()

    # 3. Peça em Inventário & Utilização
    inv = SparePartInventory(
        tenant_id=tenant_id,
        sku="FIL-001",
        name="Filtro de Óleo",
        current_quantity=Decimal("10.000"),
        average_unit_cost=Decimal("1500.00"),
    )
    db.add(inv)
    await db.flush()

    part = MaintenancePartUsed(
        tenant_id=tenant_id,
        work_order_id=wo.id,
        inventory_id=inv.id,
        request_reference="REQ-123",
        quantity=1,
        unit_cost=Decimal("1500.00"),
    )
    db.add(part)

    # 4. Garantia Emitida
    warranty = ServiceWarranty(
        tenant_id=tenant_id,
        work_order_id=wo.id,
        vehicle_id=vehicle.id,
        warranty_type="parts",
        duration_months=6,
        expires_at=datetime.now(UTC) + timedelta(days=180),
        status="active",
        notes="Garantia de peças 6 meses",
    )
    db.add(warranty)
    await db.flush()

    history = await get_vehicle_intervention_history(db, tenant_id, vehicle.id)

    assert history["vehicle_id"] == vehicle.id
    assert history["plate"] == "POP-100"
    assert history["current_odometer_km"] == 48500
    assert len(history["receptions"]) == 1
    assert len(history["work_orders"]) == 1
    assert len(history["parts_used"]) == 1
    assert len(history["warranties"]) == 1

    assert history["receptions"][0]["reported_issues"] == "Mudança de óleo e pastilhas"
    assert history["work_orders"][0]["status"] == "closed"
    assert history["warranties"][0]["warranty_type"] == "parts"
    assert history["warranties"][0]["status"] == "active"

