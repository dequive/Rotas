---
phase: 07
plan: 02
status: done
completed: 2026-06-21
tests: 6/6 PASS
---

# 07-02 SUMMARY — AR Correctness Tests

## What shipped

`backend/tests/test_ar_phase7.py` — 6 tests:

1. `test_ar_summary_buckets_correct` — invoice 45 days overdue lands in 31_60 bucket
2. `test_ar_summary_as_of_param` — invoice issued today excluded when as_of=yesterday
3. `test_ar_summary_excludes_drafts` — draft document never appears in AR totals
4. `test_client_statement_outstanding_correct` — outstanding = total_amount - confirmed allocations (voided excluded)
5. `test_client_statement_pdf_returns_bytes` — PDF endpoint returns `%PDF` magic bytes, Content-Type application/pdf
6. `test_ar_cross_tenant` — tenant A invoices not visible in tenant B AR summary

## Result

6/6 PASS (verified 2026-06-21).
