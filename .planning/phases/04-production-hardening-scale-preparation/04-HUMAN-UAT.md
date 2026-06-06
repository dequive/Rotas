---
status: partial
phase: 04-production-hardening-scale-preparation
source: [04-VERIFICATION.md]
started: 2026-06-06T00:00:00Z
updated: 2026-06-06T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Railway deployment — gunicorn importa a app sem erros
expected: `gunicorn --check-config -k uvicorn.workers.UvicornWorker app.main:app` sai com código 0 (em Linux/Railway)
result: [pending — requer ambiente Linux]

### 2. ARQ worker arranca sem erros
expected: `arq app.jobs.worker.WorkerSettings` arranca e regista o cron diário sem exceções
result: [pending — requer Redis activo]

### 3. DriverScorecardPanel renderiza correctamente em /motoristas
expected: Secção "Desempenho de Motoristas" aparece abaixo da tabela; selector de motorista funciona; com <3 viagens mostra badge "Dados insuficientes"
result: [pending]

### 4. MaintenanceImminentPanel renderiza correctamente em / (Control Tower)
expected: Painel "Manutenção Iminente" aparece abaixo da conformidade da frota; sem alertas mostra "Sem manutenções iminentes"
result: [pending]

### 5. RLS — cross-tenant isolation em produção
expected: Query com `SET LOCAL app.tenant_id = 'tenant-A'` não retorna dados de tenant-B (verificado pelos testes automatizados; validação manual opcional em staging)
result: [covered by automated tests — 3 RLS tests green]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
