"""ROTAS workshop document exporters — Ordem de Serviço PDF (fpdf2 + DejaVuSans).

Design: clean typographic layout — no coloured fills, no nav bars.
Thin 0.2 mm rules for structure; issuer left, doc box right (border only).
"""

from __future__ import annotations

from datetime import datetime
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _d(v: object) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def _fmt(v: object, decimals: int = 2) -> str:
    try:
        return f"{Decimal(str(v or 0)):,.{decimals}f}"
    except Exception:
        return "—"


def _money(v: object, currency: str = "MZN") -> str:
    return f"{_d(v):,.2f} {currency}"


def _date(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and value:
        return value[:10]
    return "—"


def _get(obj: object, attr: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


# ── Base PDF class ────────────────────────────────────────────────────────────


class _CleanPDF(FPDF):
    """Base class for clean workshop PDFs — typographic footer, no fills."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(left=15, top=15, right=15)
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


# ── Layout primitives ─────────────────────────────────────────────────────────


def _header_block(
    pdf: _CleanPDF,
    profile: dict | None,
    doc_type: str,
    reference: str,
    date_str: str,
) -> None:
    """Two-column header: issuer left (typographic), doc box right (border only)."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    y0 = pdf.get_y()

    LEFT_W = PW * 0.58
    RIGHT_W = PW * 0.38
    RIGHT_X = LM + PW - RIGHT_W

    # Left: issuer
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

    # Right: bordered document box (no fill)
    BOX_H = 34.0
    pdf.set_draw_color(*_INK_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(RIGHT_X, y0, RIGHT_W, BOX_H)

    pdf.set_xy(RIGHT_X, y0 + 4)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(RIGHT_W, 5, doc_type, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    sep_y = y0 + 14
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

    # Rule below header
    rule_y = max(issuer_bottom, y0 + BOX_H) + 4
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)
    pdf.set_text_color(*_INK)


def _section(pdf: _CleanPDF, label: str) -> None:
    """Muted small-caps label + 0.2 mm rule. Replaces coloured section_header."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    pdf.ln(3)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, pdf.get_y(), LM + PW, pdf.get_y())
    pdf.set_y(pdf.get_y() + 3)
    pdf.set_text_color(*_INK)


def _kv(pdf: _CleanPDF, label: str, value: str, w_label: float = 55) -> None:
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(w_label, 5, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _two_kv(
    pdf: _CleanPDF,
    l_label: str,
    l_val: str,
    r_label: str,
    r_val: str,
    lw: float = 45,
    lv: float = 55,
    rw: float = 35,
) -> None:
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(lw, 5, l_label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_INK)
    pdf.cell(lv, 5, l_val or "—", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(rw, 5, r_label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, r_val or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _sig_block(pdf: _CleanPDF, labels: list[str], cols: int = 2) -> None:
    """Draw N equally-spaced signature lines near bottom."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    pdf.ln(12)
    sig_y = pdf.get_y()
    col_w = PW / cols
    for i, label in enumerate(labels):
        x = LM + i * col_w
        line_end = x + col_w - 8
        pdf.set_draw_color(*_INK_LINE)
        pdf.set_line_width(0.3)
        pdf.line(x, sig_y, line_end, sig_y)
        pdf.set_xy(x, sig_y + 2)
        pdf.set_font("DejaVu", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(col_w - 8, 4, label, align="C")
        pdf.set_xy(x, sig_y + 7)
        pdf.set_font("DejaVu", "", 6.5)
        pdf.cell(col_w - 8, 4, "Data: _____ / _____ / _________", align="C")
    pdf.set_text_color(*_INK)


# ── Public render functions ───────────────────────────────────────────────────


def render_work_order(
    work_order: object,
    tasks: list | None = None,
    vehicle: dict | None = None,
    profile: dict | None = None,
) -> bytes:
    """Generate Ordem de Serviço PDF — clean typographic layout.

    work_order: WorkOrder ORM object or dict-like.
    tasks: list of WorkOrderTask ORM objects or dicts.
    vehicle: dict with keys plate, brand, model, current_km.
    profile: TenantDocumentProfile dict for issuer header.
    Returns raw PDF bytes.
    """
    tasks = tasks or []

    def g(obj: object, attr: str) -> str:
        val = _get(obj, attr)
        return str(val) if val is not None else "—"

    pdf = _CleanPDF()
    pdf.add_page()

    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin

    wo_num = g(work_order, "work_order_number")
    created = _date(_get(work_order, "created_at"))
    _header_block(pdf, profile, "ORDEM DE SERVIÇO", wo_num, created)

    # ── Vehicle info block ────────────────────────────────────────────────────
    v = vehicle or {}
    plate = v.get("plate", "—")
    brand_model = " ".join(filter(None, [v.get("brand"), v.get("model")])) or "—"
    km = str(v.get("current_km", "—"))

    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, "VIATURA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, plate, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Two-column sub-block: model | odómetro
    _two_kv(pdf, "Modelo", brand_model, "Odómetro", f"{km} km", lw=20, lv=80, rw=28)

    # Metadata row: status | priority | closed
    wo_status = g(work_order, "status")
    priority = g(work_order, "priority")
    closed = _date(_get(work_order, "closed_at"))
    _two_kv(pdf, "Estado", wo_status, "Prioridade", priority, lw=20, lv=80, rw=28)
    _kv(pdf, "Fecho", closed, w_label=20)

    # Rule below vehicle block
    rule_y = pdf.get_y() + 3
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    _section(pdf, "Diagnóstico")
    diagnosis = str(_get(work_order, "diagnosis") or "—")
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5, diagnosis, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Planned work ──────────────────────────────────────────────────────────
    _section(pdf, "Trabalho Planeado")
    planned = str(_get(work_order, "planned_work") or "—")
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(0, 5, planned, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Tasks table ───────────────────────────────────────────────────────────
    if tasks:
        _section(pdf, "Tarefas")
        TCOLS = [10.0, 95.0, 30.0, 23.0, 22.0]
        THDRS = ["#", "Descrição", "Estado", "H. Est.", "H. Real"]
        TALNS = ["C", "L", "C", "C", "C"]
        row_h = 6.0

        # Header row — bottom border only, no fill
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_INK)
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.2)
        x0 = LM
        y0 = pdf.get_y()
        for w, hdr, aln in zip(TCOLS, THDRS, TALNS, strict=False):
            pdf.set_xy(x0, y0)
            pdf.cell(w, row_h, hdr, border="B", align=aln)  # type: ignore[arg-type]
            x0 += w
        pdf.ln()

        pdf.set_font("DejaVu", "", 7)
        for idx, task in enumerate(tasks):
            desc = str(_get(task, "description") or "—")[:55]
            t_status = str(_get(task, "status") or "—")
            est_min = _get(task, "estimated_minutes")
            real_min = _get(task, "actual_minutes")
            est_str = f"{int(est_min) // 60}h{int(est_min) % 60:02d}m" if est_min else "—"
            real_str = f"{int(real_min) // 60}h{int(real_min) % 60:02d}m" if real_min else "—"
            row_vals = [str(idx + 1), desc, t_status, est_str, real_str]
            x0 = LM
            ry = pdf.get_y()
            for val, w, aln in zip(row_vals, TCOLS, TALNS, strict=False):
                pdf.set_xy(x0, ry)
                pdf.cell(w, row_h, val, border="B", align=aln)  # type: ignore[arg-type]
                x0 += w
            pdf.ln()

    # ── Costs ─────────────────────────────────────────────────────────────────
    _section(pdf, "Custos")
    labor = _d(_get(work_order, "labor_cost"))
    estimated = _d(_get(work_order, "estimated_cost"))
    actual = _d(_get(work_order, "actual_cost"))

    _kv(pdf, "Mão-de-Obra", _money(labor))
    _kv(pdf, "Total Estimado", _money(estimated))

    # Total Real: green if within budget, red if over
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(55, 5, "Total Real:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_text_color(*(_GREEN if actual <= estimated else _RED))
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(0, 5, _money(actual), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)

    # ── Close notes ───────────────────────────────────────────────────────────
    close_notes = str(_get(work_order, "close_notes") or "")
    if close_notes and close_notes not in ("—", "None"):
        _section(pdf, "Notas de Encerramento")
        pdf.set_font("DejaVu", "", 8)
        pdf.multi_cell(0, 5, close_notes, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Dual signature block ──────────────────────────────────────────────────
    _section(pdf, "Aprovação e Fecho")

    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    pdf.ln(10)
    sig_y = pdf.get_y()
    SIG_COL = PW / 2 - 5

    for i, (label, date_attr) in enumerate(
        [
            ("Aprovado por", "approved_at"),
            ("Encerrado por", "closed_at"),
        ]
    ):
        x = LM + i * (SIG_COL + 10)
        date_val = _date(_get(work_order, date_attr))
        pdf.set_draw_color(*_INK_LINE)
        pdf.set_line_width(0.3)
        pdf.line(x, sig_y, x + SIG_COL, sig_y)
        pdf.set_xy(x, sig_y + 2)
        pdf.set_font("DejaVu", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(SIG_COL, 4, label, align="C")
        pdf.set_xy(x, sig_y + 7)
        pdf.set_font("DejaVu", "", 6.5)
        pdf.cell(SIG_COL, 4, f"Data: {date_val}", align="C")

    pdf.set_text_color(*_INK)
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ── Spare-part movement labels ────────────────────────────────────────────────

_MOVEMENT_TITLES: dict[str, str] = {
    "receipt": "REQUISIÇÃO EXTERNA DE PEÇAS",
    "work_order_issue": "REQUISIÇÃO INTERNA DE PEÇAS",
    "adjustment": "AJUSTE DE INVENTÁRIO",
    "serial_install": "INSTALAÇÃO DE PEÇA SÉRIE",
    "serial_remove": "REMOÇÃO DE PEÇA SÉRIE",
}

_MOVEMENT_DIRECTION_LABELS = {
    "in": "Entrada",
    "out": "Saída",
}

_MOVEMENT_TYPE_LABELS = {
    "receipt": "Receção de Fornecedor",
    "work_order_issue": "Emissão para Ordem de Serviço",
    "adjustment": "Ajuste Manual",
    "serial_install": "Instalação de Série",
    "serial_remove": "Remoção de Série",
}


def render_spare_part_movement(
    movement: object,
    part: object | None = None,
    *,
    profile: dict | None = None,
) -> bytes:
    """Generate Requisição Interna / Requisição Externa PDF — clean typographic layout.

    movement: SparePartMovement ORM object or dict.
    part:     SparePartInventory ORM object or dict (for SKU/name/category).
    profile:  TenantDocumentProfile dict for issuer header.
    Returns raw PDF bytes.
    """
    mov_type = _get(movement, "movement_type") or "receipt"
    title = _MOVEMENT_TITLES.get(str(mov_type), "MOVIMENTAÇÃO DE PEÇAS")

    pdf = _CleanPDF()
    pdf.add_page()

    ref_val = str(_get(movement, "request_reference") or "—")
    occurred = _date(_get(movement, "occurred_at"))
    _header_block(pdf, profile, title, ref_val, occurred)

    # ── Part info block ───────────────────────────────────────────────────────
    sku = _get(part, "sku") if part else "—"
    name = _get(part, "name") if part else "—"
    category = _get(part, "category") if part else ""

    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, "PEÇA / ARTIGO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, str(name)[:60], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, f"SKU: {sku}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if category and str(category) not in ("None", ""):
        pdf.set_font("DejaVu", "", 8)
        pdf.cell(0, 4, str(category), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Rule below part block
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    rule_y = pdf.get_y() + 3
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)

    # ── Movement details ──────────────────────────────────────────────────────
    _section(pdf, "Detalhes da Movimentação")

    direction_raw = str(_get(movement, "direction") or "")
    direction_label = _MOVEMENT_DIRECTION_LABELS.get(direction_raw, direction_raw.title())
    type_label = _MOVEMENT_TYPE_LABELS.get(str(mov_type), str(mov_type).replace("_", " ").title())

    qty = _get(movement, "quantity") or 0
    try:
        qty_fmt = f"{Decimal(str(qty)):,.4f}"
    except Exception:
        qty_fmt = str(qty)

    bal = _get(movement, "balance_after_quantity") or 0
    try:
        bal_fmt = f"{Decimal(str(bal)):,.4f}"
    except Exception:
        bal_fmt = str(bal)

    unit = _get(part, "unit") if part else "unid."
    unit_str = str(unit) if unit and str(unit) != "None" else "unid."

    _kv(pdf, "Tipo", type_label)
    _kv(pdf, "Direcção", direction_label)
    _kv(pdf, "Quantidade", f"{qty_fmt} {unit_str}")
    _kv(pdf, "Saldo Após Movimentação", f"{bal_fmt} {unit_str}")

    unit_cost = _get(movement, "unit_cost")
    total_cost = _get(movement, "total_cost")
    if unit_cost and str(unit_cost) not in ("None", "0", "0.00"):
        _kv(pdf, "Custo Unitário", _money(unit_cost))
    if total_cost and str(total_cost) not in ("None", "0", "0.00"):
        _kv(pdf, "Custo Total", _money(total_cost))

    source_type = _get(movement, "source_type") or ""
    source_id = _get(movement, "source_id") or ""
    if source_type and str(source_type) not in ("None", "—"):
        label = "Origem" if direction_raw == "in" else "Destino (OS)"
        _kv(pdf, label, str(source_type).replace("_", " ").title())
    if source_id and str(source_id) not in ("None", "—"):
        _kv(pdf, "ID Referência", str(source_id)[:40])

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes = str(_get(movement, "notes") or "")
    if notes and notes not in ("None", "—", ""):
        _section(pdf, "Observações")
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, notes, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Signature block ───────────────────────────────────────────────────────
    left_sig = "Responsável pelo Pedido" if direction_raw == "out" else "Responsável pela Receção"
    _sig_block(pdf, [left_sig, "Aprovação / Armazém"])

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
