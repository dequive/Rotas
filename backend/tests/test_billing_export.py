"""BILL-01 (PDF UTF-8) and BILL-02 (XLSX format) export tests."""

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from openpyxl import load_workbook


def _make_mock_document():
    doc = MagicMock()
    doc.id = "test-doc-id"
    doc.client_name = "Transportes Quelimane Lda"
    doc.contract_reference = "CTR-001"
    doc.billing_period_start = None
    doc.billing_period_end = None
    doc.status = "issued"
    doc.currency = "MZN"
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
    # Row 8: table column header — must be bold
    assert ws.cell(row=8, column=1).font.bold is True


def test_xlsx_currency_columns_have_format():
    """BILL-02: Currency columns (unit_price, total) must use '#,##0.00' number format.

    Data starts at row 9 (rows 1-8 are title + metadata + table header).
    """
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active
    # Row 9 = first data row; columns 7-8 = unit price / total
    assert "#,##0.00" in ws.cell(row=9, column=7).number_format
    assert "#,##0.00" in ws.cell(row=9, column=8).number_format


@pytest.mark.skip(reason="Wave 0 stub — implement in Wave 2 after FISC-02 IVA fields land")
def test_pdf_contains_iva_section():
    """FISC-02: PDF output must contain a visible IVA line with rate % and amount.

    After Wave 2 implementation:
    - Render PDF with a billing document that has tax_amount > 0 and iva_rate = 0.17
    - Decode PDF bytes and assert IVA text is present (e.g., b"IVA" in pdf_bytes)
    - Verify subtotal, IVA line, and total-com-IVA are present as distinct lines
    """
    pass


@pytest.mark.skip(reason="Wave 0 stub — implement in Wave 2 after FISC-02 IVA fields land")
def test_xlsx_iva_rows():
    """FISC-02: XLSX output must have subtotal row, IVA row, and total-com-IVA row.

    After Wave 2 implementation:
    - Render XLSX with a billing document that has iva_rate=0.17, tax_amount > 0
    - Load workbook with openpyxl and scan rows for 'SUBTOTAL', 'IVA', 'TOTAL COM IVA'
    - Confirm all three row labels exist in the worksheet
    """
    pass
