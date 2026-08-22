from datetime import datetime
from decimal import Decimal
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


# ── Response contracts (F7.2) ─────────────────────────────────────────────────


class FuelTankRead(BaseModel):
    """Mirrors `operations.serialize_tank`."""

    id: UUID
    tenant_id: UUID
    code: str
    name: str
    fuel_type: str
    capacity_liters: Decimal
    minimum_stock_liters: Decimal
    current_stock_liters: Decimal
    average_unit_cost: Decimal | None = None
    location: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class FuelPurchaseRead(BaseModel):
    """Mirrors `operations.serialize_purchase`."""

    id: UUID
    tenant_id: UUID
    supplier_name: str | None = None
    supplier_third_party_id: UUID | None = None
    purchase_reference: str | None = None
    fuel_type: str
    ordered_liters: Decimal
    unit_price: Decimal
    total_cost: Decimal
    status: str
    ordered_at: datetime | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    notes: str | None = None
    created_at: datetime


class FuelBoardSummary(BaseModel):
    tanks: int
    purchases_pending: int
    low_stock_tanks: int
    stock_adjustments_pending: int
    total_stock_liters: Decimal


class FuelBoardQueues(BaseModel):
    low_stock_tanks: list[FuelTankRead]


class FuelControlBoardResponse(BaseModel):
    summary: FuelBoardSummary
    tanks: list[FuelTankRead]
    queues: FuelBoardQueues
