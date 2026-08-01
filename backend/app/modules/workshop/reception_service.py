import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.files.models import File
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import MaintenancePartUsed, WorkOrder
from app.modules.workshop.reception_models import (
    ReceptionPhoto,
    VehicleReception,
    VehicleRelease,
)
from app.modules.workshop.reception_schemas import (
    ReceptionCreate,
    ReceptionPhotoCreate,
    VehicleReleaseCreate,
)
from app.modules.workshop.warranty_models import ServiceWarranty


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", "", no_accents.lower()).strip()
    return cleaned


def _names_match(authorized: str | None, presented: str | None) -> bool:
    norm_auth = _normalize_name(authorized)
    norm_pres = _normalize_name(presented)
    if not norm_auth or not norm_pres:
        return True  # Sem autorização restritiva gravada, não bloqueia
    if norm_auth == norm_pres:
        return True
    auth_tokens = set(norm_auth.split())
    pres_tokens = set(norm_pres.split())
    common = auth_tokens.intersection(pres_tokens)
    if len(common) >= 2 or (len(common) == 1 and (len(auth_tokens) == 1 or len(pres_tokens) == 1)):
        return True
    return False


async def get_next_tenant_sequence(db: AsyncSession, tenant_id: UUID, entity_type: str) -> int:
    """Atomic lightweight sequence generation per tenant without fiscal counter locks.
    Usa INSERT ... ON CONFLICT DO NOTHING + UPDATE ... RETURNING.
    """
    current_year = datetime.now(UTC).year
    key = f"{entity_type}_{current_year}"

    # Ensure sequence row exists for (tenant_id, key)
    insert_stmt = text(
        """
        INSERT INTO tenant_sequences (id, tenant_id, entity_type, current_value, updated_at)
        VALUES (gen_random_uuid(), :tenant_id, :entity_type, 0, NOW())
        ON CONFLICT (tenant_id, entity_type) DO NOTHING
        """
    )
    await db.execute(insert_stmt, {"tenant_id": tenant_id, "entity_type": key})

    # Atomic update returning current_value
    update_stmt = text(
        """
        UPDATE tenant_sequences
        SET current_value = current_value + 1, updated_at = NOW()
        WHERE tenant_id = :tenant_id AND entity_type = :entity_type
        RETURNING current_value
        """
    )
    res = await db.execute(update_stmt, {"tenant_id": tenant_id, "entity_type": key})
    seq_val = res.scalar_one()
    return seq_val


def serialize_reception(reception: VehicleReception, photos: list[dict] | None = None) -> dict:
    return {
        "id": reception.id,
        "tenant_id": reception.tenant_id,
        "vehicle_id": reception.vehicle_id,
        "client_id": reception.client_id,
        "reception_number": reception.reception_number,
        "received_by": reception.received_by,
        "received_at": reception.received_at,
        "odometer_at_reception": reception.odometer_at_reception,
        "reported_issues": reception.reported_issues,
        "visual_condition": reception.visual_condition,
        "personal_items": reception.personal_items,
        "fuel_level": reception.fuel_level,
        "delivered_by_name": reception.delivered_by_name,
        "delivered_by_phone": reception.delivered_by_phone,
        "pickup_authorized_by_name": reception.pickup_authorized_by_name,
        "pickup_authorized_by_phone": reception.pickup_authorized_by_phone,
        "client_signature_file_id": reception.client_signature_file_id,
        "estimated_completion_at": reception.estimated_completion_at,
        "status": reception.status,
        "photos": photos or [],
        "created_at": reception.created_at,
        "updated_at": reception.updated_at,
    }


def serialize_photo(photo: ReceptionPhoto) -> dict:
    return {
        "id": photo.id,
        "tenant_id": photo.tenant_id,
        "reception_id": photo.reception_id,
        "file_id": photo.file_id,
        "caption": photo.caption,
        "taken_at": photo.taken_at,
        "created_at": photo.created_at,
    }


def serialize_release(release: VehicleRelease) -> dict:
    return {
        "id": release.id,
        "tenant_id": release.tenant_id,
        "vehicle_id": release.vehicle_id,
        "reception_id": release.reception_id,
        "released_by": release.released_by,
        "released_at": release.released_at,
        "odometer_at_release": release.odometer_at_release,
        "condition_at_release": release.condition_at_release,
        "picked_up_by_name": release.picked_up_by_name,
        "picked_up_by_phone": release.picked_up_by_phone,
        "override_unauthorized_pickup": release.override_unauthorized_pickup,
        "override_reason": release.override_reason,
        "client_signature_file_id": release.client_signature_file_id,
        "release_type": release.release_type,
        "notes": release.notes,
        "created_at": release.created_at,
    }


async def create_reception(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ReceptionCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    current_year = datetime.now(UTC).year
    seq_num = await get_next_tenant_sequence(db, tenant_id, "reception")
    reception_number = f"REC-{current_year}-{seq_num:04d}"

    reception = VehicleReception(
        tenant_id=tenant_id,
        vehicle_id=payload.vehicle_id,
        client_id=payload.client_id or getattr(vehicle, "customer_client_id", None),
        reception_number=reception_number,
        received_by=actor_id,
        odometer_at_reception=payload.odometer_at_reception or (vehicle.current_km or 0),
        reported_issues=payload.reported_issues,
        visual_condition=payload.visual_condition,
        personal_items=payload.personal_items,
        fuel_level=payload.fuel_level,
        delivered_by_name=payload.delivered_by_name,
        delivered_by_phone=payload.delivered_by_phone,
        pickup_authorized_by_name=payload.pickup_authorized_by_name,
        pickup_authorized_by_phone=payload.pickup_authorized_by_phone,
        client_signature_file_id=payload.client_signature_file_id,
        estimated_completion_at=payload.estimated_completion_at,
        status="received",
    )
    db.add(reception)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_reception.created",
        entity_type="vehicle_reception",
        entity_id=reception.id,
        new_values={"reception_number": reception.reception_number, "status": reception.status},
    )
    await db.commit()
    await db.refresh(reception)
    return serialize_reception(reception)


async def list_receptions(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    client_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(VehicleReception).where(VehicleReception.tenant_id == tenant_id)
    if status_filter:
        query = query.where(VehicleReception.status == status_filter)
    if vehicle_id:
        query = query.where(VehicleReception.vehicle_id == vehicle_id)
    if client_id:
        query = query.where(VehicleReception.client_id == client_id)

    result = await db.execute(
        query.order_by(VehicleReception.created_at.desc()).limit(limit).offset(offset)
    )
    receptions = result.scalars().all()
    return [serialize_reception(r) for r in receptions]


async def get_reception_detail(db: AsyncSession, tenant_id: UUID, reception_id: UUID) -> dict:
    reception = await db.get(VehicleReception, reception_id)
    if not reception or reception.tenant_id != tenant_id:
        raise ApiError("reception_not_found", "Vehicle reception not found.", status_code=404)

    photos_res = await db.execute(
        select(ReceptionPhoto)
        .where(ReceptionPhoto.reception_id == reception_id, ReceptionPhoto.tenant_id == tenant_id)
        .order_by(ReceptionPhoto.taken_at.asc())
    )
    photos = [serialize_photo(p) for p in photos_res.scalars().all()]
    return serialize_reception(reception, photos=photos)


async def add_reception_photo(
    db: AsyncSession,
    tenant_id: UUID,
    reception_id: UUID,
    payload: ReceptionPhotoCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    reception = await db.get(VehicleReception, reception_id)
    if not reception or reception.tenant_id != tenant_id:
        raise ApiError("reception_not_found", "Vehicle reception not found.", status_code=404)

    file_obj = await db.get(File, payload.file_id)
    if not file_obj or file_obj.tenant_id != tenant_id:
        raise ApiError("file_not_found", "File not found.", status_code=404)

    photo = ReceptionPhoto(
        tenant_id=tenant_id,
        reception_id=reception_id,
        file_id=payload.file_id,
        caption=payload.caption,
    )
    db.add(photo)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="reception_photo.added",
        entity_type="reception_photo",
        entity_id=photo.id,
        new_values={"file_id": str(photo.file_id), "caption": photo.caption},
    )
    await db.commit()
    await db.refresh(photo)
    return serialize_photo(photo)


async def update_reception_status(
    db: AsyncSession,
    tenant_id: UUID,
    reception_id: UUID,
    new_status: str,
    *,
    actor_id: UUID | None = None,
) -> dict:
    reception = await db.get(VehicleReception, reception_id)
    if not reception or reception.tenant_id != tenant_id:
        raise ApiError("reception_not_found", "Vehicle reception not found.", status_code=404)

    old_status = reception.status
    reception.status = new_status
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_reception.status_updated",
        entity_type="vehicle_reception",
        entity_id=reception.id,
        old_values={"status": old_status},
        new_values={"status": new_status},
    )
    await db.commit()
    await db.refresh(reception)
    return serialize_reception(reception)


async def release_vehicle(
    db: AsyncSession,
    tenant_id: UUID,
    reception_id: UUID,
    payload: VehicleReleaseCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    reception = await db.get(VehicleReception, reception_id)
    if not reception or reception.tenant_id != tenant_id:
        raise ApiError("reception_not_found", "Vehicle reception not found.", status_code=404)

    if reception.status in {"delivered", "returned_no_service"}:
        raise ApiError(
            "reception_already_closed", "Vehicle has already been released.", status_code=409
        )

    # Validação de Levantamento (#2): Comparação de Nomes
    if reception.pickup_authorized_by_name and payload.picked_up_by_name:
        match_ok = _names_match(reception.pickup_authorized_by_name, payload.picked_up_by_name)
        if not match_ok and not payload.override_unauthorized_pickup:
            raise ApiError(
                "unauthorized_pickup_person",
                f"A pessoa indicada ({payload.picked_up_by_name}) difere da autorizada no check-in "
                f"({reception.pickup_authorized_by_name}). É necessária confirmação com motivo de exceção.",
                status_code=409,
            )

    release = VehicleRelease(
        tenant_id=tenant_id,
        vehicle_id=reception.vehicle_id,
        reception_id=reception_id,
        released_by=actor_id,
        odometer_at_release=payload.odometer_at_release,
        condition_at_release=payload.condition_at_release,
        picked_up_by_name=payload.picked_up_by_name,
        picked_up_by_phone=payload.picked_up_by_phone,
        override_unauthorized_pickup=payload.override_unauthorized_pickup,
        override_reason=payload.override_reason,
        client_signature_file_id=payload.client_signature_file_id,
        release_type=payload.release_type,
        notes=payload.notes,
    )
    db.add(release)

    # Set reception status matching release_type
    reception.status = (
        "delivered" if payload.release_type == "after_service" else "returned_no_service"
    )
    await db.flush()

    if payload.override_unauthorized_pickup:
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="vehicle_release.unauthorized_pickup_override",
            entity_type="vehicle_release",
            entity_id=release.id,
            new_values={
                "picked_up_by_name": payload.picked_up_by_name,
                "pickup_authorized_by_name": reception.pickup_authorized_by_name,
                "override_reason": payload.override_reason,
            },
        )

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_release.created",
        entity_type="vehicle_release",
        entity_id=release.id,
        new_values={"release_type": release.release_type, "reception_status": reception.status},
    )
    await db.commit()
    await db.refresh(release)
    return serialize_release(release)


async def get_vehicle_intervention_history(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
) -> dict:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    # 1. Recepções Anteriores
    rec_res = await db.execute(
        select(VehicleReception)
        .where(VehicleReception.tenant_id == tenant_id, VehicleReception.vehicle_id == vehicle_id)
        .order_by(VehicleReception.created_at.desc())
    )
    receptions = [
        {
            "id": r.id,
            "reception_number": r.reception_number,
            "received_at": r.received_at,
            "odometer_at_reception": r.odometer_at_reception,
            "reported_issues": r.reported_issues,
            "status": r.status,
        }
        for r in rec_res.scalars().all()
    ]

    # 2. Ordens de Serviço Concluídas
    wo_res = await db.execute(
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id, WorkOrder.vehicle_id == vehicle_id)
        .order_by(WorkOrder.created_at.desc())
    )
    work_orders = [
        {
            "id": wo.id,
            "work_order_number": getattr(wo, "work_order_number", f"OS-{wo.id.hex[:6].upper()}"),
            "status": wo.status,
            "created_at": wo.created_at,
            "total_labor_minutes": getattr(wo, "total_labor_minutes", 0),
            "actual_cost": float(getattr(wo, "actual_cost", 0.0) or 0.0),
        }
        for wo in wo_res.scalars().all()
    ]

    # 3. Peças Usadas / Montadas
    wo_ids = [wo["id"] for wo in work_orders]
    parts_used = []
    if wo_ids:
        parts_res = await db.execute(
            select(MaintenancePartUsed)
            .where(
                MaintenancePartUsed.tenant_id == tenant_id,
                MaintenancePartUsed.work_order_id.in_(wo_ids),
            )
            .order_by(MaintenancePartUsed.issued_at.desc())
        )
        parts_used = [
            {
                "id": p.id,
                "work_order_id": p.work_order_id,
                "part_name": getattr(p, "part_name", "Peça de substituição"),
                "quantity": p.quantity,
                "unit_cost": float(p.unit_cost or 0.0),
                "created_at": p.issued_at,
            }
            for p in parts_res.scalars().all()
        ]

    # 4. Garantias Ativas
    war_res = await db.execute(
        select(ServiceWarranty)
        .where(ServiceWarranty.tenant_id == tenant_id, ServiceWarranty.vehicle_id == vehicle_id)
        .order_by(ServiceWarranty.expires_at.desc())
    )
    warranties = [
        {
            "id": w.id,
            "warranty_type": w.warranty_type,
            "title": f"Garantia ({w.warranty_type})",
            "expires_at": w.expires_at,
            "status": w.status,
            "notes": w.notes,
        }
        for w in war_res.scalars().all()
    ]

    return {
        "vehicle_id": vehicle.id,
        "plate": vehicle.plate,
        "current_odometer_km": vehicle.current_km or 0,
        "receptions": receptions,
        "work_orders": work_orders,
        "parts_used": parts_used,
        "warranties": warranties,
    }
