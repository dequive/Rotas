from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.third_party.models import (
    DriverVehicleAssignment,
    MzProvince,
    ServiceProviderProfile,
    SupplierProfile,
    ThirdParty,
    ThirdPartyRole,
)
from app.modules.third_party.schemas import (
    RoleCreate,
    ServiceProviderProfileCreate,
    SupplierProfileCreate,
    ThirdPartyCreate,
    ThirdPartyUpdate,
    VALID_ROLE_TYPES,
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
