import uuid
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contracts.models import Contract, ContractTariff
from app.modules.trips.models import Trip, KnownRoute
from app.modules.vehicles.models import Vehicle
from app.modules.drivers.models import Driver
from app.modules.trips.revenue import auto_calculate_revenue
from app.modules.trips.costs import reconcile_trip_costs


@pytest.fixture
async def sample_entities(db, tenant_id):
    suffix = uuid.uuid4().hex[:6]
    contract = Contract(
        tenant_id=tenant_id,
        client_name="Client Corp",
        contract_reference=f"CTR-{suffix}",
        status="active",
        billing_basis="trip",
        default_unit_price=Decimal("150.00"),
    )
    db.add(contract)

    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{suffix.upper()}",
        status="active",
    )
    db.add(vehicle)

    driver = Driver(
        tenant_id=tenant_id,
        full_name="John Doe",
        status="active",
    )
    db.add(driver)

    route = KnownRoute(
        tenant_id=tenant_id,
        origin="Maputo",
        destination="Inhambane",
        distance_km=Decimal("480.0"),
        is_active=True,
    )
    db.add(route)

    await db.commit()
    await db.refresh(contract)
    await db.refresh(vehicle)
    await db.refresh(driver)
    await db.refresh(route)

    return {
        "contract": contract,
        "vehicle": vehicle,
        "driver": driver,
        "route": route,
    }


@pytest.mark.asyncio
async def test_revenue_by_trip_tariff(db, tenant_id, sample_entities):
    entities = sample_entities
    # Create a contract tariff for "trip"
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="trip",
        unit_price=Decimal("5000.00"),
        currency="MZN",
    )
    db.add(tariff)

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("5000.00")


@pytest.mark.asyncio
async def test_revenue_by_ton_tariff(db, tenant_id, sample_entities):
    entities = sample_entities
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="ton",
        unit_price=Decimal("150.00"),
        currency="MZN",
    )
    db.add(tariff)

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin=" Maputo ",  # leading/trailing spaces to test strip
        destination="inhambane",  # casing to test case-insensitive
        cargo_weight=Decimal("12.5"),
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("150.00") * Decimal("12.5")


@pytest.mark.asyncio
async def test_revenue_by_volume_tariff(db, tenant_id, sample_entities):
    entities = sample_entities
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="volume",
        unit_price=Decimal("200.00"),
        currency="MZN",
    )
    db.add(tariff)

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        cargo_volume=Decimal("8.2"),
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("200.00") * Decimal("8.2")


@pytest.mark.asyncio
async def test_revenue_by_km_tariff_fallback_route_distance(db, tenant_id, sample_entities):
    entities = sample_entities
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="km",
        unit_price=Decimal("10.00"),
        currency="MZN",
    )
    db.add(tariff)

    # Trip doesn't have km_start/km_end recorded -> fallback to route.distance_km (480.0)
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("10.00") * Decimal("480.0")


@pytest.mark.asyncio
async def test_revenue_by_km_tariff_using_trip_kms(db, tenant_id, sample_entities):
    entities = sample_entities
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="km",
        unit_price=Decimal("10.00"),
        currency="MZN",
    )
    db.add(tariff)

    # Trip has km_start/km_end recorded (500 km difference)
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        km_start=1000,
        km_end=1500,
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("10.00") * Decimal("500")


@pytest.mark.asyncio
async def test_revenue_fallback_to_contract_default(db, tenant_id, sample_entities):
    entities = sample_entities
    # No tariff defined. Contract default billing_basis = "trip", default_unit_price = 150.00.
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        status="planned",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    rev = await auto_calculate_revenue(db, tenant_id, trip)
    assert rev == Decimal("150.00")


@pytest.mark.asyncio
async def test_reconcile_trip_costs_calculates_actual_revenue_and_margin(db, tenant_id, sample_entities):
    entities = sample_entities
    # Reconciled trip: actual_revenue and actual_margin are recalculated automatically
    tariff = ContractTariff(
        tenant_id=tenant_id,
        contract_id=entities["contract"].id,
        known_route_id=entities["route"].id,
        rate_basis="trip",
        unit_price=Decimal("1000.00"),
    )
    db.add(tariff)

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=entities["vehicle"].id,
        driver_id=entities["driver"].id,
        contract_id=entities["contract"].id,
        origin="Maputo",
        destination="Inhambane",
        total_fuel_cost=Decimal("200.00"),
        status="closed",
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    # Reconcile costs
    updated_trip = await reconcile_trip_costs(db, tenant_id, trip)
    assert updated_trip.actual_revenue == Decimal("1000.00")
    assert updated_trip.total_transport_cost == Decimal("200.00")
    assert updated_trip.actual_margin == Decimal("800.00")
