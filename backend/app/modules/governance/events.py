"""
Builders de eventos: traduzem objectos de domínio ROTAS em payloads
prontos para push_governance_event().
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

# Mapeamento ROTAS severity → governance severity
_SEVERITY_MAP = {
    "critical": "critica",
    "high": "alta",
    "medium": "media",
    "low": "baixa",
}

# Mapeamento exception_type ROTAS → event_type do adapter
_TYPE_MAP = {
    "vehicle_breakdown": "vehicle.breakdown",
    "trip_incident": "trip.incident",
    "fuel_anomaly": "fuel.anomaly",
    "cargo_damage": "cargo.damage",
    "document_expired": "document.expired",
    "driver_infraction": "driver.infraction",
    "route_deviation": "trip.route_deviation",
    "overdue_checklist": "vehicle.overdue_checklist",
}


def operational_exception_event(
    *,
    exception_id: UUID,
    exception_type: str,
    severity: str,
    title: str,
    message: str,
    entity_type: str,
    entity_id: UUID,
    entity_display_name: str,
    entity_attributes: dict,
    tenant_id: UUID,
) -> dict:
    """Constrói o payload de evento a partir de um OperationalException ROTAS."""
    return {
        "event_type": _TYPE_MAP.get(exception_type, "trip.operational_exception"),
        "severity": _SEVERITY_MAP.get(severity, "baixa"),
        "title": title,
        "description": message,
        "occurred_at": datetime.now(UTC),
        "entities": [
            {
                "entity_type": entity_type,
                "external_id": str(entity_id),
                "role": "sujeito",
                "display_name": entity_display_name,
                "snapshot": entity_attributes,
            }
        ],
        # Idempotency key inclui exception_id para que o mesmo exception nunca crie
        # dois eventos no motor mesmo que ensure_exception seja chamado duas vezes
        # por código não-idempotente.
        "idempotency_key": f"rotas:exception:{exception_id}:{tenant_id}",
    }
