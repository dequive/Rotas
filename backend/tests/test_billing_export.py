"""BILL-01 (PDF UTF-8) and BILL-02 (XLSX format) export tests."""
from io import BytesIO
from unittest.mock import MagicMock

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
    """BILL-02: XLSX header row cells must have font.bold == True."""
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active
    assert ws.cell(row=1, column=1).font.bold is True


def test_xlsx_currency_columns_have_format():
    """BILL-02: Currency columns (unit_price, total) must use '#,##0.00' number format."""
    from app.modules.billing.exporters import render_billing_export

    doc = _make_mock_document()
    artifact = render_billing_export(doc, [_make_mock_item()], "xlsx")
    wb = load_workbook(BytesIO(artifact.content))
    ws = wb.active
    assert ws.cell(row=2, column=7).number_format == "#,##0.00"
    assert ws.cell(row=2, column=8).number_format == "#,##0.00"
