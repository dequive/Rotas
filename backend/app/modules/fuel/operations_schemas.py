from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FuelTankCreate(BaseModel):
    code: str
    name: str
    fuel_type: str = "gasoleo"
    capacity_liters: float
    minimum_stock_liters: float = 0
    location: str | None = None


class FuelPurchaseCreate(BaseModel):
    supplier_name: str
    purchase_reference: str
    fuel_type: str = "gasoleo"
    ordered_liters: float
    unit_price: float
    ordered_at: datetime
    notes: str | None = None


class FuelReceiptCreate(BaseModel):
    purchase_id: UUID
    tank_id: UUID
    received_liters: float
    received_at: datetime
    delivery_note_number: str | None = None
    delivery_note_file_id: UUID | None = None
    notes: str | None = None


class VehicleRefuelCreate(BaseModel):
    tank_id: UUID
    vehicle_id: UUID
    driver_id: UUID
    trip_id: UUID | None = None
    liters: float
    odometer_reading: int
    refueled_at: datetime
    notes: str | None = None


class FuelStockCountCreate(BaseModel):
    tank_id: UUID
    measured_liters: float
    counted_at: datetime
    notes: str | None = None


class FuelStockAdjustmentApprove(BaseModel):
    notes: str | None = None
