from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.third_party.models import (
    DriverVehicleAssignment,
    MzProvince,
    OperationalDocument,
    ServiceProviderProfile,
    SupplierProfile,
    ThirdParty,
    ThirdPartyRole,
)
from app.modules.third_party.schemas import (
    AssignmentCreate,
    DocumentCreate,
    DocumentVerify,
    RoleCreate,
    ServiceProviderProfileCreate,
    SupplierProfileCreate,
    ThirdPartyCreate,
    ThirdPartyUpdate,
    VALID_ROLE_TYPES,
    VALID_SUBJECT_TYPES,
)


# ── Serializers ───────────────────────────────────────────────────────────────


def serialize_third_party(tp: ThirdParty) -> dict:
    return {
        "id": tp.id,
        "tenant_id": tp.tenant_id,
        "name": tp.name,
        "trade_name": tp.trade_name,
        "legal_type": tp.legal_type,
        "nuit": tp.nuit,
        "contact_email": tp.contact_email,
        "contact_phone": tp.contact_phone,
        "province_code": tp.province_code,
        "address": tp.address,
        "status": tp.status,
        "is_verified": tp.is_verified,
        "verified_at": tp.verified_at,
        "notes": tp.notes,
        "created_at": tp.created_at,
        "updated_at": tp.updated_at,
    }


def serialize_role(r: ThirdPartyRole) -> dict:
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "third_party_id": r.third_party_id,
        "role_type": r.role_type,
        "is_active": r.is_active,
        "certified_at": r.certified_at,
        "certification_ref": r.certification_ref,
        "created_at": r.created_at,
    }


def serialize_supplier_profile(sp: SupplierProfile) -> dict:
    return {
        "id": sp.id,
        "tenant_id": sp.tenant_id,
        "third_party_id": sp.third_party_id,
        "payment_terms": sp.payment_terms,
        "preferred_currency": sp.preferred_currency,
        "credit_limit": sp.credit_limit,
        "account_number": sp.account_number,
        "bank_name": sp.bank_name,
        "created_at": sp.created_at,
        "updated_at": sp.updated_at,
    }


def serialize_service_provider_profile(spp: ServiceProviderProfile) -> dict:
    return {
        "id": spp.id,
        "tenant_id": spp.tenant_id,
        "third_party_id": spp.third_party_id,
        "service_categories": spp.service_categories,
        "coverage_province_codes": spp.coverage_province_codes,
        "response_time_hours": spp.response_time_hours,
        "rate_per_hour": spp.rate_per_hour,
        "created_at": spp.created_at,
        "updated_at": spp.updated_at,
    }


# ── Guard helpers ─────────────────────────────────────────────────────────────


async def _require_third_party(
    db: AsyncSession, tenant_id: UUID, tp_id: UUID
) -> ThirdParty:
    tp = await db.get(ThirdParty, tp_id)
    if not tp or tp.tenant_id != tenant_id:
        raise ApiError("third_party_not_found", "Third party not found.", status_code=404)
    return tp


async def _nuit_exists(
    db: AsyncSession,
    tenant_id: UUID,
    nuit: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    query = select(ThirdParty.id).where(
        ThirdParty.tenant_id == tenant_id,
        ThirdParty.nuit == nuit,
    )
    if exclude_id is not None:
        query = query.where(ThirdParty.id != exclude_id)
    return await db.scalar(query) is not None


# ── Core CRUD ─────────────────────────────────────────────────────────────────


async def create_third_party(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ThirdPartyCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    if payload.nuit and await _nuit_exists(db, tenant_id, payload.nuit):
        raise ApiError(
            "third_party_nuit_duplicate",
            "A third party with this NUIT already exists for this tenant.",
            status_code=409,
            details={"nuit": payload.nuit},
        )

    tp = ThirdParty(tenant_id=tenant_id, **payload.model_dump())
    db.add(tp)
    await db.flush()
    await db.refresh(tp)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.created",
        entity_type="third_party",
        entity_id=tp.id,
        new_values=serialize_third_party(tp),
    )
    await db.commit()
    await db.refresh(tp)
    return serialize_third_party(tp)


async def list_third_parties(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(ThirdParty).where(ThirdParty.tenant_id == tenant_id)
    if status is not None:
        query = query.where(ThirdParty.status == status)
    query = query.order_by(ThirdParty.name.asc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [serialize_third_party(tp) for tp in result.scalars()]


async def get_third_party(db: AsyncSession, tenant_id: UUID, tp_id: UUID) -> dict:
    return serialize_third_party(await _require_third_party(db, tenant_id, tp_id))


async def update_third_party(
    db: AsyncSession,
    tenant_id: UUID,
    tp_id: UUID,
    payload: ThirdPartyUpdate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    tp = await _require_third_party(db, tenant_id, tp_id)
    old_values = serialize_third_party(tp)
    values = payload.model_dump(exclude_unset=True)

    if "nuit" in values and values["nuit"] and values["nuit"] != tp.nuit:
        if await _nuit_exists(db, tenant_id, values["nuit"], exclude_id=tp.id):
            raise ApiError(
                "third_party_nuit_duplicate",
                "A third party with this NUIT already exists for this tenant.",
                status_code=409,
                details={"nuit": values["nuit"]},
            )

    for field, value in values.items():
        setattr(tp, field, value)

    await db.flush()
    await db.refresh(tp)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.updated",
        entity_type="third_party",
        entity_id=tp.id,
        old_values=old_values,
        new_values=serialize_third_party(tp),
    )
    await db.commit()
    await db.refresh(tp)
    return serialize_third_party(tp)


# ── Role CRUD ─────────────────────────────────────────────────────────────────


async def create_role(
    db: AsyncSession,
    tenant_id: UUID,
    tp_id: UUID,
    payload: RoleCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    # Validate role_type
    if payload.role_type not in VALID_ROLE_TYPES:
        raise ApiError(
            "invalid_role_type",
            f"role_type must be one of: {', '.join(sorted(VALID_ROLE_TYPES))}.",
            status_code=422,
            details={"role_type": payload.role_type, "valid": sorted(VALID_ROLE_TYPES)},
        )

    # Ensure third party belongs to tenant
    await _require_third_party(db, tenant_id, tp_id)

    # Check for duplicate role
    existing = await db.scalar(
        select(ThirdPartyRole.id).where(
            ThirdPartyRole.third_party_id == tp_id,
            ThirdPartyRole.role_type == payload.role_type,
        )
    )
    if existing is not None:
        raise ApiError(
            "role_already_assigned",
            "This role type is already assigned to the third party.",
            status_code=409,
            details={"role_type": payload.role_type},
        )

    role = ThirdPartyRole(
        tenant_id=tenant_id,
        third_party_id=tp_id,
        **payload.model_dump(),
    )
    db.add(role)
    await db.flush()
    await db.refresh(role)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.role_assigned",
        entity_type="third_party_role",
        entity_id=role.id,
        new_values=serialize_role(role),
    )
    await db.commit()
    await db.refresh(role)
    return serialize_role(role)


async def list_roles(
    db: AsyncSession, tenant_id: UUID, tp_id: UUID
) -> list[dict]:
    # Validate access
    await _require_third_party(db, tenant_id, tp_id)
    result = await db.execute(
        select(ThirdPartyRole)
        .where(ThirdPartyRole.third_party_id == tp_id)
        .order_by(ThirdPartyRole.role_type.asc())
    )
    return [serialize_role(r) for r in result.scalars()]


# ── Profile upsert ────────────────────────────────────────────────────────────


async def upsert_supplier_profile(
    db: AsyncSession,
    tenant_id: UUID,
    tp_id: UUID,
    payload: SupplierProfileCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_third_party(db, tenant_id, tp_id)

    existing = await db.scalar(
        select(SupplierProfile).where(SupplierProfile.third_party_id == tp_id)
    )
    if existing is not None:
        values = payload.model_dump(exclude_unset=True)
        for field, value in values.items():
            setattr(existing, field, value)
        await db.flush()
        await db.refresh(existing)
        sp = existing
    else:
        sp = SupplierProfile(
            tenant_id=tenant_id,
            third_party_id=tp_id,
            **payload.model_dump(),
        )
        db.add(sp)
        await db.flush()
        await db.refresh(sp)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.supplier_profile_updated",
        entity_type="supplier_profile",
        entity_id=sp.id,
        new_values=serialize_supplier_profile(sp),
    )
    await db.commit()
    await db.refresh(sp)
    return serialize_supplier_profile(sp)


async def upsert_service_provider_profile(
    db: AsyncSession,
    tenant_id: UUID,
    tp_id: UUID,
    payload: ServiceProviderProfileCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    await _require_third_party(db, tenant_id, tp_id)

    existing = await db.scalar(
        select(ServiceProviderProfile).where(
            ServiceProviderProfile.third_party_id == tp_id
        )
    )
    if existing is not None:
        values = payload.model_dump(exclude_unset=True)
        for field, value in values.items():
            setattr(existing, field, value)
        await db.flush()
        await db.refresh(existing)
        spp = existing
    else:
        spp = ServiceProviderProfile(
            tenant_id=tenant_id,
            third_party_id=tp_id,
            **payload.model_dump(),
        )
        db.add(spp)
        await db.flush()
        await db.refresh(spp)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.service_provider_profile_updated",
        entity_type="service_provider_profile",
        entity_id=spp.id,
        new_values=serialize_service_provider_profile(spp),
    )
    await db.commit()
    await db.refresh(spp)
    return serialize_service_provider_profile(spp)


# ── Provinces ─────────────────────────────────────────────────────────────────


async def list_provinces(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(MzProvince).order_by(MzProvince.name.asc())
    )
    return [
        {
            "code": p.code,
            "name": p.name,
            "name_local": p.name_local,
            "region": p.region,
        }
        for p in result.scalars()
    ]


# ── DriverVehicleAssignment ───────────────────────────────────────────────────


def serialize_assignment(a: DriverVehicleAssignment) -> dict:
    return {
        "id": a.id,
        "tenant_id": a.tenant_id,
        "driver_id": a.driver_id,
        "vehicle_id": a.vehicle_id,
        "assigned_at": a.assigned_at,
        "unassigned_at": a.unassigned_at,
        "assignment_type": a.assignment_type,
        "notes": a.notes,
        "assigned_by": a.assigned_by,
        "created_at": a.created_at,
    }


async def assign_driver_to_vehicle(
    db: AsyncSession,
    tenant_id: UUID,
    payload: AssignmentCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Create a new driver-vehicle assignment with cross-tenant isolation."""
    from app.modules.drivers.models import Driver
    from app.modules.vehicles.models import Vehicle

    driver = await db.get(Driver, payload.driver_id)
    if not driver or driver.tenant_id != tenant_id:
        raise ApiError("driver_not_found", "Driver not found.", status_code=404)

    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    assignment = DriverVehicleAssignment(
        tenant_id=tenant_id,
        driver_id=payload.driver_id,
        vehicle_id=payload.vehicle_id,
        assignment_type=payload.assignment_type,
        notes=payload.notes,
        assigned_by=actor_id,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver_vehicle_assignment.created",
        entity_type="driver_vehicle_assignment",
        entity_id=assignment.id,
        new_values={
            "driver_id": str(payload.driver_id),
            "vehicle_id": str(payload.vehicle_id),
        },
    )
    await db.commit()
    await db.refresh(assignment)
    return serialize_assignment(assignment)


async def unassign_driver_from_vehicle(
    db: AsyncSession,
    tenant_id: UUID,
    assignment_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Soft-delete: set unassigned_at = now(). Idempotent if already unassigned."""
    assignment = await db.get(DriverVehicleAssignment, assignment_id)
    if not assignment or assignment.tenant_id != tenant_id:
        raise ApiError("assignment_not_found", "Assignment not found.", status_code=404)
    if assignment.unassigned_at is not None:
        return serialize_assignment(assignment)  # already unassigned — idempotent

    assignment.unassigned_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(assignment)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver_vehicle_assignment.unassigned",
        entity_type="driver_vehicle_assignment",
        entity_id=assignment.id,
        new_values={"unassigned_at": assignment.unassigned_at.isoformat()},
    )
    await db.commit()
    await db.refresh(assignment)
    return serialize_assignment(assignment)


async def list_assignments(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    driver_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    current_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List assignments, optionally filtered to active rows (unassigned_at IS NULL)."""
    query = select(DriverVehicleAssignment).where(
        DriverVehicleAssignment.tenant_id == tenant_id
    )
    if driver_id:
        query = query.where(DriverVehicleAssignment.driver_id == driver_id)
    if vehicle_id:
        query = query.where(DriverVehicleAssignment.vehicle_id == vehicle_id)
    if current_only:
        query = query.where(DriverVehicleAssignment.unassigned_at.is_(None))
    query = (
        query.order_by(DriverVehicleAssignment.assigned_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return [serialize_assignment(a) for a in result.scalars()]


# ── OperationalDocument ───────────────────────────────────────────────────────


def serialize_document(doc: OperationalDocument) -> dict:
    return {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "subject_type": doc.subject_type,
        "subject_id": doc.subject_id,
        "document_type": doc.document_type,
        "file_id": doc.file_id,
        "document_number": doc.document_number,
        "issued_at": doc.issued_at,
        "expiry_date": doc.expiry_date,
        "issuing_authority": doc.issuing_authority,
        "verification_status": doc.verification_status,
        "verified_by": doc.verified_by,
        "verified_at": doc.verified_at,
        "notes": doc.notes,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


async def create_document(
    db: AsyncSession,
    tenant_id: UUID,
    payload: DocumentCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Creates an operational document. Validates subject_type and file_id tenant ownership."""
    from app.modules.files.models import File

    if payload.subject_type not in VALID_SUBJECT_TYPES:
        raise ApiError(
            "invalid_subject_type",
            f"subject_type must be one of {VALID_SUBJECT_TYPES}",
            status_code=422,
        )

    if payload.file_id is not None:
        file = await db.get(File, payload.file_id)
        if not file or file.tenant_id != tenant_id:
            raise ApiError("file_not_found", "File not found.", status_code=404)

    doc = OperationalDocument(tenant_id=tenant_id, **payload.model_dump())
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_document.created",
        entity_type="operational_document",
        entity_id=doc.id,
        new_values={
            "subject_type": payload.subject_type,
            "subject_id": str(payload.subject_id),
            "document_type": payload.document_type,
        },
    )
    await db.commit()
    await db.refresh(doc)
    return serialize_document(doc)


async def list_documents(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    subject_type: str | None = None,
    subject_id: UUID | None = None,
    verification_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(OperationalDocument).where(OperationalDocument.tenant_id == tenant_id)
    if subject_type:
        query = query.where(OperationalDocument.subject_type == subject_type)
    if subject_id:
        query = query.where(OperationalDocument.subject_id == subject_id)
    if verification_status:
        query = query.where(OperationalDocument.verification_status == verification_status)
    result = await db.execute(
        query.order_by(OperationalDocument.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_document(d) for d in result.scalars()]


async def verify_document(
    db: AsyncSession,
    tenant_id: UUID,
    doc_id: UUID,
    payload: DocumentVerify,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Set verification_status to verified or rejected, record verifier."""
    doc = await db.get(OperationalDocument, doc_id)
    if not doc or doc.tenant_id != tenant_id:
        raise ApiError("document_not_found", "Document not found.", status_code=404)
    old_status = doc.verification_status
    doc.verification_status = payload.verification_status
    doc.verified_by = actor_id
    doc.verified_at = datetime.now(UTC)
    if payload.notes:
        doc.notes = payload.notes
    await db.flush()
    await db.refresh(doc)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_document.verified",
        entity_type="operational_document",
        entity_id=doc.id,
        old_values={"verification_status": old_status},
        new_values={"verification_status": doc.verification_status},
    )
    await db.commit()
    await db.refresh(doc)
    return serialize_document(doc)


async def get_expiring_documents(
    db: AsyncSession,
    tenant_id: UUID,
    days_ahead: int,
) -> list[dict]:
    """Return documents expiring within days_ahead days from today.
    Used by the ARQ document expiry alert job and the expiring endpoint.
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    result = await db.execute(
        select(OperationalDocument).where(
            OperationalDocument.tenant_id == tenant_id,
            OperationalDocument.expiry_date.isnot(None),
            OperationalDocument.expiry_date >= today,
            OperationalDocument.expiry_date <= cutoff,
        ).order_by(OperationalDocument.expiry_date.asc())
    )
    return [serialize_document(d) for d in result.scalars()]
