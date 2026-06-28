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
    """FPDF2 subclass — PHC-style layout. Body rendered manually in _render_pdf."""

    def __init__(self, total_pages_ref: list[int]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._total_pages_ref = total_pages_ref
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=15, top=15, right=15)

    def header(self):
        if self.page_no() > 1:
            self.set_draw_color(*_LINE)
            self.set_line_width(0.3)
            self.line(15, 15, 195, 15)
            self.set_y(19)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(80, 5, "Documento Processado por Computador", align="L")
        self.set_font("DejaVu", "B", 7)
        self.cell(50, 5, "ROTAS", align="C")
        self.set_font("DejaVu", "", 7)
        total = self._total_pages_ref[0] if self._total_pages_ref else "?"
        self.cell(0, 5, f"Página {self.page_no()} de {total}", align="R")


def _render_pdf(
    document: BillingDocument,
    items: list[BillingItem],
    *,
    issuer_name: str = "ROTAS",
    issuer_contact: str | None = None,
) -> ExportArtifact:
    currency = document.currency or "MZN"
    doc_number = document.invoice_number or str(document.id)[:8].upper()
    issue_date = _date(document.issued_at or document.created_at)
    doc_label = _doc_type_label(document)

    if document.iva_rate is None:
        raise ValueError("iva_rate is NULL on issued document — cannot render export")
    iva_rate_val = float(document.iva_rate)
    iva_pct = int(iva_rate_val * 100)

    subtotal = _money_val(document.subtotal)
    tax_amount = _money_val(document.tax_amount)
    total_amount = (
        _money_val(document.total_amount) if document.total_amount else subtotal + tax_amount
    )
    commercial_disc = _money_val(getattr(document, "commercial_discount", None) or 0)
    financial_disc = _money_val(getattr(document, "financial_discount", None) or 0)

    total_pages_ref: list[int] = [1]
    pdf = _RotasPDF(total_pages_ref)
    pdf.add_page()

    # ── HEADER — 2 colunas ────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    # Coluna esquerda: dados do emitente
    pdf.set_xy(x_left, header_y)
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(*_INK)
    issuer_display = getattr(document, "issuer_name", None) or issuer_name
    pdf.cell(LEFT_W, 6, issuer_display, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    issuer_nuit_val = getattr(document, "issuer_nuit", None)
    if issuer_nuit_val:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            LEFT_W, 4, f"NUIT: {issuer_nuit_val}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    issuer_address = getattr(document, "issuer_address", None)
    if issuer_address:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(LEFT_W, 4, issuer_address, align="L")

    contact_parts = [
        p
        for p in [
            getattr(document, "issuer_phone", None),
            getattr(document, "issuer_email", None),
        ]
        if p
    ]
    if not contact_parts and issuer_contact:
        contact_parts = [issuer_contact]
    if contact_parts:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            LEFT_W, 4, "  |  ".join(contact_parts), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    issuer_bottom = pdf.get_y()

    # Coluna direita: box cliente com bordas
    box_h = 32.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    pdf.set_xy(x_right + 3, header_y + 3)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(
        RIGHT_W - 6,
        5,
        (document.client_name or "—")[:38],
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    client_nuit = getattr(document, "client_nuit", None)
    if isinstance(client_nuit, str) and client_nuit:
        pdf.set_xy(x_right + 3, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            RIGHT_W - 6,
            4,
            f"NUIT: {client_nuit}",
            align="L",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    contract_ref = getattr(document, "contract_reference", None)
    if contract_ref:
        pdf.set_xy(x_right + 3, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            RIGHT_W - 6,
            4,
            f"Contrato: {contract_ref[:28]}",
            align="L",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.set_y(max(issuer_bottom, header_y + box_h) + 3)

    # ── BARRA DE METADADOS ────────────────────────────────────────────────────
    bar_y = pdf.get_y()
    bar_h = 11.0
    pdf.set_fill_color(240, 242, 245)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.rect(15, bar_y, 180, bar_h, "FD")

    pdf.set_xy(17, bar_y + 2.5)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    due = _date(document.due_date) if isinstance(document.due_date, datetime) else "—"
    payment_conds = getattr(document, "payment_conditions", None) or "—"
    meta_str = (
        f"Data: {issue_date}  |  Vencimento: {due}"
        f"  |  Condições: {payment_conds}  |  Moeda: {currency}"
    )
    pdf.cell(105, 6, meta_str, align="L")

    # Número do documento em destaque
    pdf.set_xy(120, bar_y + 1.5)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(73, 8, f"{doc_label} N.º {doc_number}", align="R")

    pdf.set_y(bar_y + bar_h + 4)

    # ── TABELA DE ITENS ───────────────────────────────────────────────────────
    COL_W_RAW = [20, 74, 14, 26, 14, 32]
    scale = 180.0 / sum(COL_W_RAW)
    COL_W = [round(w * scale, 1) for w in COL_W_RAW]
    HEADERS_T = ["Referência", "Designação", "Quant.", "Pr. Unitário", "IVA%", f"Total {currency}"]
    ALIGNS_T = ["C", "L", "C", "R", "C", "R"]

    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7.5)
    for w, label, align in zip(COL_W, HEADERS_T, ALIGNS_T, strict=False):
        pdf.cell(w, 7, label, border=0, fill=True, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    pdf.set_font("DejaVu", "", 7.5)
    grand_total = Decimal(0)

    for idx, item in enumerate(items):
        row_fill = idx % 2 == 0
        pdf.set_fill_color(*(_SOFT if row_fill else _WHITE))
        pdf.set_text_color(*_INK)

        amount = _money_val(item.amount)
        grand_total += amount
        iva_rate_item = float(item.iva_rate) if item.iva_rate is not None else iva_rate_val
        iva_pct_item = int(iva_rate_item * 100)

        origin = item.origin or ""
        dest = item.destination or ""
        desig = f"{origin} → {dest}" if (origin or dest) else "—"
        if getattr(item, "cargo_description", None):
            desig = f"{desig} — {item.cargo_description[:60]}"

        row_vals = [
            ((getattr(item, "client_reference", None) or "—")[:14], "C"),
            (desig[:80], "L"),
            (str(item.quantity or 1), "C"),
            (_money(item.unit_price, ""), "R"),
            (f"{iva_pct_item}%", "C"),
            (_money(amount, ""), "R"),
        ]
        for w, (txt, aln) in zip(COL_W, row_vals, strict=False):
            pdf.cell(
                w, 6, txt, border=0, fill=row_fill, align=aln, new_x=XPos.RIGHT, new_y=YPos.TOP
            )
        pdf.ln()

    pdf.ln(3)

    # ── DADOS BANCÁRIOS ───────────────────────────────────────────────────────
    issuer_bank = getattr(document, "issuer_bank_details", None)
    if issuer_bank:
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(180, 4, f"Dados Bancários: {issuer_bank}", align="L")
        pdf.ln(2)

    # ── ZONA DE TOTAIS — 2 colunas ────────────────────────────────────────────
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)

    totals_y = pdf.get_y()
    LEFT_TOT = 87.0
    GAP = 6.0
    RIGHT_TOT = 180.0 - LEFT_TOT - GAP
    x_lt = 15.0
    x_rt = x_lt + LEFT_TOT + GAP

    # Coluna esquerda: tabela IVA por taxa
    col3 = [LEFT_TOT * 0.28, LEFT_TOT * 0.38, LEFT_TOT * 0.34]
    pdf.set_xy(x_lt, totals_y)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_WHITE)
    pdf.set_fill_color(*_NAV)
    for lbl, cw in zip(["Taxa", "Base de Incidência", "Valor do IVA"], col3, strict=False):
        pdf.cell(cw, 6, lbl, fill=True, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    pdf.set_xy(x_lt, pdf.get_y())
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*_INK)
    pdf.set_fill_color(*_SOFT)
    pdf.cell(col3[0], 5, f"{iva_pct}%", fill=True, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col3[1], 5, f"{subtotal:,.2f}", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        col3[2], 5, f"{tax_amount:,.2f}", fill=True, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )

    pdf.set_xy(x_lt, pdf.get_y())
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.cell(col3[0], 6, "Total de IVA", fill=False, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(
        col3[1], 6, f"{subtotal:,.2f}", fill=False, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP
    )
    pdf.cell(
        col3[2], 6, f"{tax_amount:,.2f}", fill=False, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    left_bottom = pdf.get_y()

    # Coluna direita: Valores do Documento
    pdf.set_xy(x_rt, totals_y)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_WHITE)
    pdf.set_fill_color(*_NAV)
    pdf.cell(
        RIGHT_TOT,
        6,
        "Valores do Documento",
        fill=True,
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    lw = RIGHT_TOT * 0.64
    vw = RIGHT_TOT * 0.36

    def _right_row(label: str, value: Decimal, bold: bool = False) -> None:
        pdf.set_xy(x_rt, pdf.get_y())
        pdf.set_font("DejaVu", "B" if bold else "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(lw, 5, label, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(vw, 5, f"{value:,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _right_row("Total antes de descontos:", subtotal + tax_amount)
    disc_pct = (
        int(float(commercial_disc / (subtotal or Decimal(1))) * 100) if commercial_disc else 0
    )
    _right_row(f"Desconto Comercial {disc_pct}%:", commercial_disc)
    _right_row("Desconto Financeiro:", financial_disc)
    _right_row("Total de IVA:", tax_amount)

    # Separador + linha TOTAL
    pdf.set_xy(x_rt, pdf.get_y() + 1)
    pdf.set_draw_color(*_LINE)
    pdf.line(x_rt, pdf.get_y(), x_rt + RIGHT_TOT, pdf.get_y())
    pdf.ln(1)
    pdf.set_xy(x_rt, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(lw, 7, f"TOTAL ({currency}):", align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(vw, 7, f"{total_amount:,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    right_bottom = pdf.get_y()

    pdf.set_y(max(left_bottom, right_bottom))

    total_pages_ref[0] = pdf.pages
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
