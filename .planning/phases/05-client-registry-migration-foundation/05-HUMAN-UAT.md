---
status: partial
phase: 05-client-registry-migration-foundation
source: [05-VERIFICATION.md]
started: 2026-06-19T05:10:00Z
updated: 2026-06-19T05:10:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. CLI-03 Backfill Applied to Live DB
expected: Connect to DB as rotas_admin and run `SELECT count(*) FROM contracts WHERE client_id IS NULL AND client_name IS NOT NULL AND client_name != '';` — result must be 0
result: [pending]

### 2. ClientCombobox Search UX
expected: Open /contratos → "Novo Contrato" → click Client field → type 2+ characters — combobox filters by trading_name and NUIT; NUIT renders in IBM Plex Mono 11px; selecting a client shows NUIT below the trigger
result: [pending]

### 3. Credit Warning Strip at Runtime
expected: Set client credit_limit to 1000 MZN, create and issue a billing document for that client totalling 850 MZN — /clientes/[id] shows amber AlertTriangle warning strip
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
