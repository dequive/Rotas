"""ROTAS billing exporters — professional PDF (fpdf2 + DejaVuSans) and XLSX (openpyxl).

Design goals:
- PDF: A4 portrait, ROTAS institutional branding, clear document hierarchy,
  subtotal/total section, page footer.
- XLSX: metadata header block, styled table with dark header row, total row,
  freeze panes, column borders.
- UTF-8: DejaVuSans covers full Latin Extended range — Portuguese diacritics
  (ã ç â ê é ô) and Mozambican names render without corruption.
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
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.modules.billing.models import BillingDocument, BillingItem

FONTS_DIR = Path(__file__).parent / "fonts"

# ── Brand palette ────────────────────────────────────────────────────────────
_NAV = (16, 32, 51)  # #102033 — deep navy (sidebar colour)
_SOFT = (245, 247, 250)  # #F5F7FA — light background
_LINE = (216, 222, 232)  # #D8DEE8 — subtle divider
_INK = (23, 32, 51)  # #172033 — body text
_MUTED = (102, 112, 133)  # #667085 — secondary text
_WHITE = (255, 255, 255)
_GREEN = (22, 121, 76)  # #16794C
_ORANGE = (180, 83, 9)  # #B45309

# ── Document type labels (Portuguese fiscal) ─────────────────────────────────
_DOC_TYPE_LABELS = {
    "invoice": "FATURA",
    "debit_note": "NOTA DE DÉBITO",
    "credit_note": "NOTA DE CRÉDITO",
    "receipt": "RECIBO",
    "invoice_receipt": "FATURA-RECIBO",
}


def _doc_type_label(document: BillingDocument) -> str:
    """Return the correct Portuguese fiscal label for this document.

    Draft documents are labelled PROFORMA — no fiscal value.
    """
    if document.status == "draft":
        return "PROFORMA — SEM VALOR FISCAL"
    return _DOC_TYPE_LABELS.get(document.document_type, "DOCUMENTO DE COBRANÇA")


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
    """Generate PDF or XLSX billing document.

    issuer_name and issuer_nuit are pulled from document columns (populated at
    create_document time from the Tenant record). No caller arguments needed.
    """
    issuer_name = document.issuer_name or "ROTAS"
    issuer_nuit = document.issuer_nuit
    # Show NUIT as the contact/subtitle line in header and footer
    issuer_contact = f"NUIT {issuer_nuit}" if issuer_nuit else None

    if export_format == "pdf":
        return _render_pdf(document, items, issuer_name=issuer_name, issuer_contact=issuer_contact)
    return _render_xlsx(document, items, issuer_name=issuer_name)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _money(value, currency: str = "MZN") -> str:
    amount = Decimal(str(value or 0))
    return f"{amount:,.2f} {currency}"


def _money_val(value) -> Decimal:
    return Decimal(str(value or 0))


def _date(value: datetime | None, fmt: str = "%d/%m/%Y") -> str:
    if not isinstance(value, datetime):
        return "—"
    return value.strftime(fmt)


def _status_label(status: str | None) -> str:
    labels = {
        "draft": "Rascunho",
        "issued": "Emitido",
        "paid": "Pago",
        "cancelled": "Cancelado",
        "overdue": "Em atraso",
    }
    return labels.get(status or "", (status or "").title())


# ── PDF ───────────────────────────────────────────────────────────────────────


class _RotasPDF(FPDF):
    """FPDF subclass with tenant-branded header and footer."""

    def __init__(
        self,
        doc_number: str,
        issue_date: str,
        issuer_name: str,
        issuer_contact: str | None,
        doc_type: str,
    ):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._doc_number = doc_number
        self._issue_date = issue_date
        self._issuer_name = issuer_name
        self._issuer_contact = issuer_contact
        self._doc_type = doc_type
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(left=15, top=15, right=15)

    def header(self):
        # ── Navy header band ────────────────────────────────────────────────
        self.set_fill_color(*_NAV)
        self.rect(0, 0, 210, 22, "F")

        self.set_y(4)
        self.set_text_color(*_WHITE)
        self.set_font("DejaVu", "B", 16)
        self.cell(0, 8, self._issuer_name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if self._issuer_contact:
            self.set_font("DejaVu", "", 7)
            self.set_y(12)
            self.cell(0, 4, self._issuer_contact, align="L")

        # ── Document title band (lighter) ────────────────────────────────────
        self.set_fill_color(*_SOFT)
        self.set_draw_color(*_LINE)
        self.rect(0, 22, 210, 12, "FD")
        self.set_y(25)
        self.set_text_color(*_INK)
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 6, self._doc_type, align="C")

        # ── Doc number + issue date (top-right) ──────────────────────────────
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.set_y(25)
        self.cell(0, 3, f"N.º {self._doc_number}   |   Emitido em {self._issue_date}", align="R")

        self.set_y(36)
        self.set_text_color(*_INK)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        footer_left = self._issuer_name
        if self._issuer_contact:
            footer_left += f"  |  {self._issuer_contact}"
        self.cell(0, 5, footer_left, align="L")
        self.cell(0, 5, f"Página {self.page_no()}", align="R")


def _render_pdf(
    document: BillingDocument,
    items: list[BillingItem],
    *,
    issuer_name: str = "ROTAS",
    issuer_contact: str | None = None,
) -> ExportArtifact:
    currency = document.currency or "MZN"
    # E1: use invoice_number for doc_number; fallback to UUID prefix only for drafts
    doc_number = document.invoice_number or str(document.id)[:8].upper()
    issue_date = _date(document.issued_at or document.created_at)

    pdf = _RotasPDF(
        doc_number=doc_number,
        issue_date=issue_date,
        issuer_name=issuer_name,
        issuer_contact=issuer_contact,
        doc_type=_doc_type_label(document),  # E2: correct type label / PROFORMA for draft
    )
    pdf.add_page()

    # ── Metadata block ────────────────────────────────────────────────────────
    period = f"{_date(document.billing_period_start)} — {_date(document.billing_period_end)}"

    def _meta_row(label: str, value: str):
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(35, 5, label.upper(), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _meta_row("Cliente", document.client_name or "—")
    # E4: render client NUIT when present (isinstance guards against MagicMock in tests)
    if isinstance(document.client_nuit, str) and document.client_nuit:
        _meta_row("NUIT do Cliente", document.client_nuit)
    _meta_row("Contrato", document.contract_reference or "—")
    _meta_row("Período de faturação", period)
    # E6: show due_date when present and is a real datetime
    if isinstance(document.due_date, datetime):
        _meta_row("Data de vencimento", _date(document.due_date))
    # E3: "Estado do documento" row removed — status is shown via document type label

    # Horizontal divider
    pdf.ln(3)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ── Table ─────────────────────────────────────────────────────────────────
    COL_W = [22, 36, 36, 44, 16, 10, 26, 26]  # total = 216 — fits A4 portrait 180mm
    # Normalise to page width (180mm usable)
    usable = 180
    scale = usable / sum(COL_W)
    COL_W = [round(w * scale, 1) for w in COL_W]

    HEADERS = [
        "Data",
        "Origem",
        "Destino",
        "Carga / Descrição",
        "Estado",
        "Qtd",
        f"Unit. {currency}",
        f"Total {currency}",
    ]

    # Header row
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7.5)
    ALIGN = ["C", "L", "L", "L", "C", "C", "R", "R"]
    for w, label, align in zip(COL_W, HEADERS, ALIGN, strict=False):
        pdf.cell(w, 7, label, border=0, fill=True, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # Data rows
    pdf.set_font("DejaVu", "", 7.5)
    grand_total = Decimal(0)

    for idx, item in enumerate(items):
        fill = idx % 2 == 0
        pdf.set_fill_color(*(_SOFT if fill else _WHITE))
        pdf.set_text_color(*_INK)

        amount = _money_val(item.amount)
        grand_total += amount

        values = [
            (_date(item.delivered_at), "C"),
            ((item.origin or "—")[:20], "L"),
            ((item.destination or "—")[:20], "L"),
            ((item.cargo_description or "—")[:26], "L"),
            ((item.load_state or "—")[:8], "C"),
            (str(item.quantity or 1), "C"),
            (_money(item.unit_price, ""), "R"),
            (_money(amount, ""), "R"),
        ]
        row_h = 6
        for w, (text, align) in zip(COL_W, values, strict=False):
            pdf.cell(
                w, row_h, text, border=0, fill=fill, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP
            )
        pdf.ln()

    # ── Totals block ─────────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # FISC-02: Three-line totals block — SUBTOTAL / IVA / TOTAL COM IVA
    label_w = sum(COL_W[:6])
    val_w = COL_W[6] + COL_W[7]

    subtotal = _money_val(document.subtotal) if document.subtotal else grand_total
    tax_amount = _money_val(document.tax_amount) if document.tax_amount else Decimal(0)
    total_amount = (
        _money_val(document.total_amount) if document.total_amount else subtotal + tax_amount
    )

    # Wave A: iva_rate=None raises ValueError — no silent fallback to 17
    if document.iva_rate is None:
        raise ValueError("iva_rate is NULL on issued document — cannot render export")
    iva_pct = int(float(document.iva_rate) * 100)
    iva_label = f"IVA ({iva_pct}%)"

    def _totals_row(label: str, value: Decimal, bold: bool = False, fill_color=_SOFT):
        pdf.set_fill_color(*fill_color)
        pdf.set_text_color(*_INK)
        pdf.set_font("DejaVu", "B" if bold else "", 9)
        pdf.cell(label_w, 7, label, fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(
            val_w,
            7,
            f"{value:,.2f} {currency}",
            fill=True,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    _totals_row("SUBTOTAL", subtotal)
    _totals_row(iva_label, tax_amount)
    pdf.ln(1)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(15 + label_w, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(1)
    _totals_row("TOTAL COM IVA", total_amount, bold=True, fill_color=_NAV)
    # Fix text colour for the nav-fill row (white on dark)
    # Re-render with correct colours since _totals_row uses _INK
    pdf.set_y(pdf.get_y() - 7)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(label_w, 7, "TOTAL COM IVA", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        val_w,
        7,
        f"{total_amount:,.2f} {currency}",
        fill=True,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    # ── Payment conditions note ───────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        5,
        "Este documento foi gerado automaticamente pelo sistema ROTAS. "
        "Qualquer contestação deve ser comunicada no prazo de 10 dias úteis após a emissão.",
        align="L",
    )

    # E7: filename uses invoice_number
    filename = f"fatura_{document.invoice_number or str(document.id)[:8]}.pdf"
    return ExportArtifact(filename=filename, content_type="application/pdf", content=pdf.output())


# ── XLSX ──────────────────────────────────────────────────────────────────────


def _xlsx_fill(hex_rgb: str) -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=hex_rgb)


def _xlsx_border(style: str = "thin") -> Border:
    s = Side(border_style=style, color="D8DEE8")
    return Border(left=s, right=s, top=s, bottom=s)


def _render_xlsx(
    document: BillingDocument,
    items: list[BillingItem],
    *,
    issuer_name: str = "ROTAS",
) -> ExportArtifact:
    currency = document.currency or "MZN"
    wb = Workbook()
    ws = wb.active
    ws.title = "Cobrança"

    # ── Branding / document metadata block ───────────────────────────────────
    ws.merge_cells("A1:H1")
    title_cell = ws["A1"]
    # E2: correct document type label in title; E5: issuer_name from document
    title_cell.value = f"{issuer_name} — {_doc_type_label(document)}"
    title_cell.font = Font(bold=True, size=14, color="FFFFFF")
    title_cell.fill = _xlsx_fill("102033")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    def _meta(row: int, label: str, value: str):
        label_cell = ws.cell(row=row, column=1, value=label)
        label_cell.font = Font(bold=True, size=9, color="667085")
        ws.merge_cells(f"A{row}:B{row}")

        val_cell = ws.cell(row=row, column=3, value=value)
        val_cell.font = Font(size=9, color="172033")
        ws.merge_cells(f"C{row}:H{row}")

    period = f"{_date(document.billing_period_start)} — {_date(document.billing_period_end)}"
    _meta(2, "Cliente", document.client_name or "—")
    # E4: render client NUIT when present (check isinstance to guard against MagicMock in tests)
    client_nuit_str = document.client_nuit if isinstance(document.client_nuit, str) else None
    due_date_val = document.due_date if not isinstance(document.due_date, type(None)) else None

    next_row = 3
    if client_nuit_str:
        _meta(next_row, "NUIT do Cliente", client_nuit_str)
        next_row += 1
    _meta(next_row, "Contrato", document.contract_reference or "—")
    next_row += 1
    _meta(next_row, "Período", period)
    next_row += 1
    # E6: show due_date when present and is a real datetime
    if due_date_val is not None and isinstance(due_date_val, datetime):
        _meta(next_row, "Data de vencimento", _date(due_date_val))
        next_row += 1
    # E3: "Estado" row removed from metadata block
    _meta(next_row, "Emitido em", _date(document.issued_at or document.created_at))
    next_row += 1

    # Spacer
    ws.row_dimensions[next_row].height = 6
    next_row += 1

    # ── Table header ──────────────────────────────────────────────────────────
    HEADER_ROW = next_row
    DATA_START = HEADER_ROW + 1
    HEADERS = [
        "Data descarga",
        "Origem",
        "Destino",
        "Carga / Descrição",
        "Estado carga",
        "Qtd",
        f"Unit. {currency}",
        f"Total {currency}",
    ]
    COL_WIDTHS = [14, 22, 22, 34, 14, 8, 20, 20]

    header_fill = _xlsx_fill("102033")
    header_font = Font(bold=True, size=9, color="FFFFFF")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, (header, width) in enumerate(zip(HEADERS, COL_WIDTHS, strict=False), start=1):
        cell = ws.cell(row=HEADER_ROW, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = _xlsx_border()
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[HEADER_ROW].height = 22

    # ── Data rows ─────────────────────────────────────────────────────────────
    CURRENCY_FMT = f'#,##0.00" {currency}"'
    grand_total = Decimal(0)

    even_fill = _xlsx_fill("F5F7FA")
    odd_fill = _xlsx_fill("FFFFFF")

    for row_offset, item in enumerate(items):
        row = DATA_START + row_offset
        fill = even_fill if row_offset % 2 == 0 else odd_fill
        amount = _money_val(item.amount)
        grand_total += amount

        values = [
            (item.delivered_at.strftime("%d/%m/%Y") if item.delivered_at else "—", None),
            (item.origin or "—", None),
            (item.destination or "—", None),
            (item.cargo_description or "—", None),
            (item.load_state or "—", None),
            (item.quantity or 1, None),
            (float(_money_val(item.unit_price)), CURRENCY_FMT),
            (float(amount), CURRENCY_FMT),
        ]
        ALIGNS = ["center", "left", "left", "left", "center", "center", "right", "right"]

        for col_idx, ((val, num_fmt), h_align) in enumerate(
            zip(values, ALIGNS, strict=False), start=1
        ):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.font = Font(size=9)
            cell.fill = fill
            cell.border = _xlsx_border()
            cell.alignment = Alignment(horizontal=h_align, vertical="center")
            if num_fmt:
                cell.number_format = num_fmt

        ws.row_dimensions[row].height = 16

    # ── FISC-02: Three totals rows — SUBTOTAL / IVA / TOTAL COM IVA ──────────
    subtotal_val = float(_money_val(document.subtotal)) if document.subtotal else float(grand_total)
    tax_val = float(_money_val(document.tax_amount)) if document.tax_amount else 0.0
    total_val = (
        float(_money_val(document.total_amount))
        if document.total_amount
        else subtotal_val + tax_val
    )
    # Wave A: iva_rate=None raises ValueError — no silent fallback to 17
    if document.iva_rate is None:
        raise ValueError("iva_rate is NULL on issued document — cannot render export")
    iva_pct = int(float(document.iva_rate) * 100)

    def _totals_xlsx_row(
        row: int, label: str, value: float, bold: bool = False, dark: bool = False
    ):
        ws.merge_cells(f"A{row}:G{row}")
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = Font(bold=bold, size=9, color="FFFFFF" if dark else "172033")
        lc.fill = _xlsx_fill("102033" if dark else "F5F7FA")
        lc.alignment = Alignment(horizontal="right", vertical="center")
        lc.border = _xlsx_border()
        vc = ws.cell(row=row, column=8, value=value)
        vc.font = Font(bold=bold, size=9, color="FFFFFF" if dark else "172033")
        vc.fill = _xlsx_fill("102033" if dark else "F5F7FA")
        vc.number_format = CURRENCY_FMT
        vc.alignment = Alignment(horizontal="right", vertical="center")
        vc.border = _xlsx_border()
        ws.row_dimensions[row].height = 18

    subtotal_row = DATA_START + len(items)
    iva_row = subtotal_row + 1
    total_row = subtotal_row + 2

    _totals_xlsx_row(subtotal_row, "SUBTOTAL", subtotal_val)
    _totals_xlsx_row(iva_row, f"IVA ({iva_pct}%)", tax_val)
    _totals_xlsx_row(total_row, "TOTAL COM IVA", total_val, bold=True, dark=True)

    # Freeze panes below header row so data scrolls but header stays
    ws.freeze_panes = ws.cell(row=DATA_START, column=1)

    output = BytesIO()
    wb.save(output)
    # E7: filename uses invoice_number
    filename = f"fatura_{document.invoice_number or str(document.id)[:8]}.xlsx"
    return ExportArtifact(
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content=output.getvalue(),
    )
