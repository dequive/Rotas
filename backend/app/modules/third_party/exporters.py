"""ROTAS supplier account statement exporter — PHC layout (fpdf2 + DejaVuSans)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"

# ── Brand palette ─────────────────────────────────────────────────────────────
_NAV = (16, 32, 51)
_SOFT = (245, 247, 250)
_LINE = (216, 222, 232)
_INK = (23, 32, 51)
_MUTED = (102, 112, 133)
_WHITE = (255, 255, 255)
_GREEN = (22, 121, 76)
_RED = (185, 28, 28)

_SOURCE_LABELS: dict[str, str] = {
    "manual_payment": "Pagamento manual",
    "fuel_purchase": "Combustível",
    "work_order": "Ordem de serviço",
    "invoice": "Fatura",
    "adjustment": "Ajuste",
}


def _get(obj: object, attr: str, default: str = "—") -> str:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return str(obj.get(attr) or default)
    return str(getattr(obj, attr, None) or default)


def _money(v: object) -> str:
    try:
        return f"{Decimal(str(v or 0)):,.2f} MZN"
    except Exception:
        return "0.00 MZN"


def _fmt_date(d: object) -> str:
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    if isinstance(d, str) and d:
        return d[:10]
    return "—"


class _StatementPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(0, 4, "Documento Processado por Computador — ROTAS", align="L")
        self.cell(0, 4, f"Página {self.page_no()} de {{nb}}", align="R")


def render_supplier_statement(
    third_party: object,
    entries: list[dict],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    opening_balance: str | None = None,
    total_debits: str = "0.00",
    total_credits: str = "0.00",
    balance: str = "0.00",
    profile: dict | None = None,
) -> bytes:
    pdf = _StatementPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.alias_nb_pages()
    pdf.add_page()

    LM = pdf.l_margin  # 10mm
    PW = pdf.w - LM - pdf.r_margin  # ~277mm landscape

    # ── Header bar ────────────────────────────────────────────────────────────
    pdf.set_fill_color(*_NAV)
    pdf.rect(LM, 10, PW, 10, style="F")
    pdf.set_xy(LM + 3, 10)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_WHITE)
    pdf.cell(PW - 6, 10, "EXTRATO DE CONTA CORRENTE", align="L")

    # ── Two-column block: issuer (left) | supplier box (right) ────────────────
    y0 = 24.0
    col_w = PW / 2 - 4

    # Left: issuer
    pdf.set_xy(LM, y0)
    p = profile or {}
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(col_w, 5, p.get("legal_name") or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for field in ("address_line1", "address_line2", "city", "phone", "email"):
        val = p.get(field)
        if val:
            pdf.set_xy(LM, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(col_w, 4, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Right: supplier box
    box_x = LM + col_w + 8
    box_y = y0
    box_w = col_w
    box_h = 32.0

    pdf.set_draw_color(*_LINE)
    pdf.set_fill_color(*_SOFT)
    pdf.rect(box_x, box_y, box_w, box_h, style="FD")

    pdf.set_xy(box_x + 3, box_y + 3)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(box_w - 6, 4, "FORNECEDOR / PRESTADOR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(box_x + 3, pdf.get_y())
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    tp_name = _get(third_party, "name")
    pdf.cell(box_w - 6, 6, tp_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    trade = _get(third_party, "trade_name", "")
    if trade and trade != "—":
        pdf.set_xy(box_x + 3, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(box_w - 6, 4, trade, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    nuit = _get(third_party, "nuit", "")
    if nuit and nuit != "—":
        pdf.set_xy(box_x + 3, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(box_w - 6, 4, f"NUIT: {nuit}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    meta_y = max(pdf.get_y(), box_y + box_h) + 4
    pdf.set_fill_color(*_SOFT)
    pdf.set_draw_color(*_LINE)
    pdf.rect(LM, meta_y, PW, 8, style="FD")
    pdf.set_xy(LM + 3, meta_y + 2)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_MUTED)

    period_str = "Todos os movimentos"
    if date_from and date_to:
        period_str = f"Período: {_fmt_date(date_from)} a {_fmt_date(date_to)}"
    elif date_from:
        period_str = f"A partir de: {_fmt_date(date_from)}"
    elif date_to:
        period_str = f"Até: {_fmt_date(date_to)}"

    today_str = _fmt_date(date.today())
    meta_cells = [
        ("Emissão", today_str),
        ("Período", period_str),
        ("Moeda", "MZN"),
    ]
    cell_w = PW / len(meta_cells)
    for label, val in meta_cells:
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(cell_w / 2, 4, f"{label}:", align="L")
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(cell_w / 2, 4, val, align="L")

    # ── Opening balance row ────────────────────────────────────────────────────
    table_y = meta_y + 12
    if opening_balance is not None:
        ob_val = Decimal(str(opening_balance or "0"))
        pdf.set_xy(LM, table_y)
        pdf.set_fill_color(*_SOFT)
        pdf.rect(LM, table_y, PW, 6, style="F")
        pdf.set_xy(LM + 3, table_y + 1)
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(PW * 0.55, 4, "SALDO DE ABERTURA DO PERÍODO")
        pdf.set_font("DejaVu", "B", 8)
        color = _GREEN if ob_val >= 0 else _RED
        pdf.set_text_color(*color)
        pdf.cell(PW * 0.45, 4, _money(ob_val), align="R")
        table_y += 8

    # ── Table header ──────────────────────────────────────────────────────────
    COL = {
        "data":    (0,    PW * 0.09),
        "tipo":    (0.09, PW * 0.08),
        "origem":  (0.17, PW * 0.13),
        "desc":    (0.30, PW * 0.30),
        "debito":  (0.60, PW * 0.13),
        "credito": (0.73, PW * 0.13),
        "saldo":   (0.86, PW * 0.14),
    }

    pdf.set_fill_color(*_NAV)
    pdf.rect(LM, table_y, PW, 7, style="F")
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_WHITE)

    headers = [
        ("data", "DATA", "L"),
        ("tipo", "TIPO", "L"),
        ("origem", "ORIGEM", "L"),
        ("desc", "DESCRIÇÃO", "L"),
        ("debito", "DÉBITO", "R"),
        ("credito", "CRÉDITO", "R"),
        ("saldo", "SALDO", "R"),
    ]
    for key, label, align in headers:
        off, w = COL[key]
        pdf.set_xy(LM + PW * off + 2, table_y + 1.5)
        pdf.cell(w - 2, 4, label, align=align)  # type: ignore[arg-type]

    table_y += 7

    # ── Table rows ─────────────────────────────────────────────────────────────
    running = Decimal(str(opening_balance or "0"))
    odd = False

    for entry in entries:
        if pdf.get_y() > pdf.h - 30:
            pdf.add_page()
            table_y = pdf.get_y()

        row_y = pdf.get_y()
        row_h = 6.0

        # Alternating row background
        if odd:
            pdf.set_fill_color(*_SOFT)
            pdf.rect(LM, row_y, PW, row_h, style="F")
        odd = not odd

        amount = Decimal(str(entry.get("amount") or "0"))
        etype = entry.get("entry_type", "")
        if etype == "credit":
            running += amount
            debit_str = ""
            credit_str = f"{amount:,.2f}"
        else:
            running -= amount
            debit_str = f"{amount:,.2f}"
            credit_str = ""

        src = entry.get("source_type", "")
        origem = _SOURCE_LABELS.get(src, src)[:30]
        cells = [
            ("data",    entry.get("entry_date", "")[:10], "L"),
            ("tipo",    "Crédito" if etype == "credit" else "Débito", "L"),
            ("origem",  origem, "L"),
            ("desc",    entry.get("description") or "—", "L"),
            ("debito",  debit_str, "R"),
            ("credito", credit_str, "R"),
            ("saldo",   f"{running:,.2f}", "R"),
        ]

        pdf.set_font("DejaVu", "", 7.5)
        for key, val, align in cells:
            off, w = COL[key]
            pdf.set_xy(LM + PW * off + 2, row_y + 1)

            # Colour the running balance
            if key == "saldo":
                pdf.set_text_color(*(_GREEN if running >= 0 else _RED))
            elif key == "credito" and credit_str:
                pdf.set_text_color(*_GREEN)
            elif key == "debito" and debit_str:
                pdf.set_text_color(*_RED)
            else:
                pdf.set_text_color(*_INK)

            pdf.cell(w - 2, row_h - 1, str(val)[:60], align=align)  # type: ignore[arg-type]

        # Bottom border
        pdf.set_draw_color(*_LINE)
        pdf.line(LM, row_y + row_h, LM + PW, row_y + row_h)
        pdf.set_y(row_y + row_h)

    # ── Totals footer ──────────────────────────────────────────────────────────
    totals_y = pdf.get_y() + 4
    pdf.set_fill_color(*_NAV)
    pdf.rect(LM, totals_y, PW, 8, style="F")
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_WHITE)

    td = Decimal(str(total_debits or "0"))
    tc = Decimal(str(total_credits or "0"))
    bal = Decimal(str(balance or "0"))

    totals = [
        (0.0,  PW * 0.60, "TOTAIS DO PERÍODO", "L"),
        (0.60, PW * 0.13, f"- {td:,.2f}", "R"),
        (0.73, PW * 0.13, f"+ {tc:,.2f}", "R"),
        (0.86, PW * 0.14, f"{bal:,.2f}", "R"),
    ]
    for off, w, label, align in totals:
        pdf.set_xy(LM + PW * off + 2, totals_y + 2)
        pdf.cell(w - 2, 4, label, align=align)  # type: ignore[arg-type]

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
