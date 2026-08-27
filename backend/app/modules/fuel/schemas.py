from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FuelLogCreate(BaseModel):
    trip_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID
    fuel_date: datetime
    station_name: str | None = None
    station_location: dict | None = None
    fuel_type: str = "gasoleo"
    liters: float
    price_per_liter: float | None = None
    total_cost: float
    km_at_refuel: int
    receipt_file_id: UUID | None = None
    odometer_file_id: UUID | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    client_captured_at: datetime | None = None


class VerifyFuelLogRequest(BaseModel):
    is_verified: bool = True
    flagged: bool | None = None
