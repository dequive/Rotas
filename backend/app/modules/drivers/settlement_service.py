"""Settlement service — post-trip financial reconciliation (despacho liquidation)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.drivers.models import DriverAdvance, TripSettlement
from app.modules.trips.models import Trip, TripCost

# ── Serializer ────────────────────────────────────────────────────────────────


def serialize_settlement(s: TripSettlement) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "tenant_id": str(s.tenant_id),
        "trip_id": str(s.trip_id),
        "advance_id": str(s.advance_id) if s.advance_id else None,
        "total_costs_mzn": str(s.total_costs_mzn),
        "advance_amount_mzn": str(s.advance_amount_mzn),
        "balance_mzn": str(s.balance_mzn),
        "status": s.status,
        "approved_by": str(s.approved_by) if s.approved_by else None,
        "approved_at": s.approved_at.isoformat() if s.approved_at else None,
        "rejection_reason": s.rejection_reason,
        "pdf_file_id": str(s.pdf_file_id) if s.pdf_file_id else None,
        "settled_at": s.settled_at.isoformat() if s.settled_at else None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _require_trip(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Trip:
    trip = await db.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.tenant_id == tenant_id)
    )
    if not trip:
        raise ApiError("trip_not_found", "Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
    return trip


async def _require_settlement(
    db: AsyncSession, tenant_id: UUID, settlement_id: UUID
) -> TripSettlement:
    s = await db.scalar(
        select(TripSettlement).where(
            TripSettlement.id == settlement_id,
            TripSettlement.tenant_id == tenant_id,
        )
    )
    if not s:
        raise ApiError(
            "settlement_not_found",
            "Settlement not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return s


async def _sum_trip_costs(db: AsyncSession, tenant_id: UUID, trip_id: UUID) -> Decimal:
    """Sum TripCost.amount for all costs on a trip within the tenant."""
    result = await db.scalar(
        select(func.coalesce(func.sum(TripCost.amount), Decimal("0"))).where(
            TripCost.trip_id == trip_id,
            TripCost.tenant_id == tenant_id,
        )
    )
    return Decimal(str(result)) if result is not None else Decimal("0")


async def _latest_active_advance(
    db: AsyncSession, tenant_id: UUID, trip_id: UUID
) -> DriverAdvance | None:
    """Return the most recent non-voided advance for a trip, or None."""
    return await db.scalar(
        select(DriverAdvance)
        .where(
            DriverAdvance.trip_id == trip_id,
            DriverAdvance.tenant_id == tenant_id,
            DriverAdvance.status != "voided",
        )
        .order_by(DriverAdvance.issued_at.desc())
        .limit(1)
    )


# ── Public API ────────────────────────────────────────────────────────────────


async def compute_settlement(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    trip_id: UUID,
) -> dict[str, Any]:
    """Compute or refresh the settlement for a completed trip.

    Idempotent: if settlement already exists, return it as-is.
    Trip must be in 'completed' status.
    """
    trip = await _require_trip(db, tenant_id, trip_id)
    if trip.status != "completed":
        raise ApiError(
            "trip_not_completed",
            f"Settlement requires trip status 'completed', got '{trip.status}'.",
            status_code=status.HTTP_409_CONFLICT,
        )

    existing = await db.scalar(
        select(TripSettlement).where(
            TripSettlement.trip_id == trip_id,
            TripSettlement.tenant_id == tenant_id,
        )
    )
    if existing:
        return serialize_settlement(existing)

    total_costs = await _sum_trip_costs(db, tenant_id, trip_id)
    advance = await _latest_active_advance(db, tenant_id, trip_id)
    advance_amount = advance.amount_mzn if advance else Decimal("0")
    balance = advance_amount - total_costs

    settlement = TripSettlement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        trip_id=trip_id,
        advance_id=advance.id if advance else None,
        total_costs_mzn=total_costs,
        advance_amount_mzn=advance_amount,
        balance_mzn=balance,
        status="pending",
    )
    db.add(settlement)

    if advance:
        advance.status = "settled"

    await db.commit()
    await db.refresh(settlement)
    return serialize_settlement(settlement)


async def approve_settlement(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    settlement_id: UUID,
) -> dict[str, Any]:
    """Approve a pending settlement."""
    from datetime import UTC, datetime

    s = await _require_settlement(db, tenant_id, settlement_id)
    if s.status != "pending":
        if s.status == "approved":
            raise ApiError(
                "settlement_already_approved",
                "Settlement is already approved.",
                status_code=status.HTTP_409_CONFLICT,
            )
        raise ApiError(
            "settlement_not_pending",
            f"Cannot approve settlement in status '{s.status}'.",
            status_code=status.HTTP_409_CONFLICT,
        )

    s.status = "approved"
    s.approved_by = user_id
    s.approved_at = datetime.now(UTC)
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip_settlement.approved",
        entity_type="trip_settlement",
        entity_id=s.id,
        new_values={"status": "approved"},
    )
    await db.commit()
    await db.refresh(s)
    return serialize_settlement(s)


async def reject_settlement(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    settlement_id: UUID,
    reason: str,
) -> dict[str, Any]:
    """Reject a pending settlement."""
    s = await _require_settlement(db, tenant_id, settlement_id)
    if s.status != "pending":
        raise ApiError(
            "settlement_not_pending",
            f"Cannot reject settlement in status '{s.status}'.",
            status_code=status.HTTP_409_CONFLICT,
        )

    s.status = "rejected"
    s.rejection_reason = reason
    await db.flush()

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip_settlement.rejected",
        entity_type="trip_settlement",
        entity_id=s.id,
        new_values={"status": "rejected", "reason": reason},
    )
    await db.commit()
    await db.refresh(s)
    return serialize_settlement(s)


async def generate_settlement_pdf(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    settlement_id: UUID,
) -> bytes:
    """Generate a 'Recibo de Despacho' PDF and persist it.

    Uses fpdf2 + DejaVuSans for full UTF-8 support (Mozambican names with diacritics).
    Stores the PDF via save_generated_file and updates settlement.pdf_file_id.
    Returns raw PDF bytes.
    """
    from io import BytesIO

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    from app.modules.billing.exporters import FONTS_DIR
    from app.modules.drivers.models import Driver
    from app.modules.files.service import save_generated_file
    from app.modules.tenants.models import Tenant
    from app.modules.vehicles.models import Vehicle

    s = await _require_settlement(db, tenant_id, settlement_id)

    trip = await db.scalar(select(Trip).where(Trip.id == s.trip_id))
    driver = await db.scalar(select(Driver).where(Driver.id == trip.driver_id)) if trip else None
    vehicle = (
        await db.scalar(select(Vehicle).where(Vehicle.id == trip.vehicle_id)) if trip else None
    )
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))

    costs_rows = await db.scalars(
        select(TripCost).where(
            TripCost.trip_id == s.trip_id, TripCost.tenant_id == tenant_id
        )
    )
    costs = list(costs_rows)

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = FPDF()
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "RECIBO DE DESPACHO", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, tenant.name if tenant else "—",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Dados da Viagem", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(60, 6, "Motorista:")
    pdf.cell(0, 6, driver.full_name if driver else "—",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    doc_number = (driver.bi_number or driver.license_number or "—") if driver else "—"
    pdf.cell(60, 6, "Documento:")
    pdf.cell(0, 6, doc_number, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(60, 6, "Viatura:")
    pdf.cell(0, 6, vehicle.plate if vehicle else "—",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if trip:
        pdf.cell(60, 6, "Rota:")
        pdf.cell(0, 6, f"{trip.origin} → {trip.destination}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if trip.actual_departure:
            pdf.cell(60, 6, "Partida:")
            pdf.cell(0, 6, trip.actual_departure.strftime("%d/%m/%Y %H:%M"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if trip.actual_arrival:
            pdf.cell(60, 6, "Chegada:")
            pdf.cell(0, 6, trip.actual_arrival.strftime("%d/%m/%Y %H:%M"),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Despesas Realizadas", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(90, 6, "Descrição", border=1)
    pdf.cell(40, 6, "Categoria", border=1)
    pdf.cell(0, 6, "Valor (MZN)", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 9)
    for cost in costs:
        desc = cost.description or cost.cost_type
        pdf.cell(90, 6, desc[:50], border=1)
        pdf.cell(40, 6, cost.cost_type, border=1)
        pdf.cell(0, 6, f"{cost.amount:,.2f}", border=1, align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Resumo Financeiro", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(90, 7, "Adiantamento (Despacho):")
    pdf.cell(0, 7, f"MZN {s.advance_amount_mzn:,.2f}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(90, 7, "Total de Despesas:")
    pdf.cell(0, 7, f"MZN {s.total_costs_mzn:,.2f}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 11)
    balance_label = (
        "Saldo a Devolver à Empresa:" if s.balance_mzn >= 0
        else "Valor a Pagar ao Motorista:"
    )
    pdf.cell(90, 8, balance_label)
    pdf.cell(0, 8, f"MZN {abs(s.balance_mzn):,.2f}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    pdf.set_font("DejaVu", "", 10)
    pdf.cell(80, 6, "Assinatura do Motorista:", border="B")
    pdf.cell(20)
    pdf.cell(80, 6, "Assinatura do Gestor:", border="B",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)
    pdf.cell(80, 6, driver.full_name if driver else "—", align="C")
    pdf.cell(20)
    approved_label = "Aprovado por: " + (str(s.approved_by) if s.approved_by else "—")
    pdf.cell(80, 6, approved_label, align="C")

    buf = BytesIO()
    pdf.output(buf)
    pdf_bytes = buf.getvalue()

    file_obj = await save_generated_file(
        db,
        tenant_id,
        content=pdf_bytes,
        filename=f"despacho-{s.trip_id}.pdf",
        mime_type="application/pdf",
        file_type="settlement_pdf",
        entity_type="trip_settlement",
        entity_id=s.id,
    )
    s.pdf_file_id = file_obj.id
    await db.commit()
    return pdf_bytes
