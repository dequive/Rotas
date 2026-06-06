"""ROTAS billing exporters — UTF-8 safe PDF (fpdf2 + DejaVuSans) and XLSX (openpyxl).

Replaces hand-rolled latin-1 implementation that corrupted Mozambican names with diacritics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.modules.billing.models import BillingDocument, BillingItem

FONTS_DIR = Path(__file__).parent / "fonts"


@dataclass(frozen=True)
class ExportArtifact:
    filename: str
    content_type: str
    content: bytes


def render_billing_export(
    document: BillingDocument,
    items: list[BillingItem],
    export_format: str,
) -> ExportArtifact:
    if export_format == "pdf":
        return _render_pdf(document, items)
    return _render_xlsx(document, items)


def _money(value, currency: str = "MZN") -> str:
    amount = Decimal(str(value or 0))
    return f"{amount:,.2f} {currency}"


def _date(value: datetime | None) -> str:
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d")


def _render_pdf(document: BillingDocument, items: list[BillingItem]) -> ExportArtifact:
    """Generate UTF-8 safe PDF using fpdf2 + DejaVuSans TTF font.

    DejaVuSans covers the full Latin Extended range — Portuguese diacritics
    (ã ç â ê é ô) render correctly. Font path is absolute (relative to this file),
    not the process CWD, so it works in both FastAPI and ARQ worker contexts.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(auto=True, margin=10)

    # Header
    pdf.add_page()
    pdf.set_fill_color(16, 32, 51)  # --nav #102033
    pdf.rect(0, 0, 297, 20, "F")
    pdf.set_y(4)
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "ROTAS — Documento de Cobrança de Transporte", align="L")

    # Document metadata
    pdf.set_y(24)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(50, 5, "Cliente", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 5, "Contrato", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 5, "Período", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(40, 5, "Estado", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("DejaVu", "", 10)
    period = f"{_date(document.billing_period_start)} a {_date(document.billing_period_end)}"
    pdf.cell(50, 7, document.client_name or "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 7, document.contract_reference or "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 7, period, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(40, 7, (document.status or "").upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Table header
    pdf.set_y(pdf.get_y() + 4)
    pdf.set_fill_color(219, 234, 254)  # light blue
    pdf.set_font("DejaVu", "B", 8)
    headers = [
        (20, "Data"),
        (35, "Origem"),
        (35, "Destino"),
        (50, "Carga"),
        (20, "Estado"),
        (15, "Qtd"),
        (30, "Unitário MZN"),
        (30, "Total MZN"),
    ]
    for width, label in headers:
        pdf.cell(width, 7, label, border=0, fill=True, align="C")
    pdf.ln()

    # Table rows
    pdf.set_font("DejaVu", "", 8)
    for idx, item in enumerate(items):
        fill = idx % 2 == 0
        if fill:
            pdf.set_fill_color(248, 250, 252)
        values = [
            (20, _date(item.delivered_at), "C"),
            (35, (item.origin or "-")[:18], "L"),
            (35, (item.destination or "-")[:18], "L"),
            (50, (item.cargo_description or "-")[:28], "L"),
            (20, item.load_state or "-", "C"),
            (15, str(item.quantity or 1), "R"),
            (30, _money(item.unit_price, document.currency or "MZN"), "R"),
            (30, _money(item.amount, document.currency or "MZN"), "R"),
        ]
        for width, text, align in values:
            pdf.cell(width, 6, text, border=0, fill=fill, align=align)
        pdf.ln()

    filename = f"cobranca_{document.id}.pdf"
    return ExportArtifact(filename=filename, content_type="application/pdf", content=pdf.output())


def _render_xlsx(document: BillingDocument, items: list[BillingItem]) -> ExportArtifact:
    """Generate XLSX using openpyxl — bold headers, #,##0.00 for currency columns."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cobrança"

    # Header row — bold
    headers = ["Data descarga", "Origem", "Destino", "Carga", "Estado", "Qtd", "Preço unit. MZN", "Total MZN"]
    col_widths = [14, 20, 20, 30, 12, 8, 18, 18]
    for col_idx, (header, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        ws.column_dimensions[cell.column_letter].width = width

    # Data rows
    for row_idx, item in enumerate(items, start=2):
        ws.cell(row=row_idx, column=1, value=_date(item.delivered_at))
        ws.cell(row=row_idx, column=2, value=item.origin or "-")
        ws.cell(row=row_idx, column=3, value=item.destination or "-")
        ws.cell(row=row_idx, column=4, value=item.cargo_description or "-")
        ws.cell(row=row_idx, column=5, value=item.load_state or "-")
        ws.cell(row=row_idx, column=6, value=item.quantity or 1)

        price_cell = ws.cell(row=row_idx, column=7, value=float(item.unit_price or 0))
        price_cell.number_format = "#,##0.00"
        price_cell.alignment = Alignment(horizontal="right")

        total_cell = ws.cell(row=row_idx, column=8, value=float(item.amount or 0))
        total_cell.number_format = "#,##0.00"
        total_cell.alignment = Alignment(horizontal="right")

    output = BytesIO()
    wb.save(output)
    filename = f"cobranca_{document.id}.xlsx"
    return ExportArtifact(
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=output.getvalue(),
    )
