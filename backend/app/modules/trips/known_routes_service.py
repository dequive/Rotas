from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.trips.models import KnownRoute


def _serialize(route: KnownRoute) -> dict:
    return {
        "id": str(route.id),
        "tenant_id": str(route.tenant_id),
        "origin": route.origin,
        "destination": route.destination,
        "distance_km": float(route.distance_km),
        "avg_fuel_liters": float(route.avg_fuel_liters)
        if route.avg_fuel_liters is not None
        else None,
        "despacho_vazio": float(route.despacho_vazio) if route.despacho_vazio is not None else None,
        "despacho_carregado": float(route.despacho_carregado)
        if route.despacho_carregado is not None
        else None,
        "notes": route.notes,
        "is_active": route.is_active,
        "created_at": route.created_at.isoformat(),
        "updated_at": route.updated_at.isoformat(),
    }


async def list_known_routes(
    db: AsyncSession, tenant_id: UUID, *, active_only: bool = True
) -> list[dict]:
    q = select(KnownRoute).where(KnownRoute.tenant_id == tenant_id)
    if active_only:
        q = q.where(KnownRoute.is_active.is_(True))
    q = q.order_by(KnownRoute.origin, KnownRoute.destination)
    rows = list((await db.scalars(q)).all())
    return [_serialize(r) for r in rows]


async def create_known_route(db: AsyncSession, tenant_id: UUID, payload: dict) -> dict:
    existing = await db.scalar(
        select(KnownRoute).where(
            KnownRoute.tenant_id == tenant_id,
            KnownRoute.origin == payload["origin"].strip(),
            KnownRoute.destination == payload["destination"].strip(),
        )
    )
    if existing:
        raise ApiError(
            "route_already_exists",
            f"Rota {payload['origin']} → {payload['destination']} já existe.",
            status_code=409,
        )
    route = KnownRoute(
        tenant_id=tenant_id,
        origin=payload["origin"].strip(),
        destination=payload["destination"].strip(),
        distance_km=Decimal(str(payload["distance_km"])),
        avg_fuel_liters=Decimal(str(payload["avg_fuel_liters"]))
        if payload.get("avg_fuel_liters")
        else None,
        despacho_vazio=Decimal(str(payload["despacho_vazio"]))
        if payload.get("despacho_vazio")
        else None,
        despacho_carregado=Decimal(str(payload["despacho_carregado"]))
        if payload.get("despacho_carregado")
        else None,
        notes=payload.get("notes"),
        is_active=payload.get("is_active", True),
    )
    db.add(route)
    await db.flush()
    await db.commit()
    await db.refresh(route)
    return _serialize(route)


async def update_known_route(
    db: AsyncSession, tenant_id: UUID, route_id: UUID, payload: dict
) -> dict:
    route = await db.scalar(
        select(KnownRoute).where(KnownRoute.id == route_id, KnownRoute.tenant_id == tenant_id)
    )
    if not route:
        raise ApiError("route_not_found", "Rota não encontrada.", status_code=404)

    if "origin" in payload:
        route.origin = payload["origin"].strip()
    if "destination" in payload:
        route.destination = payload["destination"].strip()
    if "distance_km" in payload:
        route.distance_km = Decimal(str(payload["distance_km"]))
    if "avg_fuel_liters" in payload:
        v = payload["avg_fuel_liters"]
        route.avg_fuel_liters = Decimal(str(v)) if v is not None else None
    if "despacho_vazio" in payload:
        v = payload["despacho_vazio"]
        route.despacho_vazio = Decimal(str(v)) if v is not None else None
    if "despacho_carregado" in payload:
        v = payload["despacho_carregado"]
        route.despacho_carregado = Decimal(str(v)) if v is not None else None
    if "notes" in payload:
        route.notes = payload["notes"]
    if "is_active" in payload:
        route.is_active = payload["is_active"]

    await db.commit()
    await db.refresh(route)
    return _serialize(route)


async def delete_known_route(db: AsyncSession, tenant_id: UUID, route_id: UUID) -> dict:
    route = await db.scalar(
        select(KnownRoute).where(KnownRoute.id == route_id, KnownRoute.tenant_id == tenant_id)
    )
    if not route:
        raise ApiError("route_not_found", "Rota não encontrada.", status_code=404)
    await db.delete(route)
    await db.commit()
    return {"deleted": True}
