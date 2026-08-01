from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder
from app.modules.workshop.warranty_models import ServiceWarranty
from app.modules.workshop.warranty_schemas import WarrantyClaimRequest, WarrantyCreate


def serialize_warranty(warranty: ServiceWarranty) -> dict:
    return {
        "id": warranty.id,
        "tenant_id": warranty.tenant_id,
        "work_order_id": warranty.work_order_id,
        "vehicle_id": warranty.vehicle_id,
        "client_id": warranty.client_id,
        "warranty_type": warranty.warranty_type,
        "duration_months": warranty.duration_months,
        "duration_km": warranty.duration_km,
        "starts_at": warranty.starts_at,
        "expires_at": warranty.expires_at,
        "km_at_service": warranty.km_at_service,
        "status": warranty.status,
        "notes": warranty.notes,
        "created_at": warranty.created_at,
    }


async def create_warranty(
    db: AsyncSession,
    tenant_id: UUID,
    payload: WarrantyCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    wo = await db.get(WorkOrder, payload.work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work Order not found.", status_code=404)

    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    now = datetime.now(UTC)
    expires_at = now + timedelta(days=payload.duration_months * 30)

    warranty = ServiceWarranty(
        tenant_id=tenant_id,
        work_order_id=payload.work_order_id,
        vehicle_id=payload.vehicle_id,
        client_id=payload.client_id or getattr(vehicle, "customer_client_id", None),
        warranty_type=payload.warranty_type,
        duration_months=payload.duration_months,
        duration_km=payload.duration_km,
        starts_at=now,
        expires_at=expires_at,
        km_at_service=payload.km_at_service or vehicle.current_km,
        status="active",
        notes=payload.notes,
    )
    db.add(warranty)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="service_warranty.created",
        entity_type="service_warranty",
        entity_id=warranty.id,
        new_values={
            "warranty_type": warranty.warranty_type,
            "expires_at": warranty.expires_at.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(warranty)
    return serialize_warranty(warranty)


async def list_warranties(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    vehicle_id: UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(ServiceWarranty).where(ServiceWarranty.tenant_id == tenant_id)
    if vehicle_id:
        query = query.where(ServiceWarranty.vehicle_id == vehicle_id)
    if status_filter:
        query = query.where(ServiceWarranty.status == status_filter)

    res = await db.execute(
        query.order_by(ServiceWarranty.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_warranty(w) for w in res.scalars().all()]


async def claim_warranty(
    db: AsyncSession,
    tenant_id: UUID,
    warranty_id: UUID,
    payload: WarrantyClaimRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    warranty = await db.get(ServiceWarranty, warranty_id)
    if not warranty or warranty.tenant_id != tenant_id:
        raise ApiError("warranty_not_found", "Warranty not found.", status_code=404)

    if warranty.status != "active":
        raise ApiError(
            "warranty_not_active", f"Warranty is in status '{warranty.status}'.", status_code=409
        )

    now = datetime.now(UTC)
    if warranty.expires_at and now > warranty.expires_at:
        warranty.status = "expired"
        await db.commit()
        raise ApiError(
            "warranty_expired", "Warranty duration by time has expired.", status_code=409
        )

    if warranty.duration_km and warranty.km_at_service:
        km_elapsed = payload.current_km - warranty.km_at_service
        if km_elapsed > warranty.duration_km:
            warranty.status = "expired"
            await db.commit()
            raise ApiError(
                "warranty_km_exceeded",
                f"Warranty km limit exceeded by {km_elapsed - warranty.duration_km} km.",
                status_code=409,
            )

    warranty.status = "claimed"
    warranty.notes = f"{warranty.notes or ''}\nAcionamento garantia: {payload.claim_reason}".strip()
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="service_warranty.claimed",
        entity_type="service_warranty",
        entity_id=warranty.id,
        new_values={"status": "claimed", "claim_reason": payload.claim_reason},
    )
    await db.commit()
    await db.refresh(warranty)
    return serialize_warranty(warranty)
