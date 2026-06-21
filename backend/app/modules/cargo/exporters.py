"""ROTAS cargo document exporters — Guia de Remessa and Carta de Porte Internacional PDFs.

Design: clean typographic layout — no coloured fills, no nav bars.
Thin 0.2 mm rules for structure; issuer left, doc box right (border only).
UTF-8: DejaVuSans covers Portuguese diacritics and Mozambican names.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"

_INK = (23, 32, 51)
_MUTED = (102, 112, 133)
_LINE = (180, 188, 200)
_INK_LINE = (23, 32, 51)


# ── Base PDF class ────────────────────────────────────────────────────────────


class _CleanPDF(FPDF):
    """Base class for clean cargo PDFs — typographic footer, no fills."""

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
    pdf.cell(RIGHT_W, 4, "Nº DOCUMENTO", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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


def _kv(pdf: _CleanPDF, label: str, value: str, w_label: float = 50) -> None:
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(w_label, 5, f"{label}:", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _two_kv(
    pdf: _CleanPDF,
    l_label: str, l_val: str,
    r_label: str, r_val: str,
    lw: float = 45, lv: float = 55, rw: float = 35,
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


def _entity_block(
    pdf: _CleanPDF,
    label: str,
    fields: list[tuple[str, str]],
) -> None:
    """Draw a plain-text entity block (recipient, consignee, etc.)."""
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for lbl, val in fields:
        _kv(pdf, lbl, val, w_label=28)


def _cargo_table(
    pdf: _CleanPDF,
    cargo_desc: str,
    package_count: str,
    gross_weight: str,
    declared_value: str,
) -> None:
    """Draw the cargo table with border-only rows (no fills)."""
    LM = pdf.l_margin
    COL_WIDTHS = [90.0, 30.0, 30.0, 30.0]
    HEADERS = ["Descrição", "Volumes", "Peso Bruto kg", "Valor Declarado"]
    ALIGNS = ["L", "C", "C", "R"]
    row_h = 6.0

    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_INK)

    # Header row — bottom border only
    x0 = LM
    y0 = pdf.get_y()
    for w, hdr, aln in zip(COL_WIDTHS, HEADERS, ALIGNS, strict=False):
        pdf.set_xy(x0, y0)
        pdf.cell(w, row_h, hdr, border="B", align=aln)  # type: ignore[arg-type]
        x0 += w
    pdf.ln()

    # Data row — thin bottom border per cell
    pdf.set_font("DejaVu", "", 8)
    row_vals = [cargo_desc[:55], package_count, gross_weight, declared_value]
    x0 = LM
    ry = pdf.get_y()
    for val, w, aln in zip(row_vals, COL_WIDTHS, ALIGNS, strict=False):
        pdf.set_xy(x0, ry)
        pdf.cell(w, row_h, val, border="B", align=aln)  # type: ignore[arg-type]
        x0 += w
    pdf.ln()


def _sig_3col(pdf: _CleanPDF, labels: list[str]) -> None:
    """Three-column signature block."""
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    pdf.ln(12)
    sig_y = pdf.get_y()
    col_w = PW / 3
    for i, label in enumerate(labels):
        x = LM + i * col_w
        line_end = x + col_w - 5
        pdf.set_draw_color(*_INK_LINE)
        pdf.set_line_width(0.3)
        pdf.line(x, sig_y, line_end, sig_y)
        pdf.set_xy(x, sig_y + 2)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(col_w - 5, 4, label[:24], align="C")
        pdf.set_xy(x, sig_y + 7)
        pdf.set_font("DejaVu", "", 6.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(col_w - 5, 4, "Data: ___/___/______", align="C")
    pdf.set_text_color(*_INK)


# ── Public render functions ───────────────────────────────────────────────────


def render_guia_remessa(
    document: object, extra: dict | None = None, profile: dict | None = None
) -> bytes:
    """Generate Guia de Remessa PDF — clean typographic layout.

    document: TransportDocument ORM object or dict-like with document fields.
    extra: extra_fields dict (cargo_description, package_count, gross_weight,
           declared_value, vehicle_plate, driver_name, recipient_name,
           recipient_nuit).
    profile: TenantDocumentProfile dict (legal_name, address_line1, address_line2,
             city, phone, email). Falls back to "—" for missing fields.
    Returns raw PDF bytes.
    """
    extra = extra or {}

    def g(attr: str) -> str:
        if isinstance(document, dict):
            val = document.get(attr)
        else:
            val = getattr(document, attr, None)
        return str(val) if val is not None else ""

    pdf = _CleanPDF()
    pdf.add_page()

    doc_num = g("document_number") or "N/D"
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    _header_block(pdf, profile, "GUIA DE REMESSA", doc_num, issued)

    # ── Recipient block ───────────────────────────────────────────────────────
    recipient = (
        getattr(document, "recipient_name", None)
        or extra.get("recipient_name", "")
        or "—"
    )
    recipient_nuit = (
        getattr(document, "recipient_nuit", None)
        or extra.get("recipient_nuit", "")
        or "—"
    )
    dest_val = g("destination") or "—"
    valid_until = g("valid_until")[:10] if g("valid_until") else "—"

    _entity_block(pdf, "Destinatário", [
        ("Nome", str(recipient)),
        ("Destino", dest_val),
        ("NUIT", str(recipient_nuit)),
    ])

    _kv(pdf, "Válido até", valid_until, w_label=28)

    # Rule below entity
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    rule_y = pdf.get_y() + 3
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)

    # ── Cargo table ───────────────────────────────────────────────────────────
    _section(pdf, "Carga")
    cargo_desc = extra.get("cargo_description") or g("notes") or "—"
    package_count = str(extra.get("package_count", "—"))
    gross_weight = str(extra.get("gross_weight", "—"))
    declared_value = str(extra.get("declared_value", "—"))
    _cargo_table(pdf, cargo_desc, package_count, gross_weight, declared_value)

    # ── Route block ───────────────────────────────────────────────────────────
    _section(pdf, "Percurso")
    _kv(pdf, "Origem", g("origin") or "—")
    _kv(pdf, "Destino", g("destination") or "—")
    _two_kv(pdf, "Viatura", extra.get("vehicle_plate", "—"),
            "Motorista", extra.get("driver_name", "—"))

    # ── Signature block ───────────────────────────────────────────────────────
    _section(pdf, "Assinaturas")
    _sig_3col(pdf, ["Remetente", "Transportador", "Destinatário"])

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def render_carta_porte_internacional(
    document: object, extra: dict | None = None, profile: dict | None = None
) -> bytes:
    """Generate Carta de Porte Internacional (CPI) PDF — bilingual PT/EN, clean layout.

    extra: extra_fields dict (border_post, country_destination, sadc_cpi_number,
    consignee_name, consignee_nuit).
    profile: TenantDocumentProfile dict. Falls back to "—" for missing fields.
    Returns raw PDF bytes.
    """
    extra = extra or {}

    def g(attr: str) -> str:
        if isinstance(document, dict):
            val = document.get(attr)
        else:
            val = getattr(document, attr, None)
        return str(val) if val is not None else ""

    pdf = _CleanPDF()
    pdf.add_page()

    cpi_num = extra.get("sadc_cpi_number") or g("document_number") or "N/D"
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    _header_block(pdf, profile, "CARTA DE PORTE INTERNACIONAL", cpi_num, issued)

    # ── Expedidor / consignor block ───────────────────────────────────────────
    client_name = g("client_name") or "—"
    issuer_nuit = g("issuer") or "—"
    _entity_block(pdf, "Expedidor / Consignor", [
        ("Nome", client_name),
        ("País Origem", "Moçambique / Mozambique"),
        ("NUIT", issuer_nuit),
    ])

    # Rule below entity
    LM = pdf.l_margin
    PW = pdf.w - LM - pdf.r_margin
    rule_y = pdf.get_y() + 3
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.2)
    pdf.line(LM, rule_y, LM + PW, rule_y)
    pdf.set_y(rule_y + 4)

    # ── Carrier block ─────────────────────────────────────────────────────────
    border_post = extra.get("border_post", "—")
    country_dest = extra.get("country_destination", "—")

    _section(pdf, "Transportador / Carrier")
    _kv(pdf, "Transportador / Carrier", g("issuer") or "—")
    _kv(pdf, "País de Origem / Country of Origin", "Moçambique / Mozambique")
    _kv(pdf, "País de Destino / Country of Destination", country_dest)
    _kv(pdf, "Posto Fronteiriço / Border Post", border_post)

    # ── Consignee block ───────────────────────────────────────────────────────
    _section(pdf, "Destinatário / Consignee")
    recipient = extra.get("consignee_name") or getattr(document, "recipient_name", "") or "—"
    recipient_nuit = extra.get("consignee_nuit") or getattr(document, "recipient_nuit", "") or "—"
    _two_kv(pdf, "Destinatário / Consignee", str(recipient), "NUIT Dest.", str(recipient_nuit))

    # ── Route block ───────────────────────────────────────────────────────────
    _section(pdf, "Percurso / Route")
    _two_kv(
        pdf,
        "Origem / Origin", g("origin") or "—",
        "Destino / Destination", g("destination") or "—",
    )
    valid_from = g("valid_from")[:10] if g("valid_from") else "—"
    valid_until = g("valid_until")[:10] if g("valid_until") else "—"
    _two_kv(
        pdf,
        "Válido De / From", valid_from,
        "Válido Até / To", valid_until,
    )

    # ── Cargo block ───────────────────────────────────────────────────────────
    _section(pdf, "Mercadoria / Goods")
    _kv(pdf, "Descrição / Description", g("notes") or extra.get("cargo_description", "—"))

    # ── Customs declaration ───────────────────────────────────────────────────
    _section(pdf, "Declaração Aduaneira / Customs Declaration")
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0, 4,
        "O expedidor declara que as informações fornecidas neste documento são verdadeiras e"
        " correctas. / The consignor declares that the information provided in this document"
        " is true and correct.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(*_INK)

    # ── Signature block ───────────────────────────────────────────────────────
    _section(pdf, "Assinaturas / Signatures")
    _sig_3col(pdf, ["Expedidor / Consignor", "Transportador / Carrier", "Autoridade Alfandegária"])

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
