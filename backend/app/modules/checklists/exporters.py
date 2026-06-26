"""ROTAS checklist document exporter — Inspecção de Viatura PDF (fpdf2 + DejaVuSans).

Design: PHC institutional layout — issuer left, vehicle/driver box right,
grey metadata bar, 2-column inspection grid with state pills, signature block.
"""

from __future__ import annotations

from datetime import datetime
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

_STATE_COLORS = {
    "ok": (_GREEN, _WHITE, "OK"),
    "nok": (_RED, _WHITE, "NOK"),
}
_STATE_DEFAULT = (_MUTED, _WHITE, "N/A")


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


def _date(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, str) and value:
        return value[:16]
    return "—"


def _get(obj: object, attr: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


class _ChecklistPDF(FPDF):
    """FPDF2 subclass for vehicle inspection PDFs."""

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


def render_checklist_report(
    checklist: object,
    template: object | None = None,
    vehicle: dict | None = None,
    driver: dict | None = None,
    profile: dict | None = None,
) -> bytes:
    """Generate Relatório de Inspecção de Viatura PDF with PHC layout.

    checklist: Checklist ORM object or dict-like.
    template: ChecklistTemplate ORM object or dict-like (optional).
    vehicle: dict with keys plate, brand, model.
    driver: dict with keys full_name.
    profile: TenantDocumentProfile dict for issuer header.
    Returns raw PDF bytes.
    """

    def g(obj: object, attr: str) -> str:
        val = _get(obj, attr)
        return str(val) if val is not None else "—"

    total_pages_ref: list[int] = [1]
    pdf = _ChecklistPDF(total_pages_ref)
    pdf.add_page()

    # ── PHC 2-col header ──────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    issuer_bottom = _phc_issuer_col(pdf, profile, x=x_left, y=header_y, w=LEFT_W)

    # Right box: VIATURA / MOTORISTA
    v = vehicle or {}
    d = driver or {}
    plate = v.get("plate", "—")
    brand_model = " ".join(filter(None, [v.get("brand"), v.get("model")])) or "—"
    driver_name = d.get("full_name", "—")

    loc_raw = _get(checklist, "location")
    if isinstance(loc_raw, dict):
        lat = loc_raw.get("lat")
        lon = loc_raw.get("lon")
        gps_str = f"{lat:.4f}, {lon:.4f}" if lat is not None and lon is not None else "—"
    else:
        gps_str = "—"

    box_h = 36.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    pdf.set_xy(x_right, header_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(
        RIGHT_W, 6, "VIATURA / MOTORISTA", fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )

    for lbl, val in [
        ("Matrícula", plate),
        ("Modelo", brand_model),
        ("Motorista", driver_name),
        ("GPS", gps_str),
    ]:
        pdf.set_xy(x_right + 2, pdf.get_y())
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(20, 5, f"{lbl}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(RIGHT_W - 22, 5, str(val)[:30], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(max(issuer_bottom, header_y + box_h) + 3)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    chk_type = g(checklist, "type")
    tmpl_name = g(template, "name") if template else "—"
    started_str = _date(_get(checklist, "started_at"))
    completed_str = _date(_get(checklist, "completed_at"))
    duration_sec = _get(checklist, "duration_seconds")
    dur_str = f"{int(duration_sec) // 60}min" if duration_sec else "—"

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
        f"Tipo: {chk_type}  |  Template: {tmpl_name[:20]}"
        f"  |  Início: {started_str}  |  Fim: {completed_str}  |  Duração: {dur_str}"
    )
    pdf.cell(120, 6, meta[:105], align="L")

    pdf.set_xy(135, bar_y + 1.5)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_NAV)
    pdf.cell(58, 6, "INSPECÇÃO DE VIATURA", align="R")
    pdf.set_text_color(*_INK)
    pdf.set_y(bar_y + bar_h + 3)

    # ── Inspection items grid (2 per row) ─────────────────────────────────────
    pdf.section_header("ITENS DE INSPECÇÃO")

    items: list = []
    if template is not None:
        raw_items = _get(template, "items") or []
        items = list(raw_items) if not isinstance(raw_items, list) else raw_items

    responses: dict = {}
    raw_resp = _get(checklist, "responses")
    if isinstance(raw_resp, dict):
        responses = raw_resp

    CELL_W = 90.0
    CELL_H = 14.0
    PILL_W = 18.0
    PILL_H = 4.0

    for i in range(0, max(len(items), 1), 2):
        row_items = items[i : i + 2]
        row_y = pdf.get_y()

        for col, item in enumerate(row_items):
            item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            item_label = (
                item.get("label") if isinstance(item, dict) else getattr(item, "label", "—")
            ) or "—"
            resp = responses.get(str(item_id), {}) if item_id else {}
            answer = str(resp.get("answer", "—") or "—")[:28]
            state_key = str(resp.get("state", "")).lower()
            fill_col, text_col, pill_text = _STATE_COLORS.get(state_key, _STATE_DEFAULT)

            x_cell = 15 + col * CELL_W
            pdf.set_xy(x_cell, row_y)
            pdf.set_draw_color(*_LINE)
            pdf.set_line_width(0.2)
            pdf.rect(x_cell, row_y, CELL_W - 1, CELL_H)

            # Item label
            pdf.set_xy(x_cell + 2, row_y + 1)
            pdf.set_font("DejaVu", "B", 7)
            pdf.set_text_color(*_INK)
            pdf.cell(CELL_W - PILL_W - 5, 5, str(item_label)[:35])

            # State pill
            pill_x = x_cell + CELL_W - PILL_W - 3
            pdf.set_fill_color(*fill_col)
            pdf.rect(pill_x, row_y + 1.5, PILL_W, PILL_H, "F")
            pdf.set_xy(pill_x, row_y + 1.8)
            pdf.set_font("DejaVu", "B", 6)
            pdf.set_text_color(*text_col)
            pdf.cell(PILL_W, PILL_H - 0.5, pill_text, align="C")

            # Answer text
            pdf.set_xy(x_cell + 2, row_y + 7)
            pdf.set_font("DejaVu", "", 7)
            pdf.set_text_color(*_MUTED)
            pdf.cell(CELL_W - 4, 5, answer)

        pdf.set_text_color(*_INK)
        pdf.set_y(row_y + CELL_H + 1)

    pdf.ln(3)

    # ── Observations ─────────────────────────────────────────────────────────
    obs_rows = [
        (
            (item.get("label") if isinstance(item, dict) else getattr(item, "label", "—")) or "—",
            (
                responses.get(
                    str(item.get("id") if isinstance(item, dict) else getattr(item, "id", "")), {}
                )
            ).get("notes", ""),
        )
        for item in items
        if responses.get(
            str(item.get("id") if isinstance(item, dict) else getattr(item, "id", "")), {}
        ).get("notes")
    ]

    if obs_rows:
        pdf.section_header("OBSERVAÇÕES")
        for lbl, note in obs_rows:
            pdf.set_font("DejaVu", "B", 7)
            pdf.set_text_color(*_INK)
            pdf.cell(50, 5, f"{str(lbl)[:28]}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font("DejaVu", "", 7)
            pdf.cell(0, 5, str(note)[:80], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.section_header("ASSINATURA DO MOTORISTA")
    pdf.ln(4)
    sig_y = pdf.get_y()
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.line(15, sig_y + 18, 110, sig_y + 18)
    pdf.set_xy(15, sig_y + 19)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_INK)
    pdf.cell(95, 4, "Assinatura do Motorista")
    pdf.set_xy(15, sig_y + 23)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(95, 4, driver_name)
    pdf.set_xy(15, sig_y + 27)
    pdf.cell(95, 3, "Data: ___/___/______")

    pdf.set_text_color(*_INK)
    total_pages_ref[0] = pdf.pages
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
