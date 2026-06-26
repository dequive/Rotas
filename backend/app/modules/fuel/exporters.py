"""ROTAS fuel document exporters — Ordem de Compra PDF (fpdf2 + DejaVuSans)."""

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
_AMBER = (180, 116, 0)

_FUEL_TYPE_LABELS = {
    "gasoleo": "Gasóleo",
    "gasolina": "Gasolina",
    "gas": "Gás",
    "eletrico": "Elétrico",
}

_STATUS_LABELS = {
    "pending": "Pendente",
    "approved": "Aprovada",
    "cancelled": "Cancelada",
}


def _g(obj: object, attr: str, default: str = "—") -> str:
    if isinstance(obj, dict):
        return str(obj.get(attr) or default)
    return str(getattr(obj, attr, None) or default)


def _money(v: object) -> str:
    try:
        return f"{Decimal(str(v or 0)):,.2f} MZN"
    except Exception:
        return "0.00 MZN"


def _date(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, str) and value:
        return value[:16].replace("T", " ")
    return "—"


def _date_short(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str) and value:
        return value[:10]
    return "—"


class _PurchaseOrderPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(0, 4, "Documento Processado por Computador — ROTAS", align="L")
        self.cell(0, 4, f"Página {self.page_no()} de {{nb}}", align="R")


def render_purchase_order(
    purchase: object,
    *,
    profile: dict | None = None,
) -> bytes:
    """Generate Ordem de Compra de Combustível PDF (PHC layout, A4 portrait).

    purchase: FuelPurchase ORM object or dict.
    profile:  TenantDocumentProfile dict for issuer header.
    Returns raw PDF bytes.
    """
    pdf = _PurchaseOrderPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.alias_nb_pages()
    pdf.add_page()

    PW = 180.0  # usable page width
    LM = 15.0

    # ── Nav bar ───────────────────────────────────────────────────────────────
    pdf.set_fill_color(*_NAV)
    pdf.rect(LM, pdf.get_y(), PW, 9, style="F")
    pdf.set_xy(LM + 3, pdf.get_y() + 1)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_WHITE)
    pdf.cell(PW - 6, 7, "ORDEM DE COMPRA DE COMBUSTÍVEL", align="L")
    pdf.ln(11)

    # ── Two-column header: issuer (left) | supplier box (right) ──────────────
    y0 = pdf.get_y()
    LEFT_W = 95.0
    RIGHT_W = 80.0

    # Left: issuer
    p = profile or {}
    pdf.set_xy(LM, y0)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(LEFT_W, 6, p.get("legal_name") or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for field in ("address_line1", "address_line2", "city", "phone", "email"):
        val = p.get(field)
        if val:
            pdf.set_xy(LM, pdf.get_y())
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(LEFT_W, 4, val, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    issuer_bottom = pdf.get_y()

    # Right: supplier box
    bx = LM + LEFT_W + 5
    by = y0
    bw = RIGHT_W
    bh = 34.0
    pdf.set_draw_color(*_LINE)
    pdf.set_fill_color(*_SOFT)
    pdf.rect(bx, by, bw, bh, style="FD")

    pdf.set_xy(bx + 3, by + 3)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(bw - 6, 4, "FORNECEDOR", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(bx + 3, pdf.get_y())
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*_INK)
    pdf.cell(bw - 6, 6, _g(purchase, "supplier_name"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(bx + 3, pdf.get_y() + 2)
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(bw - 6, 4, "Nº REFERÊNCIA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(bx + 3, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(bw - 6, 5, _g(purchase, "purchase_reference"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    meta_y = max(issuer_bottom, by + bh) + 4
    pdf.set_fill_color(*_SOFT)
    pdf.set_draw_color(*_LINE)
    pdf.rect(LM, meta_y, PW, 8, style="FD")
    pdf.set_xy(LM + 2, meta_y + 2)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_MUTED)

    status_raw = _g(purchase, "status", "pending")
    status_label = _STATUS_LABELS.get(status_raw, status_raw.title())
    meta = [
        (
            "Data do Pedido",
            _date_short(
                getattr(purchase, "ordered_at", None)
                if not isinstance(purchase, dict)
                else purchase.get("ordered_at")
            ),
        ),
        ("Estado", status_label),
        ("Emissão", _date_short(__import__("datetime").date.today())),
    ]
    cw = PW / len(meta)
    for label, val in meta:
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(cw / 2, 4, f"{label}:", align="L")
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(cw / 2, 4, val, align="L")

    # ── Details section ───────────────────────────────────────────────────────
    pdf.set_y(meta_y + 10)

    def section(title: str) -> None:
        pdf.set_fill_color(*_NAV)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("DejaVu", "B", 8)
        pdf.cell(0, 6, f"  {title}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)
        pdf.ln(1)

    def kv(label: str, value: str, lw: float = 60) -> None:
        pdf.set_font("DejaVu", "B", 8)
        pdf.cell(lw, 6, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 8)
        pdf.cell(0, 6, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    section("DETALHES DA ENCOMENDA")

    fuel_raw = _g(purchase, "fuel_type", "gasoleo")
    fuel_label = _FUEL_TYPE_LABELS.get(fuel_raw, fuel_raw.title())

    ordered = _g(purchase, "ordered_liters")
    try:
        ordered_fmt = f"{Decimal(ordered):,.2f} L"
    except Exception:
        ordered_fmt = f"{ordered} L"

    kv("Tipo de Combustível", fuel_label)
    kv("Quantidade Pedida", ordered_fmt)
    kv(
        "Preço Unitário",
        _money(
            getattr(purchase, "unit_price", None)
            if not isinstance(purchase, dict)
            else purchase.get("unit_price")
        ),
    )
    kv(
        "Total da Encomenda",
        _money(
            getattr(purchase, "total_cost", None)
            if not isinstance(purchase, dict)
            else purchase.get("total_cost")
        ),
    )

    notes = _g(purchase, "notes", "")
    if notes and notes != "—":
        kv("Observações", notes)

    # ── Approval block (if approved) ──────────────────────────────────────────
    approved_at = (
        getattr(purchase, "approved_at", None)
        if not isinstance(purchase, dict)
        else purchase.get("approved_at")
    )
    if approved_at:
        pdf.ln(4)
        section("APROVAÇÃO")
        kv("Aprovado em", _date(approved_at))

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.ln(10)
    sig_y = pdf.get_y()
    half = PW / 2 - 5
    pdf.set_draw_color(*_LINE)
    pdf.line(LM, sig_y + 18, LM + half, sig_y + 18)
    pdf.line(LM + half + 10, sig_y + 18, LM + PW, sig_y + 18)

    pdf.set_xy(LM, sig_y + 20)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(half, 4, "Responsável pela Requisição", align="C")
    pdf.set_x(LM + half + 10)
    pdf.cell(half, 4, "Aprovação / Gestor de Frota", align="C")

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
