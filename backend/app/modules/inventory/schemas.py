from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# Warehouses
# ---------------------------------------------------------
class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    is_active: bool = True

class WarehouseResponse(WarehouseCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Item Categories
# ---------------------------------------------------------
class ItemCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class ItemCategoryResponse(ItemCategoryCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Items
# ---------------------------------------------------------
class ItemCreate(BaseModel):
    category_id: UUID | None = None
    sku: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    unit_of_measure: str = Field(default="UN", max_length=20)

class ItemResponse(ItemCreate):
    id: UUID
    tenant_id: UUID
    current_stock: Decimal
    average_unit_cost: Decimal
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Stock Movements
# ---------------------------------------------------------
class StockMovementIn(BaseModel):
    """Payload for registering incoming stock (Purchases)"""
    item_id: UUID
    warehouse_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, description="Cost per unit of the newly received stock")
    reference_doc: str | None = None
    notes: str | None = None


class StockMovementOut(BaseModel):
    """Payload for registering outgoing stock (Consumption/Workshop)"""
    item_id: UUID
    warehouse_id: UUID
    quantity: Decimal = Field(gt=0)
    reference_doc: str | None = None
    notes: str | None = None


class StockMovementResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    item_id: UUID
    warehouse_id: UUID
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal
    total_value: Decimal
    reference_doc: str | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
