"""ANA-02: Fuel consumption XLSX report generator."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fuel.models import FuelLog
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

RED_FILL = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
HEADER_FONT = Font(bold=True)

COLUMNS = [
    "Matrícula",
    "Combustível Total (L)",
    "Custo Total (MZN)",
    "Consumo Real (L/100km)",
    "Target (L/100km)",
    "Desvio %",
]


async def generate_fuel_report_xlsx(
    db: AsyncSession,
    tenant_id: UUID,
    month: str,
) -> bytes:
    """ANA-02: Generate XLSX with one row per vehicle for the given month (YYYY-MM).

    Highlights rows with Desvio % > 20 in red. Includes a second sheet with
    weekly cost evolution.
    """
    year, mon = int(month[:4]), int(month[5:7])
    _, last_day = calendar.monthrange(year, mon)
    # Timezone-aware boundaries — fuel_date and closed_at are timestamptz
    ts_start = datetime(year, mon, 1, tzinfo=UTC)
    ts_end = datetime(year, mon, last_day, 23, 59, 59, tzinfo=UTC)

    # Query active vehicles for this tenant
    vehicles = (
        (
            await db.execute(
                select(Vehicle)
                .where(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.status == "active",
                )
                .limit(500)
            )
        )
        .scalars()
        .all()
    )

    # Fuel aggregates per vehicle for the month
    fuel_rows = (
        await db.execute(
            select(
                FuelLog.vehicle_id,
                func.coalesce(func.sum(FuelLog.liters), 0).label("total_liters"),
                func.coalesce(func.sum(FuelLog.total_cost), 0).label("total_cost"),
            )
            .where(
                FuelLog.tenant_id == tenant_id,
                FuelLog.fuel_date >= ts_start,
                FuelLog.fuel_date <= ts_end,
            )
            .group_by(FuelLog.vehicle_id)
        )
    ).all()
    fuel_map = {str(r.vehicle_id): r for r in fuel_rows}

    # Total km per vehicle from closed trips in the month
    km_rows = (
        await db.execute(
            select(
                Trip.vehicle_id,
                func.coalesce(func.sum(Trip.km_end - Trip.km_start), 0).label("total_km"),
            )
            .where(
                Trip.tenant_id == tenant_id,
                Trip.status == "closed",
                Trip.closed_at >= ts_start,
                Trip.closed_at <= ts_end,
                Trip.km_end.isnot(None),
                Trip.km_start.isnot(None),
            )
            .group_by(Trip.vehicle_id)
        )
    ).all()
    km_map = {str(r.vehicle_id): float(r.total_km) for r in km_rows}

    # Weekly cost evolution (fuel_date grouped by ISO week)
    weekly_rows = (
        await db.execute(
            select(
                func.extract("week", FuelLog.fuel_date).label("week_num"),
                func.coalesce(func.sum(FuelLog.total_cost), 0).label("week_cost"),
            )
            .where(
                FuelLog.tenant_id == tenant_id,
                FuelLog.fuel_date >= ts_start,
                FuelLog.fuel_date <= ts_end,
            )
            .group_by(func.extract("week", FuelLog.fuel_date))
            .order_by(func.extract("week", FuelLog.fuel_date))
        )
    ).all()

    wb = Workbook()

    # ── Sheet 1: Per-vehicle summary ─────────────────────────────────────────
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet()
    ws.title = f"Combustível {month}"

    for col_idx, col_name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, vehicle in enumerate(vehicles, start=2):
        vid = str(vehicle.id)
        fuel = fuel_map.get(vid)
        total_liters = float(fuel.total_liters) if fuel else 0.0
        total_cost = float(fuel.total_cost) if fuel else 0.0
        total_km = km_map.get(vid, 0.0)
        target = (
            float(vehicle.avg_consumption_target)
            if vehicle.avg_consumption_target is not None
            else None
        )

        consumption = round((total_liters / total_km) * 100, 2) if total_km > 0 else None
        if consumption is not None and target is not None and target > 0:
            desvio = round(((consumption - target) / target) * 100, 1)
        else:
            desvio = None

        row_data = [
            vehicle.plate,
            round(total_liters, 2),
            round(total_cost, 2),
            consumption,
            target,
            desvio,
        ]
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx == 6 and desvio is not None and desvio > 20:
                cell.fill = RED_FILL

    for col_idx in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 22

    # ── Sheet 2: Weekly cost evolution ───────────────────────────────────────
    ws2 = wb.create_sheet(title="Evolução Semanal")
    week_headers = ["Semana", "Custo Total (MZN)"]
    for col_idx, col_name in enumerate(week_headers, start=1):
        cell = ws2.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, wr in enumerate(weekly_rows, start=2):
        ws2.cell(row=row_idx, column=1, value=int(wr.week_num))
        ws2.cell(row=row_idx, column=2, value=round(float(wr.week_cost), 2))

    for col_idx in range(1, 3):
        ws2.column_dimensions[get_column_letter(col_idx)].width = 22

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
