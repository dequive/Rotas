"""INS-01 + INS-02: Vehicle insurance CRUD service."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.vehicles.models import InsuranceClaim, Vehicle, VehicleInsurance
from app.modules.vehicles.schemas import (
    InsuranceClaimCreate,
    InsuranceClaimStatusUpdate,
    VehicleInsuranceCreate,
)


def _serialize_insurance(ins: VehicleInsurance) -> dict:
    return {
        "id": str(ins.id),
        "tenant_id": str(ins.tenant_id),
        "vehicle_id": str(ins.vehicle_id),
        "policy_number": ins.policy_number,
        "insurer": ins.insurer,
        "coverage_type": ins.coverage_type,
        "premium_amount": float(ins.premium_amount) if ins.premium_amount is not None else None,
        "valid_from": ins.valid_from.isoformat(),
        "valid_until": ins.valid_until.isoformat(),
        "notes": ins.notes,
        "created_at": ins.created_at.isoformat(),
        "updated_at": ins.updated_at.isoformat(),
    }


def _serialize_claim(claim: InsuranceClaim) -> dict:
    return {
        "id": str(claim.id),
        "tenant_id": str(claim.tenant_id),
        "vehicle_id": str(claim.vehicle_id),
        "insurance_id": str(claim.insurance_id),
        "incident_id": str(claim.incident_id) if claim.incident_id else None,
        "claim_number": claim.claim_number,
        "claim_date": claim.claim_date.isoformat(),
        "estimated_damage": (
            float(claim.estimated_damage) if claim.estimated_damage is not None else None
        ),
        "status": claim.status,
        "resolved_at": claim.resolved_at.isoformat() if claim.resolved_at else None,
        "notes": claim.notes,
        "created_at": claim.created_at.isoformat(),
        "updated_at": claim.updated_at.isoformat(),
    }


async def _require_vehicle(db: AsyncSession, tenant_id: UUID, vehicle_id: UUID) -> Vehicle:
    vehicle = await db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.tenant_id == tenant_id)
    )
    if not vehicle:
        raise ApiError(
            "vehicle_not_found", "Vehicle not found.", status_code=status.HTTP_404_NOT_FOUND
        )
    return vehicle


async def _require_insurance(
    db: AsyncSession, tenant_id: UUID, insurance_id: UUID
) -> VehicleInsurance:
    ins = await db.scalar(
        select(VehicleInsurance).where(
            VehicleInsurance.id == insurance_id,
            VehicleInsurance.tenant_id == tenant_id,
        )
    )
    if not ins:
        raise ApiError(
            "insurance_not_found",
            "Insurance policy not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return ins


async def create_insurance(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    payload: VehicleInsuranceCreate,
    actor_id: UUID | None = None,
) -> dict:
    await _require_vehicle(db, tenant_id, vehicle_id)
    ins = VehicleInsurance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(),
    )
    db.add(ins)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_insurance.created",
        entity_type="vehicle_insurance",
        entity_id=ins.id,
        new_values=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(ins)
    return _serialize_insurance(ins)


async def list_insurances(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    await _require_vehicle(db, tenant_id, vehicle_id)
    rows = (
        await db.execute(
            select(VehicleInsurance)
            .where(
                VehicleInsurance.tenant_id == tenant_id,
                VehicleInsurance.vehicle_id == vehicle_id,
            )
            .order_by(VehicleInsurance.valid_until.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [_serialize_insurance(r) for r in rows]


async def get_insurance(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
) -> dict:
    await _require_vehicle(db, tenant_id, vehicle_id)
    ins = await _require_insurance(db, tenant_id, insurance_id)
    return _serialize_insurance(ins)


async def update_insurance(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
    payload: VehicleInsuranceCreate,
    actor_id: UUID | None = None,
) -> dict:
    await _require_vehicle(db, tenant_id, vehicle_id)
    ins = await _require_insurance(db, tenant_id, insurance_id)
    old_values = _serialize_insurance(ins)
    for key, value in payload.model_dump().items():
        setattr(ins, key, value)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_insurance.updated",
        entity_type="vehicle_insurance",
        entity_id=ins.id,
        old_values=old_values,
        new_values=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(ins)
    return _serialize_insurance(ins)


async def delete_insurance(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
    actor_id: UUID | None = None,
) -> None:
    await _require_vehicle(db, tenant_id, vehicle_id)
    ins = await _require_insurance(db, tenant_id, insurance_id)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_insurance.deleted",
        entity_type="vehicle_insurance",
        entity_id=ins.id,
        old_values=_serialize_insurance(ins),
    )
    await db.delete(ins)
    await db.commit()


async def create_claim(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
    payload: InsuranceClaimCreate,
    actor_id: UUID | None = None,
) -> dict:
    await _require_vehicle(db, tenant_id, vehicle_id)
    ins = await _require_insurance(db, tenant_id, insurance_id)
    claim = InsuranceClaim(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        insurance_id=ins.id,
        status="open",
        **payload.model_dump(),
    )
    db.add(claim)
    try:
        await db.flush()
    except Exception as exc:
        await db.rollback()
        if "ForeignKeyViolation" in type(exc).__name__ or "foreign key" in str(exc).lower():
            raise ApiError(
                "invalid_incident_id",
                "incident_id does not reference a valid trip incident.",
                status_code=422,
            ) from exc
        raise
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="insurance_claim.created",
        entity_type="insurance_claim",
        entity_id=claim.id,
        new_values=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(claim)
    return _serialize_claim(claim)


async def list_claims(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    await _require_vehicle(db, tenant_id, vehicle_id)
    await _require_insurance(db, tenant_id, insurance_id)
    rows = (
        await db.execute(
            select(InsuranceClaim)
            .where(
                InsuranceClaim.tenant_id == tenant_id,
                InsuranceClaim.insurance_id == insurance_id,
            )
            .order_by(InsuranceClaim.claim_date.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [_serialize_claim(r) for r in rows]


async def update_claim_status(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    insurance_id: UUID,
    claim_id: UUID,
    payload: InsuranceClaimStatusUpdate,
    actor_id: UUID | None = None,
) -> dict:
    from datetime import UTC, datetime

    await _require_vehicle(db, tenant_id, vehicle_id)
    await _require_insurance(db, tenant_id, insurance_id)
    claim = await db.scalar(
        select(InsuranceClaim).where(
            InsuranceClaim.id == claim_id,
            InsuranceClaim.tenant_id == tenant_id,
            InsuranceClaim.insurance_id == insurance_id,
        )
    )
    if not claim:
        raise ApiError("claim_not_found", "Claim not found.", status_code=status.HTTP_404_NOT_FOUND)
    old_status = claim.status
    claim.status = payload.status
    if payload.notes:
        claim.notes = payload.notes
    if payload.status in ("paid", "rejected"):
        claim.resolved_at = datetime.now(UTC)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="insurance_claim.status_updated",
        entity_type="insurance_claim",
        entity_id=claim.id,
        old_values={"status": old_status},
        new_values={"status": payload.status},
    )
    await db.commit()
    await db.refresh(claim)
    return _serialize_claim(claim)
