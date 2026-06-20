-- ROTAS billing IVA backfill — 2026-06-20
-- Run in a transaction; ROLLBACK to inspect counts before COMMITting.
--
-- Purpose: normalise iva_rate on all billing_documents to fiscal-correct values:
--   - Documents issued before 2023-01-01 → 0.1700 (IVA 17%, pre-reform rate)
--   - Documents issued 2023-01-01 onwards (or with NULL issued_at) → 0.1600 (IVA 16%, current rate)
--
-- Usage:
--   psql -d rotas -f billing_iva_backfill.sql
--   Inspect counts from the audit query, then COMMIT or ROLLBACK as appropriate.

BEGIN;

-- 1. Audit: count documents that will be updated
SELECT
  CASE WHEN issued_at < '2023-01-01' THEN 'pre-2023 → 0.1700'
       ELSE 'from-2023 → 0.1600'
  END AS bucket,
  COUNT(*) AS doc_count,
  SUM(total_amount) AS total_exposure_mzn
FROM billing_documents
WHERE iva_rate IS NULL OR iva_rate NOT IN (0.1600, 0.1700)
GROUP BY 1;

-- 2. Backfill pre-2023 documents (IVA 17%)
UPDATE billing_documents
SET iva_rate = 0.1700, updated_at = NOW()
WHERE issued_at < '2023-01-01'
  AND (iva_rate IS NULL OR iva_rate != 0.1700);

-- 3. Backfill 2023+ documents (IVA 16%)
UPDATE billing_documents
SET iva_rate = 0.1600, updated_at = NOW()
WHERE (issued_at >= '2023-01-01' OR issued_at IS NULL)
  AND (iva_rate IS NULL OR iva_rate != 0.1600);

-- 4. Verify zero residual NULLs
SELECT COUNT(*) AS remaining_nulls FROM billing_documents WHERE iva_rate IS NULL;

-- ROLLBACK;  -- uncomment to inspect only
COMMIT;
