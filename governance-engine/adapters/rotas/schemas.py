from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ROTAS severity → governance severity
ROTAS_TO_GOVERNANCE_SEVERITY: dict[str, str] = {
    "critical": "critica",
    "high": "alta",
    "medium": "media",
    "low": "baixa",
    # governance engine native values pass through
    "critica": "critica",
    "alta": "alta",
    "media": "media",
    "baixa": "baixa",
}

# ROTAS event type → governance taxonomy type code (must match bootstrap)
ROTAS_EVENT_TYPE_CODES: dict[str, str] = {
    "vehicle.breakdown":          "rotas.vehicle.breakdown",
    "vehicle.accident":           "rotas.vehicle.accident",
    "vehicle.overdue_checklist":  "rotas.vehicle.overdue_checklist",
    "trip.incident":              "rotas.trip.incident",
    "trip.route_deviation":       "rotas.trip.route_deviation",
    "trip.operational_exception": "rotas.trip.operational_exception",
    "fuel.anomaly":               "rotas.fuel.anomaly",
    "fuel.theft_suspicion":       "rotas.fuel.theft_suspicion",
    "cargo.damage":               "rotas.cargo.damage",
    "cargo.loss":                 "rotas.cargo.loss",
    "document.expired":           "rotas.document.expired",
    "driver.infraction":          "rotas.driver.infraction",
    "driver.absence":             "rotas.driver.absence",
}


class RotasEntityRecord(BaseModel):
    entity_type: str
    external_id: str
    display_name: str
    attributes: dict = Field(default_factory=dict)


class RotasEntitySyncRequest(BaseModel):
    entities: list[RotasEntityRecord]


class RotasEntitySyncResponse(BaseModel):
    synced: int
    entity_ids: list[UUID]


class RotasEventEntity(BaseModel):
    entity_type: str
    external_id: str
    role: str = "sujeito"
    display_name: str = ""
    snapshot: dict = Field(default_factory=dict)


class RotasEventPush(BaseModel):
    event_type: str
    severity: str
    title: str
    description: str | None = None
    occurred_at: datetime
    entities: list[RotasEventEntity] = Field(default_factory=list)
    idempotency_key: str
    location_text: str | None = None
    payload: dict = Field(default_factory=dict)


class RotasEventPushResponse(BaseModel):
    occurrence_id: UUID
    numero: str
    case_id: UUID | None = None
    case_reference: str | None = None


class RotasBootstrapRequest(BaseModel):
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
