"""Schemas for generic procurement document PDF generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(..., max_length=200)
    quantity: float
    unit: str = Field("unid.", max_length=20)
    unit_price: float | None = None


class EntityBlock(BaseModel):
    name: str = Field(..., max_length=200)
    contact: str | None = Field(None, max_length=300)
    nuit: str | None = Field(None, max_length=30)


class PurchaseOrderRequest(BaseModel):
    reference: str = Field(..., max_length=80)
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    entity: EntityBlock
    items: list[LineItem] = Field(..., min_length=1, max_length=100)
    notes: str | None = Field(None, max_length=1000)
    currency: str = Field("MZN", max_length=5)
    payment_terms: str | None = Field(None, max_length=100)
    delivery_deadline: str | None = Field(None, max_length=80)


class RequisitionRequest(BaseModel):
    type: str = Field("external", pattern="^(internal|external)$")
    reference: str = Field(..., max_length=80)
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    entity: EntityBlock
    requester_department: str | None = Field(None, max_length=100)
    items: list[LineItem] = Field(..., min_length=1, max_length=100)
    notes: str | None = Field(None, max_length=1000)
    currency: str = Field("MZN", max_length=5)
