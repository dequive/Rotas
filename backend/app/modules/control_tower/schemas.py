"""Response contracts for the control tower aggregation (F7.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ControlTowerSummary(BaseModel):
    """KPI row rendered above the queues. Mirrors `service.get_control_tower`."""

    trip_orders_open: int
    dispatch_pending: int
    dispatch_blocked: int
    trips_in_execution: int
    incidents_open: int
    delivery_proofs_pending_validation: int
    billing_ready: int
    active_waivers: int
    operational_exceptions_open: int
    alerts_active: int
    work_orders_active: int
    spare_parts_low_stock: int
    tool_checkouts_overdue: int
    maintenance_overdue: int
    vehicles_active: int
    drivers_active: int
    trips_created_today: int
    vehicle_documents_expiring: int
    driver_documents_expiring: int
    # Financial block merged in from `_financial_summary`.
    costs_reconciled_trips: int
    transport_cost_total: float
    contract_revenue_total: float
    margin_total: float
    negative_margin_trips: int
    closed_trips_unreconciled: int


class ControlTowerQueues(BaseModel):
    """The 15 operational queues.

    Each queue is a heterogeneous row set built by its own aggregation helper —
    a dispatch clearance row and a spare-part row share no fields. They stay as
    open objects here rather than being flattened into a false common shape.
    """

    pending_dispatch: list[dict] = Field(default_factory=list)
    blocked_dispatch: list[dict] = Field(default_factory=list)
    open_incidents: list[dict] = Field(default_factory=list)
    delayed_trips: list[dict] = Field(default_factory=list)
    pending_delivery_validation: list[dict] = Field(default_factory=list)
    operational_exceptions: list[dict] = Field(default_factory=list)
    alerts: list[dict] = Field(default_factory=list)
    active_work_orders: list[dict] = Field(default_factory=list)
    negative_margin_trips: list[dict] = Field(default_factory=list)
    driver_despacho_pending: list[dict] = Field(default_factory=list)
    failed_checklists: list[dict] = Field(default_factory=list)
    disputed_delivery_proofs: list[dict] = Field(default_factory=list)
    operational_close_candidates: list[dict] = Field(default_factory=list)
    vehicle_documents_expiring: list[dict] = Field(default_factory=list)
    driver_documents_expiring: list[dict] = Field(default_factory=list)


class ControlTowerResponse(BaseModel):
    date: str
    summary: ControlTowerSummary
    queues: ControlTowerQueues
