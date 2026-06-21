"""ROTAS workshop document exporter — Ordem de Serviço PDF (fpdf2 + DejaVuSans).

Design: PHC institutional layout — issuer left, vehicle box right,
grey metadata bar, diagnosis/tasks sections, dual signature block.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"

_NAV = (16, 32, 51)
_SOFT = (245, 247, 250)
_LINE = (216, 222, 232)
_INK = (23, 32, 51)
_MUTED = (102, 112, 133)
_WHITE = (255, 255, 255)
_GREEN = (22, 121, 76)
_RED = (185, 28, 28)


def _phc_issuer_col(
    pdf: FPDF, profile: dict | None, *, x: float, y: float, w: float = 110
) -> float:
    """Draw issuer block in left column. Returns new Y position after block."""
    p = profile or {}
    pdf.set_xy(x, y)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(w, 6, p.get("legal_name") or "—", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for field in ("address_line1", "address_line2", "city", "phone", "email"):
        val = p.get(field)
        if val:
            pdf.set_xy(x, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(w, 4, val, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)
    return pdf.get_y()


def _money(v: object) -> str:
    return f"{Decimal(str(v or 0)):,.2f} MZN"


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


class _WorkOrderPDF(FPDF):
    """FPDF2 subclass for work order PDFs."""

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

    def section_header(self, label: str) -> None:
        self.set_fill_color(*_NAV)
        self.set_text_color(*_WHITE)
        self.set_font("DejaVu", "B", 8)
        self.cell(0, 6, label, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*_INK)
        self.ln(1)

    def kv_row(self, label: str, value: str, w_label: float = 55) -> None:
        self.set_font("DejaVu", "B", 8)
        self.cell(w_label, 5, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def render_work_order(
    work_order: object,
    tasks: list | None = None,
    vehicle: dict | None = None,
    profile: dict | None = None,
) -> bytes:
    """Generate Ordem de Serviço PDF with PHC layout.

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

    total_pages_ref: list[int] = [1]
    pdf = _WorkOrderPDF(total_pages_ref)
    pdf.add_page()

    # ── PHC 2-col header ──────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    issuer_bottom = _phc_issuer_col(pdf, profile, x=x_left, y=header_y, w=LEFT_W)

    # Right box: VIATURA
    v = vehicle or {}
    plate = v.get("plate", "—")
    brand_model = " ".join(filter(None, [v.get("brand"), v.get("model")])) or "—"
    km = f"{v.get('current_km', '—')} km"

    box_h = 32.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    pdf.set_xy(x_right, header_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(RIGHT_W, 6, "VIATURA", fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for lbl, val in [("Matrícula", plate), ("Modelo", brand_model), ("Odómetro", km)]:
        pdf.set_xy(x_right + 2, pdf.get_y())
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(22, 5, f"{lbl}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(RIGHT_W - 24, 5, str(val)[:30], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(max(issuer_bottom, header_y + box_h) + 3)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    wo_num = g(work_order, "work_order_number")
    wo_status = g(work_order, "status")
    created = _date(_get(work_order, "created_at"))
    closed = _date(_get(work_order, "closed_at"))
    priority = g(work_order, "priority")

    bar_y = pdf.get_y()
    bar_h = 9.0
    pdf.set_fill_color(*_SOFT)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.rect(15, bar_y, 180, bar_h, "FD")

    pdf.set_xy(17, bar_y + 1.5)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    meta = (
        f"N.º OS: {wo_num}  |  Data: {created}  |  Fecho: {closed}"
        f"  |  Estado: {wo_status}  |  Prioridade: {priority}"
    )
    pdf.cell(120, 6, meta[:100], align="L")

    pdf.set_xy(135, bar_y + 1.5)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_NAV)
    pdf.cell(58, 6, "ORDEM DE SERVIÇO", align="R")
    pdf.set_text_color(*_INK)
    pdf.set_y(bar_y + bar_h + 3)

    # ── Diagnosis ─────────────────────────────────────────────────────────────
    pdf.section_header("DIAGNÓSTICO")
    diagnosis = str(_get(work_order, "diagnosis") or "—")
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(0, 5, diagnosis, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # ── Planned work ──────────────────────────────────────────────────────────
    pdf.section_header("TRABALHO PLANEADO")
    planned = str(_get(work_order, "planned_work") or "—")
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(0, 5, planned, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # ── Tasks table ───────────────────────────────────────────────────────────
    if tasks:
        pdf.section_header("TAREFAS")
        TASK_COLS = [10.0, 95.0, 30.0, 23.0, 22.0]
        TASK_HDRS = ["#", "Descrição", "Estado", "H. Est.", "H. Real"]
        TASK_ALNS = ["C", "L", "C", "C", "C"]

        pdf.set_fill_color(*_SOFT)
        pdf.set_text_color(*_INK)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.3)
        for w, hdr, aln in zip(TASK_COLS, TASK_HDRS, TASK_ALNS, strict=False):
            pdf.cell(w, 6, hdr, border=1, fill=True, align=aln, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln()

        for idx, task in enumerate(tasks):
            fill = idx % 2 == 0
            pdf.set_fill_color(*(_SOFT if fill else _WHITE))
            pdf.set_font("DejaVu", "", 7)
            desc = str(_get(task, "description") or "—")[:55]
            t_status = str(_get(task, "status") or "—")
            est_min = _get(task, "estimated_minutes")
            real_min = _get(task, "actual_minutes")
            est_str = f"{int(est_min) // 60}h{int(est_min) % 60:02d}m" if est_min else "—"
            real_str = f"{int(real_min) // 60}h{int(real_min) % 60:02d}m" if real_min else "—"
            row_vals = [str(idx + 1), desc, t_status, est_str, real_str]
            for val, w, aln in zip(row_vals, TASK_COLS, TASK_ALNS, strict=False):
                pdf.cell(
                    w, 6, val, border=1, fill=fill, align=aln, new_x=XPos.RIGHT, new_y=YPos.TOP
                )
            pdf.ln()
        pdf.ln(3)

    # ── Cost totals 2-col ─────────────────────────────────────────────────────
    cost_y = pdf.get_y()
    COL_L = 87.0
    GAP = 6.0
    COL_R = 87.0
    x_lc = 15.0
    x_rc = x_lc + COL_L + GAP

    # Left: cost kv rows
    labor = Decimal(str(_get(work_order, "labor_cost") or 0))
    estimated = Decimal(str(_get(work_order, "estimated_cost") or 0))
    actual = Decimal(str(_get(work_order, "actual_cost") or 0))

    pdf.set_xy(x_lc, cost_y)
    pdf.section_header("CUSTOS")
    pdf.set_xy(x_lc, pdf.get_y())
    pdf.kv_row("Mão-de-Obra", _money(labor), w_label=60)
    pdf.set_xy(x_lc, pdf.get_y())
    pdf.kv_row("Total Estimado", _money(estimated), w_label=60)
    pdf.set_xy(x_lc, pdf.get_y())
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(60, 5, "Total Real:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_text_color(*(_GREEN if actual <= estimated else _RED))
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(0, 5, _money(actual), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)
    left_bottom = pdf.get_y()

    # Right: close notes
    pdf.set_xy(x_rc, cost_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(COL_R, 6, "NOTAS DE ENCERRAMENTO", fill=True, align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)
    pdf.set_xy(x_rc, pdf.get_y())
    notes = str(_get(work_order, "close_notes") or "—")
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(COL_R, 5, notes, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    right_bottom = pdf.get_y()

    pdf.set_y(max(left_bottom, right_bottom) + 5)

    # ── Dual signature block ──────────────────────────────────────────────────
    pdf.section_header("APROVAÇÃO E FECHO")
    pdf.ln(3)
    sig_y = pdf.get_y()
    SIG_COL = 85.0

    for i, (label, _name_attr, date_attr) in enumerate([
        ("Aprovado por", "approved_by", "approved_at"),
        ("Encerrado por", "closed_by", "closed_at"),
    ]):
        x = 15 + i * (SIG_COL + 10)
        closed_date = _date(_get(work_order, date_attr))
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.3)
        pdf.line(x, sig_y + 18, x + SIG_COL, sig_y + 18)
        pdf.set_xy(x, sig_y + 19)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(SIG_COL, 4, label)
        pdf.set_xy(x, sig_y + 23)
        pdf.set_font("DejaVu", "", 6)
        pdf.set_text_color(*_MUTED)
        pdf.cell(SIG_COL, 3, f"Data: {closed_date}")

    pdf.set_text_color(*_INK)
    total_pages_ref[0] = pdf.pages
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
