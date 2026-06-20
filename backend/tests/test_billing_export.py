"""BILL-01 (PDF UTF-8) and BILL-02 (XLSX format) export tests."""

import re
import zlib
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock

from openpyxl import load_workbook


def _pdf_text(pdf_bytes: bytes) -> str:
    """Decompress all FlateDecode streams in a PDF and return their text."""
    parts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        chunk = m.group(1)
        try:
            parts.append(zlib.decompress(chunk).decode("latin-1"))
        except Exception:
            parts.append(chunk.decode("latin-1", errors="replace"))
    return "\n".join(parts)


def _make_mock_document():
    doc = MagicMock()
    doc.id = "test-doc-id"
    doc.client_name = "Transportes Quelimane Lda"
    doc.contract_reference = "CTR-001"
    doc.billing_period_start = None
    doc.billing_period_end = None
    doc.status = "issued"
    doc.currency = "MZN"
    doc.subtotal = Decimal("3001.00")
    doc.tax_amount = Decimal("510.17")
    doc.total_amount = Decimal("3511.17")
    doc.iva_rate = Decimal("0.1700")
    return doc


def _make_mock_item(unit_price=1500.50, amount=3001.00):
    item = MagicMock()
    item.delivered_at = None
    item.origin = "Maputo"
    item.destination = "Quelimane"
    item.cargo_description = "Cimento Portland"
    item.load_state = "full"
    item.quantity = 2
    item.unit_price = unit_price
    item.amount = amount
    return item


def test_pdf_renders_utf8_characters():
    """BILL-01: PDF bytes for a trip with Mozambican names must not corrupt diacritics."""
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    doc.client_name = "João Machanga Transportes Quelimane"
    items = [_make_mock_item()]
    # Should not raise UnicodeEncodeError
    artifact = render_billing_export(doc, items, "pdf")
    assert len(artifact.content) > 1000
    assert artifact.content[:4] == b"%PDF"


def test_pdf_contains_header_text():
    """BILL-01: PDF must start with valid PDF header."""
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [], "pdf")
    assert artifact.content[:4] == b"%PDF"
    assert len(artifact.content) > 0


def test_xlsx_header_row_is_bold():
    """BILL-02: XLSX title row and table header row must have font.bold == True.

    Layout: row 1 = ROTAS title (bold), rows 2-6 = metadata, row 8 = table header (bold).
    """
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active
    # Row 1: ROTAS institutional title — must be bold
    assert ws.cell(row=1, column=1).font.bold is True
    # Row 7: table column header — must be bold (row 8 was Estado which was removed in CME)
    assert ws.cell(row=7, column=1).font.bold is True


def test_xlsx_currency_columns_have_format():
    """BILL-02: Currency columns (unit_price, total) must use '#,##0.00' number format.

    Data starts at row 9 (rows 1-8 are title + metadata + table header).
    """
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active
    # Row 8 = first data row; columns 7-8 = unit price / total
    # (row 9 was data when Estado row existed; Estado removed in CME, data shifts up by 1)
    assert "#,##0.00" in ws.cell(row=8, column=7).number_format
    assert "#,##0.00" in ws.cell(row=8, column=8).number_format


def test_pdf_contains_iva_section():
    """FISC-02: PDF renderer must call cell() with SUBTOTAL, IVA and TOTAL COM IVA labels.

    fpdf2 TrueType fonts encode text as glyph indices so raw bytes are not searchable.
    We capture cell() calls instead to verify the labels are passed before encoding.
    """
    from unittest.mock import patch

    from fpdf import FPDF

    from app.modules.billing.exporters import render_billing_export

    captured: list[str] = []
    _orig_cell = FPDF.cell

    def _capturing_cell(self, *args, **kwargs):
        # text is 3rd positional or keyword
        text = args[2] if len(args) > 2 else kwargs.get("text", "")
        if text:
            captured.append(str(text))
        return _orig_cell(self, *args, **kwargs)

    with patch.object(FPDF, "cell", _capturing_cell):
        doc = _make_mock_document()
        render_billing_export(doc, [_make_mock_item()], "pdf")

    assert "SUBTOTAL" in captured, f"SUBTOTAL not rendered. Got: {captured}"
    assert any("IVA" in t for t in captured), f"IVA label not rendered. Got: {captured}"
    assert "TOTAL COM IVA" in captured, f"TOTAL COM IVA not rendered. Got: {captured}"


def test_xlsx_iva_rows():
    """FISC-02: XLSX output must have SUBTOTAL, IVA, and TOTAL COM IVA rows."""
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active

    all_values = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "SUBTOTAL" in all_values, f"SUBTOTAL not found in column A. Values: {all_values}"
    assert any("IVA" in str(v) for v in all_values if v), f"IVA row not found. Values: {all_values}"
    assert "TOTAL COM IVA" in all_values, f"TOTAL COM IVA not found. Values: {all_values}"
