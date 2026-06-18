from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.operations.models import OperationalWaiver
from app.modules.operations.schemas import OperationalWaiverCreate, OperationalWaiverRevokeRequest

WAIVER_TYPES = {
    "overweight_assignment",
    "missing_document",
    "expired_warning",
    "no_pod",
    "cost_overrun",
    "manual_dispatch",
    "negative_margin_approved",
}
RISK_LEVELS = {"low", "medium", "high", "critical"}


def now_utc() -> datetime:
    return datetime.now(UTC)


def serialize_waiver(waiver: OperationalWaiver) -> dict:
    return {
        "id": waiver.id,
        "tenant_id": waiver.tenant_id,
        "entity_type": waiver.entity_type,
        "entity_id": waiver.entity_id,
        "waiver_type": waiver.waiver_type,
        "reason": waiver.reason,
        "risk_level": waiver.risk_level,
        "approved_by": waiver.approved_by,
        "approved_at": waiver.approved_at,
        "expires_at": waiver.expires_at,
        "status": waiver.status,
        "created_at": waiver.created_at,
    }


async def create_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    payload: OperationalWaiverCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    if payload.waiver_type not in WAIVER_TYPES:
        raise ApiError(
            "invalid_waiver_type",
            "Invalid operational waiver type.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed": sorted(WAIVER_TYPES), "value": payload.waiver_type},
        )
    if payload.risk_level not in RISK_LEVELS:
        raise ApiError(
            "invalid_risk_level",
            "Invalid waiver risk level.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed": sorted(RISK_LEVELS), "value": payload.risk_level},
        )

    waiver = OperationalWaiver(
        tenant_id=tenant_id,
        approved_by=actor_id,
        **payload.model_dump(),
    )
    db.add(waiver)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_waiver.created",
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        new_values={
            "waiver_id": str(waiver.id),
            "waiver_type": waiver.waiver_type,
            "risk_level": waiver.risk_level,
            "reason": waiver.reason,
        },
    )
    await db.commit()
    await db.refresh(waiver)
    return serialize_waiver(waiver)


async def list_waivers(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    status_filter: str | None = None,
    waiver_type: str | None = None,
) -> list[dict]:
    query = select(OperationalWaiver).where(OperationalWaiver.tenant_id == tenant_id)
    if entity_type:
        query = query.where(OperationalWaiver.entity_type == entity_type)
    if entity_id:
        query = query.where(OperationalWaiver.entity_id == entity_id)
    if status_filter:
        query = query.where(OperationalWaiver.status == status_filter)
    if waiver_type:
        query = query.where(OperationalWaiver.waiver_type == waiver_type)
    result = await db.execute(query.order_by(OperationalWaiver.created_at.desc()))
    return [serialize_waiver(waiver) for waiver in result.scalars()]


async def revoke_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    waiver_id: UUID,
    payload: OperationalWaiverRevokeRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    waiver = await db.get(OperationalWaiver, waiver_id)
    if not waiver or waiver.tenant_id != tenant_id:
        raise ApiError("waiver_not_found", "Operational waiver not found.", status_code=404)
    if waiver.status == "revoked":
        return serialize_waiver(waiver)
    waiver.status = "revoked"
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="operational_waiver.revoked",
        entity_type=waiver.entity_type,
        entity_id=waiver.entity_id,
        old_values={"status": "active"},
        new_values={"status": waiver.status, "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(waiver)
    return serialize_waiver(waiver)


async def has_active_waiver(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    entity_type: str,
    entity_id: UUID,
    waiver_type: str,
) -> bool:
    current_time = now_utc()
    waiver_id = await db.scalar(
        select(OperationalWaiver.id).where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_type == entity_type,
            OperationalWaiver.entity_id == entity_id,
            OperationalWaiver.waiver_type == waiver_type,
            OperationalWaiver.status == "active",
            (
                OperationalWaiver.expires_at.is_(None)
                | (OperationalWaiver.expires_at > current_time)
            ),
        )
    )
    return waiver_id is not None
