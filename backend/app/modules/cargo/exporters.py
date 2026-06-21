"""ROTAS cargo document exporters — Guia de Remessa and Carta de Porte Internacional PDFs.

Design goals:
- PHC institutional layout: issuer left column, entity info right bordered box.
- Metadata bar: grey fill, horizontal kv pairs, bold doc-type label right-aligned.
- Standard footer: divider line + 3 cells (Documento Processado / ROTAS / Página N de T).
- UTF-8: DejaVuSans covers Portuguese diacritics and Mozambican names.
"""

from __future__ import annotations

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


class _CargoDocPDF(FPDF):
    """Base FPDF subclass with PHC layout for cargo documents."""

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

    def metadata_bar(self, fields: list[tuple[str, str]], doc_label: str):
        """Draw grey metadata bar with kv pairs and bold doc label right-aligned."""
        bar_y = self.get_y()
        bar_h = 9.0
        self.set_fill_color(*_SOFT)
        self.set_draw_color(*_LINE)
        self.set_line_width(0.3)
        self.rect(15, bar_y, 180, bar_h, "FD")

        self.set_xy(17, bar_y + 1.5)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        parts = [f"{lbl}: {val}" for lbl, val in fields]
        self.cell(120, 6, "  |  ".join(parts), align="L")

        self.set_xy(135, bar_y + 1.5)
        self.set_font("DejaVu", "B", 8)
        self.set_text_color(*_NAV)
        self.cell(58, 6, doc_label, align="R")
        self.set_text_color(*_INK)
        self.set_y(bar_y + bar_h + 3)


def render_guia_remessa(
    document: object, extra: dict | None = None, profile: dict | None = None
) -> bytes:
    """Generate Guia de Remessa PDF with PHC layout.

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

    total_pages_ref: list[int] = [1]
    pdf = _CargoDocPDF(total_pages_ref)
    pdf.add_page()

    # ── PHC 2-col header ──────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()  # = 15 from top margin
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    issuer_bottom = _phc_issuer_col(pdf, profile, x=x_left, y=header_y, w=LEFT_W)

    # Right box: DESTINATÁRIO
    box_h = 32.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    # Label row
    pdf.set_xy(x_right, header_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(RIGHT_W, 6, "DESTINATÁRIO", fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # KV rows inside box
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
    for lbl, val in [("Nome", recipient), ("Destino", dest_val), ("NUIT", recipient_nuit)]:
        pdf.set_xy(x_right + 2, pdf.get_y())
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(20, 5, lbl + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(RIGHT_W - 22, 5, str(val)[:32], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(max(issuer_bottom, header_y + box_h) + 3)

    # ── Metadata bar ──────────────────────────────────────────────────────────
    doc_num = g("document_number") or "N/D"
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    valid_until = g("valid_until")[:10] if g("valid_until") else "—"
    pdf.metadata_bar(
        [("N.º Documento", doc_num), ("Data Emissão", issued), ("Válido até", valid_until)],
        "GUIA DE REMESSA",
    )

    # ── Cargo table ───────────────────────────────────────────────────────────
    pdf.ln(1)
    COL_WIDTHS = [90.0, 30.0, 30.0, 30.0]
    HEADERS = ["Descrição", "Volumes", "Peso Bruto kg", "Valor Declarado"]
    ALIGNS = ["L", "C", "C", "R"]

    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.set_fill_color(*_SOFT)
    pdf.set_text_color(*_INK)
    pdf.set_font("DejaVu", "B", 7)
    for w, hdr, aln in zip(COL_WIDTHS, HEADERS, ALIGNS, strict=False):
        pdf.cell(w, 6, hdr, border=1, fill=True, align=aln, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    cargo_desc = extra.get("cargo_description") or g("notes") or "—"
    package_count = str(extra.get("package_count", "—"))
    gross_weight = str(extra.get("gross_weight", "—"))
    declared_value = str(extra.get("declared_value", "—"))
    pdf.set_font("DejaVu", "", 8)
    pdf.set_fill_color(*_WHITE)
    for val, w, aln in zip(
        [cargo_desc[:55], package_count, gross_weight, declared_value],
        COL_WIDTHS,
        ALIGNS,
        strict=False,
    ):
        pdf.cell(w, 6, val, border=1, fill=False, align=aln, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()
    pdf.ln(4)

    # ── Route block ───────────────────────────────────────────────────────────
    pdf.section_header("PERCURSO")
    pdf.kv_row("Origem", g("origin") or "—")
    pdf.kv_row("Destino", g("destination") or "—")
    pdf.two_col_kv(
        "Viatura",
        extra.get("vehicle_plate", "—"),
        "Motorista",
        extra.get("driver_name", "—"),
    )
    pdf.ln(4)

    # ── 3-party signature block ───────────────────────────────────────────────
    pdf.section_header("ASSINATURAS")
    pdf.ln(4)
    sig_y = pdf.get_y()
    SIG_LABELS = ["Remetente", "Transportador", "Destinatário"]
    for i, label in enumerate(SIG_LABELS):
        x = 15 + i * 60
        pdf.set_draw_color(*_LINE)
        pdf.line(x, sig_y + 18, x + 55, sig_y + 18)
        pdf.set_xy(x, sig_y + 20)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(55, 4, label)
        pdf.set_xy(x, sig_y + 25)
        pdf.set_font("DejaVu", "", 6)
        pdf.set_text_color(*_MUTED)
        pdf.cell(55, 4, "Data: ___/___/______")

    pdf.set_text_color(*_INK)
    total_pages_ref[0] = pdf.pages
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def render_carta_porte_internacional(
    document: object, extra: dict | None = None, profile: dict | None = None
) -> bytes:
    """Generate Carta de Porte Internacional (CPI) PDF — bilingual PT/EN with PHC layout.

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

    total_pages_ref: list[int] = [1]
    pdf = _CargoDocPDF(total_pages_ref)
    pdf.add_page()

    # ── PHC 2-col header ──────────────────────────────────────────────────────
    LEFT_W = 110.0
    RIGHT_W = 65.0
    header_y = pdf.get_y()
    x_left = 15.0
    x_right = x_left + LEFT_W + 5.0

    issuer_bottom = _phc_issuer_col(pdf, profile, x=x_left, y=header_y, w=LEFT_W)

    # Right box: EXPEDIDOR / CONSIGNOR
    box_h = 32.0
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, header_y, RIGHT_W, box_h)

    pdf.set_xy(x_right, header_y)
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7)
    pdf.cell(
        RIGHT_W, 6, "EXPEDIDOR / CONSIGNOR", fill=True, align="C",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    client_name = g("client_name") or "—"
    issuer_nuit = g("issuer") or "—"
    for lbl, val in [
        ("Nome", client_name),
        ("País Origem", "Moçambique / Mozambique"),
        ("NUIT", issuer_nuit),
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
    cpi_num = extra.get("sadc_cpi_number") or g("document_number") or "N/D"
    issued = g("issued_at")[:10] if g("issued_at") else "—"
    border_post = extra.get("border_post", "—")
    country_dest = extra.get("country_destination", "—")
    pdf.metadata_bar(
        [
            ("N.º CPI", cpi_num),
            ("Data / Date", issued),
            ("Posto Fronteiriço", border_post),
            ("País Destino", country_dest),
        ],
        "CARTA DE PORTE INTERNACIONAL",
    )

    # ── Carrier block ─────────────────────────────────────────────────────────
    pdf.section_header("TRANSPORTADOR / CARRIER")
    pdf.kv_row("Transportador / Carrier", g("issuer") or "—")
    pdf.kv_row("País de Origem / Country of Origin", "Moçambique / Mozambique")
    pdf.kv_row("País de Destino / Country of Destination", country_dest)
    pdf.kv_row("Posto Fronteiriço / Border Post", border_post)
    pdf.ln(3)

    # ── Consignee block ───────────────────────────────────────────────────────
    pdf.section_header("DESTINATÁRIO / CONSIGNEE")
    recipient = extra.get("consignee_name") or getattr(document, "recipient_name", "") or "—"
    recipient_nuit = extra.get("consignee_nuit") or getattr(document, "recipient_nuit", "") or "—"
    pdf.two_col_kv("Destinatário / Consignee", str(recipient), "NUIT Dest.", str(recipient_nuit))
    pdf.ln(3)

    # ── Route block ───────────────────────────────────────────────────────────
    pdf.section_header("PERCURSO / ROUTE")
    pdf.two_col_kv(
        "Origem / Origin", g("origin") or "—",
        "Destino / Destination", g("destination") or "—",
    )
    valid_from = g("valid_from")[:10] if g("valid_from") else "—"
    valid_until = g("valid_until")[:10] if g("valid_until") else "—"
    pdf.two_col_kv(
        "Válido De / From", valid_from,
        "Válido Até / To", valid_until,
    )
    pdf.ln(3)

    # ── Cargo block ───────────────────────────────────────────────────────────
    pdf.section_header("MERCADORIA / GOODS")
    pdf.kv_row(
        "Descrição / Description",
        g("notes") or extra.get("cargo_description", "—"),
    )
    pdf.ln(3)

    # ── Customs declaration ───────────────────────────────────────────────────
    pdf.section_header("DECLARAÇÃO ADUANEIRA / CUSTOMS DECLARATION")
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        4,
        "O expedidor declara que as informações fornecidas neste documento são verdadeiras e"
        " correctas. / The consignor declares that the information provided in this document"
        " is true and correct.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_text_color(*_INK)
    pdf.ln(4)

    # ── 3-party signature block ───────────────────────────────────────────────
    pdf.section_header("ASSINATURAS / SIGNATURES")
    pdf.ln(4)
    sig_y = pdf.get_y()
    SIG_LABELS = ["Expedidor / Consignor", "Transportador / Carrier", "Autoridade Alfandegária"]
    for i, label in enumerate(SIG_LABELS):
        x = 15 + i * 60
        pdf.set_draw_color(*_LINE)
        pdf.line(x, sig_y + 18, x + 55, sig_y + 18)
        pdf.set_xy(x, sig_y + 20)
        pdf.set_font("DejaVu", "B", 7)
        pdf.set_text_color(*_INK)
        pdf.cell(55, 4, label[:28])
        pdf.set_xy(x, sig_y + 25)
        pdf.set_font("DejaVu", "", 6)
        pdf.set_text_color(*_MUTED)
        pdf.cell(55, 4, "Data: ___/___/______")

    pdf.set_text_color(*_INK)
    total_pages_ref[0] = pdf.pages
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
