from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contracts.models import Contract, ContractTariff
from app.modules.trips.models import KnownRoute, Trip


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


async def auto_calculate_revenue(db: AsyncSession, tenant_id: UUID, trip: Trip) -> Decimal:
    """Automated revenue calculation engine.
    
    Executes when a trip is reconciled.
    """
    if not trip.contract_id:
        return Decimal("0.00")

    # Load contract
    contract = await db.get(Contract, trip.contract_id)
    if not contract or contract.tenant_id != tenant_id:
        return Decimal("0.00")

    # 1. Find KnownRoute
    known_route = None
    if trip.origin and trip.destination:
        route_query = select(KnownRoute).where(
            KnownRoute.tenant_id == tenant_id,
            func.lower(func.trim(KnownRoute.origin)) == func.lower(func.trim(trip.origin)),
            func.lower(func.trim(KnownRoute.destination)) == func.lower(func.trim(trip.destination))
        )
        known_route = await db.scalar(route_query)

    # 2. Find ContractTariff
    tariff = None
    if known_route:
        tariff_query = select(ContractTariff).where(
            ContractTariff.tenant_id == tenant_id,
            ContractTariff.contract_id == trip.contract_id,
            ContractTariff.known_route_id == known_route.id
        )
        tariff = await db.scalar(tariff_query)

    # 3. Calculate revenue
    if tariff:
        rate_basis = (tariff.rate_basis or "trip").lower()
        unit_price = _decimal(tariff.unit_price)

        if rate_basis == "trip":
            return unit_price
        elif rate_basis == "ton":
            return _decimal(unit_price * _decimal(trip.cargo_weight))
        elif rate_basis == "volume":
            return _decimal(unit_price * _decimal(trip.cargo_volume))
        elif rate_basis == "km":
            km_diff = 0
            if trip.km_start is not None and trip.km_end is not None:
                km_diff = trip.km_end - trip.km_start
            
            if km_diff > 0:
                distance = Decimal(km_diff)
            else:
                distance = _decimal(known_route.distance_km)
            return _decimal(unit_price * distance)
        else:
            return unit_price
    else:
        # Fallback to contract default rate card
        rate_basis = (contract.billing_basis or "trip").lower()
        unit_price = _decimal(contract.default_unit_price)

        if rate_basis == "trip":
            return unit_price
        elif rate_basis == "ton":
            return _decimal(unit_price * _decimal(trip.cargo_weight))
        elif rate_basis == "volume":
            return _decimal(unit_price * _decimal(trip.cargo_volume))
        elif rate_basis == "km":
            km_diff = 0
            if trip.km_start is not None and trip.km_end is not None:
                km_diff = trip.km_end - trip.km_start
            distance = Decimal(km_diff) if km_diff > 0 else Decimal("0.00")
            return _decimal(unit_price * distance)
        else:
            return unit_price
