---
plan: "04"
phase: 15-fiscal-compliance-seguran-a-de-carga
status: complete
wave: 2
---

# Plan 15-04 Summary — FISC-02 IVA Calculation

## What was done

**Service layer:**
- `billing/service.py`: `create_document()` now computes `iva_rate=Decimal("0.1700")` and `iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))` for every `BillingItem`
- `billing/service.py`: `issue_document()` recomputes `document.subtotal`, `document.tax_amount` (= sum of item iva_amounts), and `document.total_amount = subtotal + tax_amount` at issue time
- `billing/service.py`: `document.iva_rate` set to the common rate if all items share one, otherwise `None` (mixed rates)
- `billing/service.py`: `serialize_billing_item()` now includes `iva_rate` and `iva_amount`

**Exporters:**
- `billing/exporters.py` (`_render_pdf`): Replaced single "TOTAL A PAGAR" row with three-row SUBTOTAL / IVA (17%) / TOTAL COM IVA block. TOTAL COM IVA rendered in navy fill with white bold text
- `billing/exporters.py` (`_render_xlsx`): Replaced single total row with three rows: SUBTOTAL, IVA (17%), TOTAL COM IVA (dark row, bold)

**Tests:**
- `tests/test_billing_export.py`: Updated mock document to include `subtotal`, `tax_amount`, `total_amount`, `iva_rate` fields
- `test_pdf_contains_iva_section`: Implemented — patches `FPDF.cell` to capture labels before glyph encoding (TrueType fonts encode text as glyph indices, not ASCII)
- `test_xlsx_iva_rows`: Implemented — loads workbook and scans column A for SUBTOTAL / IVA / TOTAL COM IVA labels
- All 6 billing export tests pass
