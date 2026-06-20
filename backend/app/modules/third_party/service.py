from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.third_party.models import (
    DriverVehicleAssignment,
    MzProvince,
    OperationalDocument,
    ServiceProviderProfile,
    SupplierEvaluation,
    SupplierLedgerEntry,
    SupplierProfile,
    ThirdParty,
    ThirdPartyContact,
    ThirdPartyRole,
)
from app.modules.third_party.schemas import (
    VALID_ROLE_TYPES,
    VALID_SUBJECT_TYPES,
    AssignmentCreate,
    ContactCreate,
    DocumentCreate,
    DocumentVerify,
    EvaluationCreate,
    PaymentCreate,
    RoleCreate,
    ServiceProviderProfileCreate,
    SupplierProfileCreate,
    ThirdPartyCreate,
    ThirdPartyUpdate,
)

# ── Serializers ───────────────────────────────────────────────────────────────


def serialize_third_party(tp: ThirdParty, *, average_score: Decimal | None = None) -> dict:
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
        "activity_code": tp.activity_code,
        "sector": tp.sector,
        "status": tp.status,
        "is_verified": tp.is_verified,
        "verified_at": tp.verified_at,
        "notes": tp.notes,
        "created_at": tp.created_at,
        "updated_at": tp.updated_at,
        "average_score": str(average_score) if average_score is not None else None,
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


async def _require_third_party(db: AsyncSession, tenant_id: UUID, tp_id: UUID) -> ThirdParty:
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


async def list_roles(db: AsyncSession, tenant_id: UUID, tp_id: UUID) -> list[dict]:
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
        select(ServiceProviderProfile).where(ServiceProviderProfile.third_party_id == tp_id)
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
    result = await db.execute(select(MzProvince).order_by(MzProvince.name.asc()))
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
    query = select(DriverVehicleAssignment).where(DriverVehicleAssignment.tenant_id == tenant_id)
    if driver_id:
        query = query.where(DriverVehicleAssignment.driver_id == driver_id)
    if vehicle_id:
        query = query.where(DriverVehicleAssignment.vehicle_id == vehicle_id)
    if current_only:
        query = query.where(DriverVehicleAssignment.unassigned_at.is_(None))
    query = query.order_by(DriverVehicleAssignment.assigned_at.desc()).limit(limit).offset(offset)
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
        select(OperationalDocument)
        .where(
            OperationalDocument.tenant_id == tenant_id,
            OperationalDocument.expiry_date.isnot(None),
            OperationalDocument.expiry_date >= today,
            OperationalDocument.expiry_date <= cutoff,
        )
        .order_by(OperationalDocument.expiry_date.asc())
    )
    return [serialize_document(d) for d in result.scalars()]


# ── Party Directory (UNION ALL) ───────────────────────────────────────────────


async def search_party_directory(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    query: str | None = None,
    subject_types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Single UNION ALL query across drivers / clients / third_parties.

    subject_types: optional list to restrict which entity types are included.
                   e.g. ['driver'] returns only drivers.
                   None or empty list returns all three types.
    query: optional name search applied per-sub-select (ILIKE %query%) before the UNION.
    """
    from sqlalchemy import String, cast, column, literal, union_all

    from app.modules.clients.models import Client
    from app.modules.drivers.models import Driver

    _all_types = subject_types or ["driver", "client", "third_party"]

    subqueries = []

    if "driver" in _all_types:
        q = select(
            Driver.id.label("subject_id"),
            literal("driver").label("subject_type"),
            Driver.full_name.label("name"),
            Driver.status.label("status"),
        ).where(Driver.tenant_id == tenant_id)
        if query:
            q = q.where(Driver.full_name.ilike(f"%{query}%"))
        subqueries.append(q)

    if "client" in _all_types:
        q = select(
            Client.id.label("subject_id"),
            literal("client").label("subject_type"),
            Client.trading_name.label("name"),
            cast(Client.is_active, String).label("status"),
        ).where(Client.tenant_id == tenant_id)
        if query:
            q = q.where(Client.trading_name.ilike(f"%{query}%"))
        subqueries.append(q)

    if "third_party" in _all_types:
        q = select(
            ThirdParty.id.label("subject_id"),
            literal("third_party").label("subject_type"),
            ThirdParty.name.label("name"),
            ThirdParty.status.label("status"),
        ).where(ThirdParty.tenant_id == tenant_id)
        if query:
            q = q.where(ThirdParty.name.ilike(f"%{query}%"))
        subqueries.append(q)

    if not subqueries:
        return []

    if len(subqueries) == 1:
        stmt = subqueries[0]
    else:
        stmt = union_all(*subqueries)

    # Wrap in subquery to apply ORDER BY + LIMIT + OFFSET on the full UNION result
    paginated = (
        select(
            column("subject_id"),
            column("subject_type"),
            column("name"),
            column("status"),
        )
        .select_from(stmt.subquery("party_union"))
        .order_by(column("name").asc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(paginated)
    rows = result.fetchall()
    return [
        {
            "subject_id": row.subject_id,
            "subject_type": row.subject_type,
            "name": row.name,
            "status": row.status,
        }
        for row in rows
    ]


# ── Contacts ──────────────────────────────────────────────────────────────────


async def create_contact(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
    payload: ContactCreate,
    actor_id: UUID,
) -> dict:
    party = await _require_third_party(db, tenant_id, third_party_id)
    contact = ThirdPartyContact(
        tenant_id=tenant_id,
        third_party_id=party.id,
        name=payload.name,
        role=payload.role,
        phone=payload.phone,
        email=payload.email,
        is_primary=payload.is_primary,
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party_contact.created",
        entity_type="third_party_contact",
        entity_id=contact.id,
        new_values={"third_party_id": str(third_party_id), "name": payload.name},
    )
    await db.commit()
    return serialize_contact(contact)


async def list_contacts(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
) -> list[dict]:
    await _require_third_party(db, tenant_id, third_party_id)
    result = await db.execute(
        select(ThirdPartyContact)
        .where(
            ThirdPartyContact.tenant_id == tenant_id,
            ThirdPartyContact.third_party_id == third_party_id,
        )
        .order_by(ThirdPartyContact.is_primary.desc(), ThirdPartyContact.created_at)
    )
    return [serialize_contact(c) for c in result.scalars().all()]


async def delete_contact(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
    contact_id: UUID,
    actor_id: UUID,
) -> None:
    await _require_third_party(db, tenant_id, third_party_id)
    result = await db.execute(
        select(ThirdPartyContact).where(
            ThirdPartyContact.id == contact_id,
            ThirdPartyContact.tenant_id == tenant_id,
            ThirdPartyContact.third_party_id == third_party_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise ApiError("contact_not_found", "Contacto não encontrado", 404)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party_contact.deleted",
        entity_type="third_party_contact",
        entity_id=contact_id,
        old_values={"name": contact.name},
    )
    await db.delete(contact)
    await db.commit()


def serialize_contact(c: ThirdPartyContact) -> dict:
    return {
        "id": str(c.id),
        "third_party_id": str(c.third_party_id),
        "name": c.name,
        "role": c.role,
        "phone": c.phone,
        "email": c.email,
        "is_primary": c.is_primary,
        "created_at": c.created_at.isoformat(),
    }


# ── Ledger / account ──────────────────────────────────────────────────────────


async def get_supplier_account(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
) -> dict:
    await _require_third_party(db, tenant_id, third_party_id)
    # Balance = sum(credits) - sum(debits) — NEVER denormalised, always computed
    agg = await db.execute(
        select(
            func.coalesce(
                func.sum(SupplierLedgerEntry.amount).filter(
                    SupplierLedgerEntry.entry_type == "credit"
                ),
                Decimal("0.00"),
            ).label("total_credits"),
            func.coalesce(
                func.sum(SupplierLedgerEntry.amount).filter(
                    SupplierLedgerEntry.entry_type == "debit"
                ),
                Decimal("0.00"),
            ).label("total_debits"),
        ).where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.third_party_id == third_party_id,
        )
    )
    row = agg.one()
    total_credits = row.total_credits
    total_debits = row.total_debits
    balance = total_credits - total_debits

    entries_result = await db.execute(
        select(SupplierLedgerEntry)
        .where(
            SupplierLedgerEntry.tenant_id == tenant_id,
            SupplierLedgerEntry.third_party_id == third_party_id,
        )
        .order_by(
            SupplierLedgerEntry.entry_date.desc(),
            SupplierLedgerEntry.created_at.desc(),
        )
        .limit(200)
    )
    entries = [serialize_ledger_entry(e) for e in entries_result.scalars().all()]
    return {
        "third_party_id": str(third_party_id),
        "total_debits": str(total_debits),
        "total_credits": str(total_credits),
        "balance": str(balance),
        "entries": entries,
    }


async def create_payment(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
    payload: PaymentCreate,
    actor_id: UUID,
) -> dict:
    """Creates a supplier_ledger_entry with entry_type=credit."""
    await _require_third_party(db, tenant_id, third_party_id)
    if payload.fuel_purchase_id:
        source_type = "fuel_purchase"
        source_id = payload.fuel_purchase_id
    elif payload.work_order_id:
        source_type = "work_order"
        source_id = payload.work_order_id
    else:
        source_type = "manual_payment"
        source_id = None
    entry = SupplierLedgerEntry(
        tenant_id=tenant_id,
        third_party_id=third_party_id,
        entry_type="credit",
        amount=payload.amount,
        source_type=source_type,
        source_id=source_id,
        description=payload.description,
        entry_date=payload.payment_date or date.today(),
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="supplier_payment.created",
        entity_type="supplier_ledger_entry",
        entity_id=entry.id,
        new_values={"amount": str(payload.amount), "source_type": source_type},
    )
    await db.commit()
    return serialize_ledger_entry(entry)


def serialize_ledger_entry(e: SupplierLedgerEntry) -> dict:
    return {
        "id": str(e.id),
        "third_party_id": str(e.third_party_id),
        "entry_type": e.entry_type,
        "amount": str(e.amount),
        "source_type": e.source_type,
        "source_id": str(e.source_id) if e.source_id else None,
        "description": e.description,
        "entry_date": e.entry_date.isoformat(),
        "created_at": e.created_at.isoformat(),
    }


# ── Evaluations ───────────────────────────────────────────────────────────────


async def create_evaluation(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
    payload: EvaluationCreate,
    actor_id: UUID,
) -> dict:
    await _require_third_party(db, tenant_id, third_party_id)
    if not payload.criteria:
        raise ApiError("empty_criteria", "Critérios de avaliação não podem estar vazios", 422)
    total_weight = sum(c["weight"] for c in payload.criteria)
    if abs(total_weight - 1.0) > 0.01:
        raise ApiError(
            "invalid_weights",
            f"Pesos devem somar 1.0 (soma actual: {total_weight:.2f})",
            422,
        )
    score = Decimal(
        str(sum(c["weight"] * c["score"] for c in payload.criteria))
    ).quantize(Decimal("0.01"))

    evaluation = SupplierEvaluation(
        tenant_id=tenant_id,
        third_party_id=third_party_id,
        evaluated_by=actor_id,
        evaluation_date=payload.evaluation_date or date.today(),
        criteria=payload.criteria,
        score=score,
        notes=payload.notes,
    )
    db.add(evaluation)
    await db.flush()
    await db.refresh(evaluation)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="supplier_evaluation.created",
        entity_type="supplier_evaluation",
        entity_id=evaluation.id,
        new_values={"score": str(score)},
    )
    await db.commit()
    return serialize_evaluation(evaluation)


async def list_evaluations(
    db: AsyncSession,
    tenant_id: UUID,
    third_party_id: UUID,
) -> dict:
    await _require_third_party(db, tenant_id, third_party_id)
    result = await db.execute(
        select(SupplierEvaluation)
        .where(
            SupplierEvaluation.tenant_id == tenant_id,
            SupplierEvaluation.third_party_id == third_party_id,
        )
        .order_by(SupplierEvaluation.evaluation_date.desc())
    )
    evals = [serialize_evaluation(e) for e in result.scalars().all()]
    avg_score = None
    if evals:
        avg_score = str(
            Decimal(str(sum(float(e["score"]) for e in evals) / len(evals))).quantize(
                Decimal("0.01")
            )
        )
    return {"average_score": avg_score, "evaluations": evals}


def serialize_evaluation(e: SupplierEvaluation) -> dict:
    return {
        "id": str(e.id),
        "third_party_id": str(e.third_party_id),
        "evaluated_by": str(e.evaluated_by) if e.evaluated_by else None,
        "evaluation_date": e.evaluation_date.isoformat(),
        "criteria": e.criteria,
        "score": str(e.score),
        "notes": e.notes,
        "created_at": e.created_at.isoformat(),
    }
