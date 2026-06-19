"""ROTAS cargo document exporters — Guia de Remessa and Carta de Porte Internacional PDFs.

Design goals:
- Guia de Remessa: A4 portrait, shipper/recipient columns, cargo table, signature block.
- Carta de Porte Internacional (CPI): A4 portrait, bilingual PT/EN headers, SADC fields.
- UTF-8: DejaVuSans covers Portuguese diacritics and Mozambican names.
"""

from __future__ import annotations

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


class _CargoDocPDF(FPDF):
    """Base FPDF subclass with ROTAS branding for cargo documents."""

    def __init__(self, title: str):
        super().__init__()
        self._doc_title = title
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))

    def header(self):
        self.set_fill_color(*_NAV)
        self.rect(0, 0, 210, 18, "F")
        self.set_y(4)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(*_WHITE)
        self.cell(0, 10, "ROTAS  —  " + self._doc_title, align="C")
        self.set_text_color(*_INK)
        self.ln(14)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, f"Página {self.page_no()}", align="C")
        self.set_text_color(*_INK)

    def section_header(self, label: str):
        self.set_fill_color(*_NAV)
        self.set_text_color(*_WHITE)
        self.set_font("DejaVu", "B", 8)
        self.cell(0, 6, label, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*_INK)

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


def render_guia_remessa(document: object, extra: dict | None = None) -> bytes:
    """Generate Guia de Remessa PDF.

    document: TransportDocument ORM object (or dict-like with the same fields)
    extra: extra_fields dict (cargo_description, package_count, gross_weight)
    Returns raw PDF bytes.
    """
    extra = extra or {}

    def g(attr: str) -> str:
        val = getattr(document, attr, None) if not isinstance(document, dict) else document.get(attr)
        return str(val) if val is not None else ""

    pdf = _CargoDocPDF("GUIA DE REMESSA")
    pdf.add_page()
    pdf.set_margins(15, 22, 15)

    # Document number + date
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(90, 6, f"N.º Documento: {g('document_number') or 'N/D'}", new_x=XPos.RIGHT, new_y=YPos.TOP)
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    pdf.cell(0, 6, f"Data: {issued}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # Shipper / Recipient columns
    col_w = 85
    gap = 10
    y_start = pdf.get_y()

    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(col_w, 6, "REMETENTE / SHIPPER", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(gap, 6, "", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col_w, 6, "DESTINATÁRIO / CONSIGNEE", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)

    pdf.set_font("DejaVu", "", 8)
    shipper_lines = [("Nome", g("client_name")), ("Origem", g("origin")), ("NUIT Emitente", g("issuer"))]
    recipient = getattr(document, "recipient_name", None) or extra.get("recipient_name", "")
    recipient_nuit = getattr(document, "recipient_nuit", None) or extra.get("recipient_nuit", "")
    recipient_lines = [("Nome", recipient), ("Destino", g("destination")), ("NUIT", recipient_nuit)]

    y_col = pdf.get_y()
    for (ll, lv), (rl, rv) in zip(shipper_lines, recipient_lines):
        pdf.set_xy(15, y_col)
        pdf.set_font("DejaVu", "B", 7)
        pdf.cell(20, 5, ll + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.cell(col_w - 20, 5, lv or "—", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_xy(15 + col_w + gap, y_col)
        pdf.set_font("DejaVu", "B", 7)
        pdf.cell(20, 5, rl + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.cell(col_w - 20, 5, rv or "—")
        y_col += 5

    pdf.set_y(y_col + 3)
    pdf.ln(2)

    # Cargo table
    pdf.section_header("DESCRIÇÃO DA CARGA / CARGO DESCRIPTION")
    pdf.set_font("DejaVu", "B", 7)
    pdf.set_fill_color(*_SOFT)
    pdf.cell(90, 5, "Descrição", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(30, 5, "Qtd / Volumes", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 5, "Peso Bruto (kg)", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("DejaVu", "", 8)
    cargo_desc = extra.get("cargo_description") or g("notes") or "—"
    package_count = str(extra.get("package_count", "—"))
    gross_weight = str(extra.get("gross_weight", "—"))
    pdf.cell(90, 6, cargo_desc)
    pdf.cell(30, 6, package_count, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 6, gross_weight, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    # Route
    pdf.section_header("PERCURSO / ROUTE")
    pdf.set_font("DejaVu", "", 8)
    pdf.two_col_kv("Origem", g("origin"), "Destino", g("destination"))
    pdf.two_col_kv("Válido de", g("valid_from")[:10] if g("valid_from") else "", "Válido até", g("valid_until")[:10] if g("valid_until") else "")
    pdf.ln(8)

    # Signature block
    pdf.section_header("ASSINATURAS / SIGNATURES")
    pdf.ln(4)
    sig_y = pdf.get_y()
    for i, (label, sub) in enumerate([
        ("Remetente / Shipper", "Assinatura e Carimbo"),
        ("Transportador / Carrier", "Assinatura e Carimbo"),
        ("Destinatário / Consignee", "Assinatura e Carimbo"),
    ]):
        x = 15 + i * 63
        pdf.set_xy(x, sig_y + 14)
        pdf.set_draw_color(*_LINE)
        pdf.line(x, sig_y + 13, x + 55, sig_y + 13)
        pdf.set_font("DejaVu", "B", 7)
        pdf.cell(55, 4, label)
        pdf.set_xy(x, sig_y + 18)
        pdf.set_font("DejaVu", "", 6)
        pdf.set_text_color(*_MUTED)
        pdf.cell(55, 4, sub)
        pdf.set_text_color(*_INK)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def render_carta_porte_internacional(document: object, extra: dict | None = None) -> bytes:
    """Generate Carta de Porte Internacional (CPI) PDF — bilingual PT/EN.

    extra: extra_fields dict (border_post, country_destination, sadc_cpi_number, consignee_name, consignee_nuit)
    Returns raw PDF bytes.
    """
    extra = extra or {}

    def g(attr: str) -> str:
        val = getattr(document, attr, None) if not isinstance(document, dict) else document.get(attr)
        return str(val) if val is not None else ""

    pdf = _CargoDocPDF("CARTA DE PORTE INTERNACIONAL / INTERNATIONAL BILL OF LADING")
    pdf.add_page()
    pdf.set_margins(15, 22, 15)

    # Header info
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(90, 6, f"N.º CPI / CPI No.: {extra.get('sadc_cpi_number') or g('document_number') or 'N/D'}", new_x=XPos.RIGHT, new_y=YPos.TOP)
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    pdf.cell(0, 6, f"Data / Date: {issued}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # Carrier / Route section
    pdf.section_header("TRANSPORTADOR / CARRIER")
    pdf.set_font("DejaVu", "", 8)
    pdf.kv_row("Transportador / Carrier", g("issuer"))
    pdf.kv_row("País de Origem / Country of Origin", "Moçambique / Mozambique")
    pdf.kv_row("País de Destino / Country of Destination", extra.get("country_destination", "—"))
    pdf.kv_row("Posto Fronteiriço / Border Post", extra.get("border_post", "—"))
    pdf.ln(4)

    # Consignor / Consignee
    pdf.section_header("EXPEDIDOR E DESTINATÁRIO / CONSIGNOR AND CONSIGNEE")
    pdf.two_col_kv("Expedidor / Consignor", g("client_name"), "NUIT", g("issuer"))
    recipient = extra.get("consignee_name") or getattr(document, "recipient_name", "") or ""
    recipient_nuit = extra.get("consignee_nuit") or getattr(document, "recipient_nuit", "") or ""
    pdf.two_col_kv("Destinatário / Consignee", recipient, "NUIT Dest.", recipient_nuit)
    pdf.ln(4)

    # Route
    pdf.section_header("PERCURSO / ROUTE")
    pdf.two_col_kv("Origem / Origin", g("origin"), "Destino / Destination", g("destination"))
    pdf.two_col_kv("Válido De / From", g("valid_from")[:10] if g("valid_from") else "", "Válido Até / To", g("valid_until")[:10] if g("valid_until") else "")
    pdf.ln(4)

    # Cargo
    pdf.section_header("MERCADORIA / GOODS")
    pdf.kv_row("Descrição / Description", g("notes") or extra.get("cargo_description", "—"))
    pdf.ln(8)

    # Customs declaration
    pdf.section_header("DECLARAÇÃO ADUANEIRA / CUSTOMS DECLARATION")
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 4,
        "O expedidor declara que as informações fornecidas neste documento são verdadeiras e correctas. / "
        "The consignor declares that the information provided in this document is true and correct.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)
    pdf.ln(8)

    # Signatures
    pdf.section_header("ASSINATURAS / SIGNATURES")
    pdf.ln(4)
    sig_y = pdf.get_y()
    for i, label in enumerate(["Expedidor / Consignor", "Transportador / Carrier", "Autoridade Alfandegária / Customs"]):
        x = 15 + i * 63
        pdf.line(x, sig_y + 13, x + 55, sig_y + 13)
        pdf.set_xy(x, sig_y + 14)
        pdf.set_font("DejaVu", "B", 7)
        pdf.cell(55, 4, label)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
