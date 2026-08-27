"""ROTAS trip report exporter — render_trip_report PDF (fpdf2 + DejaVuSans).

Design: PHC institutional layout — issuer left column, entity right box,
grey metadata bar, section headers, financial summary, standard footer.
"""

from __future__ import annotations

from datetime import datetime
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
_AMBER = (245, 158, 11)
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
    amount = Decimal(str(v or 0))
    return f"{amount:,.2f} MZN"


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


class _TripReportPDF(FPDF):
    """FPDF2 subclass for trip report PDFs."""

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

    def section_header(self, label: str):
        self.set_fill_color(*_NAV)
        self.set_text_color(*_WHITE)
        self.set_font("DejaVu", "B", 8)
        self.cell(0, 6, label, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*_INK)
        self.ln(1)

    def kv_row(self, label: str, value: str, w_label: float = 50):
        self.set_font("DejaVu", "B", 8)
        self.cell(w_label, 5, label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def two_col_kv(self, left_label: str, left_val: str, right_label: str, right_val: str):
        self.set_font("DejaVu", "B", 8)
        self.cell(45, 5, left_label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("DejaVu", "", 8)
        self.cell(55, 5, left_val or "—", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("DejaVu", "B", 8)
        self.cell(35, 5, right_label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 5, right_val or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def render_trip_report(
    trip: object,
    vehicle: object | None = None,
    driver: object | None = None,
    stops: list | None = None,
    profile: dict | None = None,
) -> bytes:
    """Generate Relatório de Viagem PDF.

    trip: Trip ORM object or dict-like.
    vehicle: dict with keys plate, model (optional).
    driver: dict with keys name, license_number (optional).
    stops: list of TripStop ORM objects or dicts (optional).
    profile: TenantDocumentProfile dict (optional).
    Returns raw PDF bytes.
    """
    stops = stops or []

    def g(obj: object, attr: str) -> str:
        if isinstance(obj, dict):
            val = obj.get(attr)
        else:
            val = getattr(obj, attr, None)
        return str(val) if val is not None else "—"

    total_pages_ref: list[int] = [1]
    pdf = _TripReportPDF(total_pages_ref)
    pdf.add_page()

    # ── PHC 2-col header ──────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    issuer_bottom = _phc_issuer_col(pdf, profile, x=x_left, y=header_y, w=LEFT_W)

    # Right box: VIAGEM
    box_h = 32.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    pdf.set_xy(x_right, header_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(RIGHT_W, 6, "VIAGEM", fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    trip_id_str = str(g(trip, "id"))[:8].upper() if g(trip, "id") != "—" else "—"
    waybill = g(trip, "waybill_number")
    status = g(trip, "status")
    vplate = g(vehicle, "plate") if vehicle is not None else "—"
    dname = g(driver, "full_name") if driver is not None else "—"
    for lbl, val in [
        ("ID", trip_id_str),
        ("Status", status),
        ("N.º Guia", waybill),
        ("Viatura", vplate),
        ("Motorista", dname),
    ]:
        pdf.set_xy(x_right + 2, pdf.get_y())
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(22, 5, lbl + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(RIGHT_W - 24, 5, str(val)[:30], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(max(issuer_bottom, header_y + box_h) + 3)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    origin = g(trip, "origin")
    destination = g(trip, "destination")
    started_raw = _get(trip, "actual_departure")
    completed_raw = _get(trip, "actual_arrival")
    dist_raw = _get(trip, "distance_km")
    started_str = _date(started_raw)
    completed_str = _date(completed_raw)
    dist_str = f"{dist_raw} km" if dist_raw is not None else "—"

    bar_y = pdf.get_y()
    bar_h = 9.0
    pdf.set_fill_color(*_SOFT)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.rect(15, bar_y, 180, bar_h, "FD")

    pdf.set_xy(17, bar_y + 1.5)
    pdf.set_font("DejaVu", "", 6)
    pdf.set_text_color(*_MUTED)
    meta = (
        f"Origem: {origin}  →  Destino: {destination}"
        f"  |  Partida: {started_str}  |  Chegada: {completed_str}  |  Dist.: {dist_str}"
    )
    pdf.cell(130, 6, meta[:95], align="L")

    pdf.set_xy(145, bar_y + 1.5)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_NAV)
    pdf.cell(48, 6, "RELATÓRIO DE VIAGEM", align="R")
    pdf.set_text_color(*_INK)
    pdf.set_y(bar_y + bar_h + 3)

    # ── Cargo info ────────────────────────────────────────────────────────────
    cargo_type_raw = _get(trip, "cargo_type")
    if cargo_type_raw is not None:
        pdf.section_header("CARGA")
        cargo_weight = g(trip, "cargo_weight")
        cargo_volumes = g(trip, "cargo_volumes")
        is_hazmat = _get(trip, "is_hazmat", False)
        hazmat_class = g(trip, "hazmat_class")
        hazmat_str = f"SIM — classe {hazmat_class}" if is_hazmat else "Não"
        pdf.kv_row("Tipo", str(cargo_type_raw))
        pdf.kv_row("Peso", f"{cargo_weight} t" if cargo_weight != "—" else "—")
        pdf.kv_row("Volumes", cargo_volumes)
        pdf.kv_row("HAZMAT", hazmat_str)
        pdf.ln(3)

    # ── Stops table ───────────────────────────────────────────────────────────
    if stops:
        pdf.section_header("PARAGENS")
        STOP_COLS = [80.0, 35.0, 30.0, 35.0]
        STOP_HDRS = ["Localização", "Hora Chegada", "Tipo", "Duração (min)"]

        pdf.set_fill_color(*_SOFT)
        pdf.set_text_color(*_INK)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.3)
        for w, hdr in zip(STOP_COLS, STOP_HDRS, strict=False):
            pdf.cell(w, 6, hdr, border=1, fill=True, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln()

        for idx, stop in enumerate(stops):
            fill = idx % 2 == 0
            pdf.set_fill_color(*(_SOFT if fill else _WHITE))
            pdf.set_font("DejaVu", "", 7)
            loc = g(stop, "address")
            arr_raw = _get(stop, "stopped_at")
            dep_raw = _get(stop, "resumed_at")
            arr_str = _date(arr_raw)
            stop_type = g(stop, "stop_type")
            if isinstance(arr_raw, datetime) and isinstance(dep_raw, datetime):
                dur = int((dep_raw - arr_raw).total_seconds() / 60)
                dur_str = f"{dur} min"
            else:
                dur_str = "—"
            row_vals = [loc[:40], arr_str, stop_type[:18], dur_str]
            for val, w in zip(row_vals, STOP_COLS, strict=False):
                pdf.cell(
                    w,
                    6,
                    val,
                    border=1,
                    fill=fill,
                    align="L",
                    new_x=XPos.RIGHT,
                    new_y=YPos.TOP,
                )
            pdf.ln()
        pdf.ln(3)

    # ── Financial summary ─────────────────────────────────────────────────────
    fuel_cost = _get(trip, "total_fuel_cost")
    expense_cost = _get(trip, "total_expense_cost")
    transport_cost = _get(trip, "total_transport_cost")
    revenue = _get(trip, "actual_revenue")

    fc = Decimal(str(fuel_cost or 0))
    ec = Decimal(str(expense_cost or 0))
    tc = Decimal(str(transport_cost or 0))
    rv = Decimal(str(revenue or 0))
    total_cost = fc + ec + tc
    margin = rv - total_cost
    margin_pct = (margin / rv * 100) if rv else Decimal(0)

    fin_y = pdf.get_y()
    LEFT_FIN = 90.0
    GAP = 10.0
    RIGHT_FIN = 80.0
    x_lf = 15.0
    x_rf = x_lf + LEFT_FIN + GAP

    # Left: costs
    pdf.set_xy(x_lf, fin_y)
    pdf.section_header("CUSTOS")
    fin_y2 = pdf.get_y()
    pdf.set_xy(x_lf, fin_y2)
    pdf.kv_row("Combustível", _money(fc), w_label=60)
    pdf.set_xy(x_lf, pdf.get_y())
    pdf.kv_row("Despesas Operacionais", _money(ec), w_label=60)
    pdf.set_xy(x_lf, pdf.get_y())
    pdf.kv_row("Custo Transporte", _money(tc), w_label=60)
    pdf.set_xy(x_lf, pdf.get_y())
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(60, 5, "Total:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(0, 5, _money(total_cost), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    left_bottom = pdf.get_y()

    # Right: financial summary box
    pdf.set_xy(x_rf, fin_y)
    pdf.set_draw_color(*_NAV)
    pdf.set_line_width(0.4)
    pdf.rect(x_rf, fin_y, RIGHT_FIN, 35)

    pdf.set_xy(x_rf, fin_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(
        RIGHT_FIN,
        6,
        "RESUMO FINANCEIRO",
        fill=True,
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    margin_color = _GREEN if margin >= 0 else _RED
    for lbl, val, color in [
        ("Receita", _money(rv), _INK),
        ("Custo Total", _money(total_cost), _INK),
        ("Margem %", f"{margin_pct:.1f}%", margin_color),
    ]:
        pdf.set_xy(x_rf + 2, pdf.get_y())
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(35, 5, lbl + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*color)
        pdf.cell(RIGHT_FIN - 37, 5, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(*_INK)
    pdf.set_y(max(left_bottom, fin_y + 38))

    total_pages_ref[0] = len(pdf.pages)
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
