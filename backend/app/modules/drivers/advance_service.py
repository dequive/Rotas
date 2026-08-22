"""Driver advance service — cash advance (despacho) lifecycle management."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.drivers.models import DriverAdvance
from app.modules.trips.models import Trip

# ── Serializer ────────────────────────────────────────────────────────────────


def serialize_advance(advance: DriverAdvance) -> dict[str, Any]:
    return {
        "id": str(advance.id),
        "tenant_id": str(advance.tenant_id),
        "trip_id": str(advance.trip_id),
        "driver_id": str(advance.driver_id),
        "amount_mzn": str(advance.amount_mzn),
        "allowance_mzn": str(advance.allowance_mzn),
        "expenses_mzn": str(advance.expenses_mzn),
        "currency": advance.currency,
        "status": advance.status,
        "issued_by": str(advance.issued_by) if advance.issued_by else None,
        "issued_at": advance.issued_at.isoformat() if advance.issued_at else None,
        "notes": advance.notes,
        "request_reference": advance.request_reference,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _require_trip(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Trip:
    trip = await db.scalar(select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id))
    if not trip:
        raise ApiError("trip_not_found", "Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
    return trip


async def _require_advance(db: AsyncSession, tenant_id: UUID, advance_id: UUID) -> DriverAdvance:
    advance = await db.scalar(
        select(DriverAdvance).where(
            DriverAdvance.id == advance_id,
            DriverAdvance.tenant_id == tenant_id,
        )
    )
    if not advance:
        raise ApiError("advance_not_found", "Advance not found.", status_code=status.HTTP_404_NOT_FOUND)
    return advance


# ── Public API ────────────────────────────────────────────────────────────────

DISPATCHABLE_STATUSES = {"planned", "in_progress"}


async def issue_advance(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    trip_id: UUID,
    driver_id: UUID,
    amount_mzn: Decimal,
    allowance_mzn: Decimal | None = None,
    expenses_mzn: Decimal = Decimal("0.00"),
    notes: str | None = None,
    request_reference: str | None = None,
) -> dict[str, Any]:
    """Issue a cash advance to a driver before departure.

    Constraints:
    - Trip must exist and belong to tenant_id.
    - Trip must be in 'planned' or 'in_progress' status.
    - No existing non-voided advance may exist for this trip (one advance per trip).
    """
    if allowance_mzn is None:
        allowance_mzn = amount_mzn - expenses_mzn
    if amount_mzn <= 0 or allowance_mzn < 0 or expenses_mzn < 0 or allowance_mzn + expenses_mzn != amount_mzn:
        raise ApiError(
            "invalid_advance_breakdown",
            "Advance amount must be positive and equal allowance plus expenses.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status not in DISPATCHABLE_STATUSES:
        raise ApiError(
            "trip_not_dispatchable",
            f"Cannot issue advance for trip in status '{trip.status}'. Trip must be 'planned' or 'in_progress'.",
            status_code=status.HTTP_409_CONFLICT,
        )

    existing = await db.scalar(
        select(DriverAdvance).where(
            DriverAdvance.trip_id == trip_id,
            DriverAdvance.tenant_id == tenant_id,
            DriverAdvance.status != "voided",
        )
    )
    if existing:
        raise ApiError(
            "advance_already_exists",
            "A non-voided advance already exists for this trip.",
            status_code=status.HTTP_409_CONFLICT,
        )

    advance = DriverAdvance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trip_id=trip_id,
        driver_id=driver_id,
        amount_mzn=amount_mzn,
        allowance_mzn=allowance_mzn,
        expenses_mzn=expenses_mzn,
        currency="MZN",
        status="issued",
        issued_by=user_id,
        notes=notes,
        request_reference=request_reference,
    )
    db.add(advance)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="driver_advance.issued",
        entity_type="driver_advance",
        entity_id=advance.id,
        new_values={
            "amount_mzn": str(amount_mzn),
            "allowance_mzn": str(allowance_mzn),
            "expenses_mzn": str(expenses_mzn),
            "trip_id": str(trip_id),
        },
    )
    # --- HOOK CONTABILISTICO (Fase 9) ---
    from datetime import datetime

    from app.modules.accounting.models import Account
    from app.modules.accounting.schemas import JournalEntryCreate
    from app.modules.accounting.schemas import JournalItemCreate as AccJournalItemCreate
    from app.modules.accounting.services import create_journal_entry

    if amount_mzn > 0:
        acct_advances = await db.scalar(
            select(Account).where(Account.tenant_id == tenant_id, Account.code.like("42%")).limit(1)
        )
        acct_bank = await db.scalar(
            select(Account).where(Account.tenant_id == tenant_id, Account.code.like("12%")).limit(1)
        )

        if acct_advances and acct_bank:
            await create_journal_entry(
                db,
                tenant_id=tenant_id,
                payload=JournalEntryCreate(
                    journal_type="TES",
                    date=datetime.now(),
                    reference=f"ADV-{str(advance.id)[:8]}",
                    description=f"Adiantamento de Viagem (Motorista: {driver_id})",
                    items=[
                        AccJournalItemCreate(
                            account_id=acct_advances.id,
                            description=f"Subsidio e Despesas - Viagem {trip_id}",
                            debit=amount_mzn,
                            credit=Decimal("0.00"),
                        ),
                        AccJournalItemCreate(
                            account_id=acct_bank.id,
                            description="Saida de Tesouraria",
                            debit=Decimal("0.00"),
                            credit=amount_mzn,
                        ),
                    ],
                ),
                actor_id=user_id,
            )
    # ------------------------------------

    await db.commit()
    await db.refresh(advance)
    return serialize_advance(advance)


async def void_advance(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    advance_id: UUID,
) -> dict[str, Any]:
    """Void an issued advance. Cannot void a settled advance."""
    advance = await _require_advance(db, tenant_id, advance_id)

    if advance.status == "settled":
        raise ApiError(
            "advance_already_settled",
            "Cannot void a settled advance.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if advance.status == "voided":
        raise ApiError(
            "advance_already_voided",
            "Advance is already voided.",
            status_code=status.HTTP_409_CONFLICT,
        )

    old_status = advance.status
    advance.status = "voided"
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="driver_advance.voided",
        entity_type="driver_advance",
        entity_id=advance.id,
        old_values={"status": old_status},
        new_values={"status": "voided"},
    )
    await db.commit()
    await db.refresh(advance)
    return serialize_advance(advance)


async def list_advances(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    trip_id: UUID | None = None,
    driver_id: UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List advances for a tenant with optional filters."""
    conditions = [DriverAdvance.tenant_id == tenant_id]
    if trip_id:
        conditions.append(DriverAdvance.trip_id == trip_id)
    if driver_id:
        conditions.append(DriverAdvance.driver_id == driver_id)
    if status_filter:
        conditions.append(DriverAdvance.status == status_filter)

    rows = await db.scalars(
        select(DriverAdvance)
        .where(and_(*conditions))
        .order_by(DriverAdvance.issued_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [serialize_advance(a) for a in rows]
