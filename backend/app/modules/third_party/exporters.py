"""ROTAS supplier account statement exporter — clean typographic layout (fpdf2 + DejaVuSans)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"

_INK = (23, 32, 51)
_MUTED = (102, 112, 133)
_LINE = (180, 188, 200)
_INK_LINE = (23, 32, 51)
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
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-11)
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

    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    # ── Two-column header: issuer left, supplier right (no fills) ─────────────
    y0 = pdf.get_y()
    col_w = PW / 2 - 4

    # Left: issuer
    p = profile or {}
    pdf.set_xy(LM, y0)
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(*_INK)
    pdf.cell(col_w, 7, p.get("legal_name") or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for field in ("address_line1", "address_line2", "city", "phone", "email"):
        val = p.get(field)
        if val:
            pdf.set_xy(LM, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(col_w, 4, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    issuer_bottom = pdf.get_y()

    # Right: doc box (border only — no fill)
    BOX_H = 36.0
    box_x = LM + col_w + 8
    BOX_W = col_w
    pdf.set_draw_color(*_INK_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(box_x, y0, BOX_W, BOX_H)

    pdf.set_xy(box_x, y0 + 3)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(BOX_W, 5, "EXTRATO DE CONTA CORRENTE", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    sep_y = y0 + 12
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(box_x + 3, sep_y, box_x + BOX_W - 3, sep_y)

    tp_name = _get(third_party, "name")
    pdf.set_xy(box_x, sep_y + 2)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(BOX_W, 4, "FORNECEDOR / PRESTADOR", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(box_x, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(BOX_W, 5, tp_name[:35], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    trade = _get(third_party, "trade_name", "")
    if trade and trade != "—":
        pdf.set_xy(box_x, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(BOX_W, 4, trade[:35], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    nuit = _get(third_party, "nuit", "")
    if nuit and nuit != "—":
        pdf.set_xy(box_x, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(BOX_W, 4, f"NUIT: {nuit}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Rule below header
    rule_y = max(issuer_bottom, y0 + BOX_H) + 4
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 3)
    pdf.set_text_color(*_INK)

    # ── Period metadata (plain text, no fill) ─────────────────────────────────
    period_str = "Todos os movimentos"
    if date_from and date_to:
        period_str = f"{_fmt_date(date_from)} a {_fmt_date(date_to)}"
    elif date_from:
        period_str = f"A partir de {_fmt_date(date_from)}"
    elif date_to:
        period_str = f"Até {_fmt_date(date_to)}"

    today_str = _fmt_date(date.today())
    meta_pairs = [
        ("Emissão", today_str),
        ("Período", period_str),
        ("Moeda", "MZN"),
    ]
    for label, val in meta_pairs:
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(25, 5, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(70, 5, val, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, pdf.get_y() + 2, LM + PW, pdf.get_y() + 2)
    pdf.set_y(pdf.get_y() + 5)

    # ── Opening balance (plain text, no fill) ─────────────────────────────────
    if opening_balance is not None:
        ob_val = Decimal(str(opening_balance or "0"))
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            PW * 0.65,
            5,
            "SALDO DE ABERTURA DO PERÍODO",
            align="L",
            new_x=XPos.RIGHT,
            new_y=YPos.TOP,
        )
        color = _GREEN if ob_val >= 0 else _RED
        pdf.set_text_color(*color)
        pdf.cell(PW * 0.35, 5, _money(ob_val), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)
        pdf.ln(2)

    # ── Table header (bottom border only, no fill) ────────────────────────────
    COL = {
        "data": (0, PW * 0.09),
        "tipo": (0.09, PW * 0.08),
        "origem": (0.17, PW * 0.13),
        "desc": (0.30, PW * 0.30),
        "debito": (0.60, PW * 0.13),
        "credito": (0.73, PW * 0.13),
        "saldo": (0.86, PW * 0.14),
    }

    headers = [
        ("data", "DATA", "L"),
        ("tipo", "TIPO", "L"),
        ("origem", "ORIGEM", "L"),
        ("desc", "DESCRIÇÃO", "L"),
        ("debito", "DÉBITO", "R"),
        ("credito", "CRÉDITO", "R"),
        ("saldo", "SALDO", "R"),
    ]
    header_y = pdf.get_y()
    row_h = 6.0
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    for key, label, align in headers:
        off, w = COL[key]
        pdf.set_xy(LM + PW * off, header_y)
        pdf.cell(w, row_h, label, border="B", align=align)  # type: ignore[arg-type]
    pdf.set_y(header_y + row_h)

    # ── Table rows ────────────────────────────────────────────────────────────
    running = Decimal(str(opening_balance or "0"))

    for entry in entries:
        if pdf.get_y() > pdf.h - 30:
            pdf.add_page()
            # Re-draw header on new page
            header_y = pdf.get_y()
            pdf.set_font("DejaVu", "B", 7.5)
            pdf.set_text_color(*_INK)
            for key, label, align in headers:
                off, w = COL[key]
                pdf.set_xy(LM + PW * off, header_y)
                pdf.cell(w, row_h, label, border="B", align=align)  # type: ignore[arg-type]
            pdf.set_y(header_y + row_h)

        row_y = pdf.get_y()
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
            ("data", entry.get("entry_date", "")[:10], "L"),
            ("tipo", "Crédito" if etype == "credit" else "Débito", "L"),
            ("origem", origem, "L"),
            ("desc", entry.get("description") or "—", "L"),
            ("debito", debit_str, "R"),
            ("credito", credit_str, "R"),
            ("saldo", f"{running:,.2f}", "R"),
        ]

        pdf.set_font("DejaVu", "", 7.5)
        for key, val, align in cells:
            off, w = COL[key]
            pdf.set_xy(LM + PW * off, row_y)
            if key == "saldo":
                pdf.set_text_color(*(_GREEN if running >= 0 else _RED))
            elif key == "credito" and credit_str:
                pdf.set_text_color(*_GREEN)
            elif key == "debito" and debit_str:
                pdf.set_text_color(*_RED)
            else:
                pdf.set_text_color(*_INK)
            pdf.cell(w, row_h, str(val)[:60], border="B", align=align)  # type: ignore[arg-type]

        pdf.set_y(row_y + row_h)

    # ── Totals row (plain text, bold, with rule above) ────────────────────────
    td = Decimal(str(total_debits or "0"))
    tc = Decimal(str(total_credits or "0"))
    bal = Decimal(str(balance or "0"))

    pdf.ln(3)
    totals_y = pdf.get_y()
    pdf.set_draw_color(*_INK_LINE)
    pdf.set_line_width(0.3)
    pdf.line(LM, totals_y, LM + PW, totals_y)
    pdf.set_y(totals_y + 2)

    totals = [
        (0.0, PW * 0.60, "TOTAIS DO PERÍODO", "L"),
        (0.60, PW * 0.13, f"- {td:,.2f}", "R"),
        (0.73, PW * 0.13, f"+ {tc:,.2f}", "R"),
        (0.86, PW * 0.14, f"{bal:,.2f}", "R"),
    ]
    pdf.set_font("DejaVu", "B", 8)
    for off, w, label, align in totals:
        x_pos = LM + PW * off
        pdf.set_xy(x_pos, pdf.get_y())
        if "+" in label:
            pdf.set_text_color(*_GREEN)
        elif "-" in label:
            pdf.set_text_color(*_RED)
        else:
            pdf.set_text_color(*_INK)
        pdf.cell(w, 6, label, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)  # type: ignore[arg-type]
    pdf.set_text_color(*_INK)

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
