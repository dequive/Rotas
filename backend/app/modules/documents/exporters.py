"""ROTAS generic procurement document exporters — clean typographic layout.

Design principles:
- Black ink only: no filled rectangles, no coloured bands.
- Thin 0.2 mm rules for structure.
- Document box (type + ref + date) with a simple border, top-right corner.
- Entity block: plain text, no box.
- Items table: clean borders, no background fill on data rows.
- Totals: right-aligned block, bold total line.
- Signatures: two simple horizontal rules with label beneath.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"

_INK = (23, 32, 51)
_MUTED = (102, 112, 133)
_LINE = (180, 188, 200)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def _fmt(v: object, decimals: int = 2) -> str:
    try:
        n = Decimal(str(v or 0))
        fmt = f"{{:,.{decimals}f}}"
        return fmt.format(n)
    except Exception:
        return "—"


def _date_pt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        from datetime import date
        d = date.fromisoformat(str(iso)[:10])
        months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                  "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return f"{d.day:02d} {months[d.month - 1]}. {d.year}"
    except Exception:
        return str(iso)[:10]


class _CleanPDF(FPDF):
    """Base class for all clean procurement PDFs."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(left=18, top=18, right=18)
        self.alias_nb_pages()

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-11)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(0, 4, "Documento Processado por Computador — ROTAS", align="L")
        self.cell(0, 4, f"Página {self.page_no()} de {{nb}}", align="R")


def _header_block(
    pdf: _CleanPDF,
    profile: dict | None,
    doc_type_line1: str,
    doc_type_line2: str,
    reference: str,
    date_str: str,
) -> float:
    """Draw the two-column document header.

    Left: issuer name + contact (typographic, no box).
    Right: small bordered box with document type + reference + date.
    Returns Y position after the section rule.
    """
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    y0 = pdf.get_y()

    LEFT_W = PW * 0.58
    RIGHT_W = PW * 0.38
    RIGHT_X = LM + PW - RIGHT_W

    # ── Left: issuer ──────────────────────────────────────────────────────────
    p = profile or {}
    pdf.set_xy(LM, y0)
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(*_INK)
    pdf.cell(LEFT_W, 7, p.get("legal_name") or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for field in ("address_line1", "address_line2", "city", "phone", "email"):
        val = p.get(field)
        if val:
            pdf.set_xy(LM, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(LEFT_W, 4, str(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    issuer_bottom = pdf.get_y()

    # ── Right: document type box ──────────────────────────────────────────────
    BOX_H = 34.0
    pdf.set_draw_color(*_INK)
    pdf.set_line_width(0.4)
    pdf.rect(RIGHT_X, y0, RIGHT_W, BOX_H)

    # Title line 1
    pdf.set_xy(RIGHT_X, y0 + 4)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(RIGHT_W, 5, doc_type_line1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if doc_type_line2:
        pdf.set_xy(RIGHT_X, pdf.get_y())
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(RIGHT_W, 5, doc_type_line2, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Thin rule inside box
    sep_y = y0 + 15
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(RIGHT_X + 3, sep_y, RIGHT_X + RIGHT_W - 3, sep_y)

    pdf.set_xy(RIGHT_X, sep_y + 2)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(RIGHT_W, 4, "Nº REFERÊNCIA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(RIGHT_X, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(RIGHT_W, 5, reference[:30], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(RIGHT_X, pdf.get_y() + 1)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(RIGHT_W, 4, date_str, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Horizontal rule below header ──────────────────────────────────────────
    rule_y = max(issuer_bottom, y0 + BOX_H) + 4
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)
    pdf.set_text_color(*_INK)

    return pdf.get_y()


def _entity_block(
    pdf: _CleanPDF,
    label: str,
    name: str,
    contact: str | None = None,
    nuit: str | None = None,
) -> float:
    """Draw supplier / recipient plain-text block. Returns new Y."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(LM, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, name[:80], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if contact:
        pdf.set_xy(LM, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(PW, 4, contact[:200], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if nuit:
        pdf.set_xy(LM, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 4, f"NUIT: {nuit}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Thin rule below entity
    rule_y = pdf.get_y() + 3
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 5)
    pdf.set_text_color(*_INK)

    return pdf.get_y()


def _items_table(
    pdf: _CleanPDF,
    items: list[dict],
    show_price: bool = True,
) -> tuple[Decimal, Decimal]:
    """Draw items table. Returns (subtotal, total) as Decimal.

    items: list of dicts with keys: description, quantity, unit, unit_price (optional).
    """
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    # Column widths — adjust if no price column
    if show_price:
        C = {"num": 8, "desc": PW - 8 - 22 - 16 - 24 - 28, "qty": 22, "unit": 16,
             "price": 24, "total": 28}
    else:
        C = {"num": 8, "desc": PW - 8 - 22 - 16 - 0 - 0, "qty": 22, "unit": 16,
             "price": 0, "total": 0}

    hdrs = ["#", "DESCRIÇÃO", "QTD.", "UNID."]
    cols = [C["num"], C["desc"], C["qty"], C["unit"]]
    alns: list[str] = ["C", "L", "R", "C"]
    if show_price:
        hdrs += ["P. UNIT.", "TOTAL"]
        cols += [C["price"], C["total"]]
        alns += ["R", "R"]

    # ── Table header row ──────────────────────────────────────────────────────
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_INK)

    row_h = 6.0
    x0 = LM
    y0 = pdf.get_y()

    # Bottom border for header
    for w, hdr, aln in zip(cols, hdrs, alns, strict=False):
        pdf.set_xy(x0, y0)
        pdf.cell(w, row_h, hdr, border="B", align=aln)  # type: ignore[arg-type]
        x0 += w
    pdf.ln()

    # ── Data rows ─────────────────────────────────────────────────────────────
    subtotal = Decimal("0")
    pdf.set_font("DejaVu", "", 8.5)
    pdf.set_text_color(*_INK)

    for idx, item in enumerate(items):
        desc = str(item.get("description") or "—")
        qty = _d(item.get("quantity"))
        unit = str(item.get("unit") or "unid.")
        unit_price = _d(item.get("unit_price")) if show_price else Decimal("0")
        line_total = qty * unit_price if show_price and unit_price else Decimal("0")
        subtotal += line_total

        # Estimate row height for multi-line description
        desc_lines = max(1, len(desc) // 50 + (1 if len(desc) % 50 else 0))
        rh = max(row_h, desc_lines * 4.5)

        if pdf.get_y() + rh > pdf.h - 30:
            pdf.add_page()

        x0 = LM
        row_y = pdf.get_y()

        vals = [str(idx + 1), desc, _fmt(qty, 0 if qty == int(qty) else 3), unit]
        if show_price:
            vals += [_fmt(unit_price), _fmt(line_total)]

        for i, (w, val, aln) in enumerate(zip(cols, vals, alns, strict=False)):
            pdf.set_xy(x0, row_y)
            if i == 1:  # description — multi-cell
                pdf.multi_cell(w, 4.5, val, border="B", align="L",  # type: ignore[arg-type]
                                new_x=XPos.RIGHT, new_y=YPos.TOP)
            else:
                pdf.set_xy(x0, row_y)
                pdf.cell(w, rh, val, border="B", align=aln)  # type: ignore[arg-type]
            x0 += w

        pdf.set_y(row_y + rh)

    return subtotal, subtotal


def _totals_block(
    pdf: _CleanPDF,
    total: Decimal,
    currency: str = "MZN",
    extra_rows: list[tuple[str, str]] | None = None,
) -> None:
    """Draw right-aligned totals block."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    label_w = 45.0
    val_w = 32.0
    x_label = LM + PW - label_w - val_w
    pdf.ln(3)

    if extra_rows:
        for label, val in extra_rows:
            pdf.set_xy(x_label, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(label_w, 5, label, align="R")
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_INK)
            pdf.cell(val_w, 5, val, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Thin rule before total
    rule_y = pdf.get_y() + 1
    pdf.set_draw_color(*_INK)
    pdf.set_line_width(0.3)
    pdf.line(x_label, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 2)

    pdf.set_xy(x_label, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(label_w, 6, f"TOTAL {currency}", align="R")
    pdf.cell(val_w, 6, f"{_fmt(total)}", align="R",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _notes_block(pdf: _CleanPDF, notes: str, extra_kv: list[tuple[str, str]] | None = None) -> None:
    """Draw optional notes and extra key-value pairs (payment terms, deadline, etc.)."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    if extra_kv:
        pdf.ln(6)
        for label, val in extra_kv:
            pdf.set_font("DejaVu", "B", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(40, 5, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_INK)
            pdf.cell(PW - 40, 5, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if notes:
        pdf.ln(4)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 4, "OBSERVAÇÕES", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(PW, 4.5, notes, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _signature_block(
    pdf: _CleanPDF,
    left_label: str = "Responsável pela Requisição",
    right_label: str = "Aprovação",
) -> None:
    """Draw two-column signature block near bottom."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    pdf.ln(14)
    sig_y = pdf.get_y()
    col = PW / 2 - 8

    pdf.set_draw_color(*_INK)
    pdf.set_line_width(0.3)
    pdf.line(LM, sig_y, LM + col, sig_y)
    pdf.line(LM + col + 16, sig_y, LM + PW, sig_y)

    pdf.set_xy(LM, sig_y + 2)
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(col, 4, left_label, align="C")
    pdf.set_x(LM + col + 16)
    pdf.cell(col, 4, right_label, align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(LM, pdf.get_y() + 1)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(col, 4, "Data: _____ / _____ / _________", align="C")
    pdf.set_x(LM + col + 16)
    pdf.cell(col, 4, "Data: _____ / _____ / _________", align="C")


# ── Public render functions ───────────────────────────────────────────────────


def render_purchase_order(
    *,
    reference: str,
    date: str,
    supplier_name: str,
    supplier_contact: str | None = None,
    supplier_nuit: str | None = None,
    items: list[dict],
    notes: str | None = None,
    currency: str = "MZN",
    payment_terms: str | None = None,
    delivery_deadline: str | None = None,
    profile: dict | None = None,
) -> bytes:
    """Generate Ordem de Compra PDF — generic, any product or service.

    items: list of dicts with description, quantity, unit, unit_price.
    Returns raw PDF bytes.
    """
    pdf = _CleanPDF()
    pdf.add_page()

    _header_block(pdf, profile, "ORDEM DE COMPRA", "", reference, _date_pt(date))
    _entity_block(pdf, "Fornecedor", supplier_name, supplier_contact, supplier_nuit)

    _items_table(pdf, items, show_price=True)

    total_items = sum(_d(i.get("unit_price", 0)) * _d(i.get("quantity", 0)) for i in items)
    _totals_block(pdf, total_items, currency=currency)

    extra_kv = []
    if payment_terms:
        extra_kv.append(("Condições de Pagamento", payment_terms))
    if delivery_deadline:
        extra_kv.append(("Prazo de Entrega", delivery_deadline))

    _notes_block(pdf, notes or "", extra_kv=extra_kv or None)
    _signature_block(pdf, "Responsável pela Requisição", "Gestor / Aprovação")

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def render_requisition(
    *,
    req_type: str,
    reference: str,
    date: str,
    entity_name: str,
    entity_contact: str | None = None,
    entity_nuit: str | None = None,
    requester_department: str | None = None,
    items: list[dict],
    notes: str | None = None,
    currency: str = "MZN",
    profile: dict | None = None,
) -> bytes:
    """Generate Requisição Interna or Requisição Externa PDF — generic.

    req_type: 'internal' or 'external'.
    For internal: entity is the requesting department/unit.
    For external: entity is the external supplier.
    items: list of dicts with description, quantity, unit, unit_price (optional for internal).
    Returns raw PDF bytes.
    """
    is_internal = req_type == "internal"
    title_line1 = "REQUISIÇÃO"
    title_line2 = "INTERNA" if is_internal else "EXTERNA"
    entity_label = "Destino / Departamento" if is_internal else "Fornecedor / Prestador"
    left_sig = "Requisitante" if is_internal else "Responsável pela Requisição"
    right_sig = "Responsável de Armazém" if is_internal else "Aprovação / Gestor"
    show_price = not is_internal

    pdf = _CleanPDF()
    pdf.add_page()

    _header_block(pdf, profile, title_line1, title_line2, reference, _date_pt(date))

    if requester_department:
        _entity_block(pdf, "Departamento Requisitante", requester_department)

    _entity_block(pdf, entity_label, entity_name, entity_contact, entity_nuit)
    _items_table(pdf, items, show_price=show_price)

    if show_price:
        total_items = sum(_d(i.get("unit_price", 0)) * _d(i.get("quantity", 0)) for i in items)
        _totals_block(pdf, total_items, currency=currency)

    _notes_block(pdf, notes or "")
    _signature_block(pdf, left_sig, right_sig)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
