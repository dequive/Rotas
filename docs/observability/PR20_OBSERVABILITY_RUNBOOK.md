# PR-20 — Runbook de Observabilidade

## Âmbito

Este runbook cobre os SLIs técnicos do release candidate. Não transforma
métricas técnicas em BI de negócio e não autoriza `tenant_id`, utilizador,
evento ou documento como label Prometheus.

## Rotas de resposta

### RotasBackendDown

1. Confirmar target e erro de scrape em Prometheus.
2. Verificar container, `/health/deep`, migrations, PostgreSQL, Redis e
   heartbeat ARQ.
3. Congelar promoção e rollback para o digest anterior quando
   backward-compatible.

### RotasApiHighErrorRate

1. Correlacionar início do alerta com SHA, deploy e logs estruturados.
2. Separar 5xx por handler sem introduzir identificadores de tenant.
3. Verificar DB, Redis, Governance e R2; rollback/forward-fix conforme migration.

### RotasApiLatencyBudget

1. Confirmar tráfego suficiente e p95 acima de 200 ms durante dez minutos.
2. Comparar `rotas_db_pool_connections{state="checked_out"}` com
   `rotas_db_pool_capacity{limit="max_connections"}` por pool; nunca adicionar
   tenant, utilizador, query ou connection ID como label.
   Em Gunicorn, confirmar que o target exporta a soma multiprocess e que a
   capacidade corresponde ao número de workers vivos; uma capacidade de apenas
   5 com quatro workers indica configuração/registry incompleto.
3. Investigar handlers, locks PostgreSQL, Redis, integrações e saturação.
4. Correlacionar checkouts/invalidações com `admin_sql`, `app_sql`,
   `auth_identity`, `tenant_lookup` e `rls_context` do diagnóstico PR-22.
5. Se a ocupação atingir a capacidade, confirmar limites PostgreSQL antes de
   alterar `pool_size`/`max_overflow`; tuning sem ensaio comparável é proibido.
6. Executar o cenário PR-22 correspondente antes de retomar promoção.

### RotasOutboxDeadLetter

1. Abrir a reconciliação tenant-scoped do outbox.
2. Identificar falha terminal, Governance 4xx ou esgotamento de retries.
3. Corrigir a causa e usar replay auditado com motivo; nunca alterar a linha
   directamente.

### RotasPrometheusRuleFailures

1. Consultar `prometheus_rule_evaluation_failures_total` e logs do Prometheus.
2. Revalidar regras com `promtool`.
3. Corrigir regra ou restaurar a configuração anterior; não silenciar o alerta.

## Evidência obrigatória antes de G4 verde

- screenshots/export do dashboard no SHA do RC;
- alerta firing e resolved entregue pelo canal real;
- logs/traces correlacionados sem PII;
- janela suficiente para calcular SLO e burn rate;
- ensaio de target down, 5xx, latência e DLQ;
- owner/on-call e escalonamento confirmados;
- isolamento e acesso ao Grafana aprovados.
- restart de um worker confirma remoção da sua contribuição `live*`, sem série
  obsoleta nem queda das métricas dos restantes workers.

## Bundle de certificação

Copiar
`infra/observability/PR20_OBSERVABILITY_CERTIFICATION_CONTEXT.example.json`
para o directório seguro do RC. O template é deliberadamente NO-GO e não pode
ser preenchido com resultados locais.

O gate exige doze relatórios JSON físicos:

- snapshot Prometheus e export do dashboard canónico;
- consulta ao log store e scan de PII;
- export do trace store e scan de PII;
- cinco drills, um para cada alerta canónico;
- relatório da janela SLO.

Cada relatório deve conter `kind` e o SHA integral do release, além de ser
referenciado pelo seu SHA-256. A recolha deve vir de runner externo. Logs
precisam de retenção mínima de 30 dias; traces, sete dias. A janela SLO deve
cobrir pelo menos 30 dias completos com cobertura mínima de 99%.

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.observability_certification `
  --context C:\secure\PR20_OBSERVABILITY_CERTIFICATION_CONTEXT.json `
  --output C:\secure\PR20_OBSERVABILITY_CERTIFICATION_RESULT.json
```

O resultado é somente um `release_evidence_fragment`. Só alimenta os controlos
`metrics`, `logs`, `traces`, `alerts_delivered` e `slo_window` quando
`passed=true`, todos estão verdes e os hashes são aprovados por SRE/BE.
