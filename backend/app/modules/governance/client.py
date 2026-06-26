"""
Cliente HTTP do ROTAS para o Governance Engine.

Design:
- Opt-in: se GOVERNANCE_ENGINE_URL não estiver configurado, é no-op silencioso.
- Non-blocking: falhas do motor de governança nunca afectam operações ROTAS.
- Idempotente: idempotency_key derivada de IDs ROTAS — re-envios são seguros.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.governance_engine_url) and bool(s.governance_api_key)


async def push_governance_event(
    *,
    event_type: str,
    severity: str,
    title: str,
    description: str,
    occurred_at: datetime,
    entities: list[dict],
    idempotency_key: str,
    location_text: str | None = None,
) -> dict | None:
    """
    Envia um evento ao motor de governança (fire-and-forget).
    Devolve o response body ou None se o motor não estiver configurado / falhar.
    Nunca lança excepção.
    """
    if not _is_configured():
        return None

    s = get_settings()
    payload = {
        "event_type": event_type,
        "severity": severity,
        "title": title,
        "description": description,
        "occurred_at": occurred_at.isoformat(),
        "entities": entities,
        "idempotency_key": idempotency_key,
        "location_text": location_text,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            r = await http.post(
                f"{s.governance_engine_url}/api/v1/adapters/rotas/events",
                json=payload,
                headers={"X-API-Key": s.governance_api_key},
            )
            if r.status_code == 201:
                return r.json()
            # Idempotency replay — tratar como sucesso
            if r.status_code == 409:
                logger.debug("governance: idempotency replay %s", idempotency_key)
                return None
            logger.warning(
                "governance: unexpected status %d for key %s", r.status_code, idempotency_key
            )
    except httpx.TimeoutException:
        logger.warning("governance: timeout pushing event %s", idempotency_key)
    except Exception as exc:
        logger.error("governance: error pushing event %s: %s", idempotency_key, exc)

    return None


async def sync_entity(
    *,
    entity_type: str,
    external_id: str,
    display_name: str,
    attributes: dict,
) -> None:
    """Sincroniza uma entidade ROTAS no motor de governança (upsert)."""
    if not _is_configured():
        return

    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            await http.post(
                f"{s.governance_engine_url}/api/v1/adapters/rotas/entities/sync",
                json={
                    "entities": [
                        {
                            "entity_type": entity_type,
                            "external_id": external_id,
                            "display_name": display_name,
                            "attributes": attributes,
                        }
                    ]
                },
                headers={"X-API-Key": s.governance_api_key},
            )
    except Exception as exc:
        logger.error("governance: entity sync failed for %s/%s: %s", entity_type, external_id, exc)
