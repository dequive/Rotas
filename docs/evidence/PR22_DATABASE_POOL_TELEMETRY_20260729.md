# PR-22 — Telemetria de Pool PostgreSQL

Data: 2026-07-29  
Estado: `in_progress`  
Âmbito: implementação e validação estática/local, sem execução de carga  
Efeito em G4: nenhum; continua vermelho

## Resultado

Foi fechada a lacuna de observabilidade necessária para distinguir SQL lento
de saturação/aquisição de conexão no próximo ensaio PR-22.

Foram adicionadas métricas Prometheus:

- `rotas_db_pool_connections{pool,state}`;
- `rotas_db_pool_capacity{pool,limit}`;
- `rotas_db_pool_checkouts_total{pool}`;
- `rotas_db_pool_invalidations_total{pool}`.

Os únicos valores permitidos para `pool` são `application`,
`administrative` e `shared`. Não existem labels de tenant, utilizador,
documento, query ou conexão.

## Integração

- aplicação e sessão administrativa são expostas separadamente quando usam
  engines distintos;
- quando ambas partilham engine, existe uma única série `shared`;
- ocupação é recolhida diretamente do pool no scrape, evitando contadores
  locais divergentes;
- capacidade mantém `pool_size` e `max_connections` configurados;
- dashboard `rotas-release-slos` passou de sete para oito painéis;
- o runbook de latência exige correlacionar pool, SQL, auth, tenant lookup e
  RLS antes de qualquer tuning.

## Validação

```text
Ruff:  green
Pyright: 0 erros, 0 warnings
Pytest observabilidade/performance/pool: 14 passed
Dashboard JSON: validado pelo validador PR-20
```

## Limite da evidência

A topologia anterior em PostgreSQL 5440/Redis não estava ativa e Docker
Desktop não estava disponível. A instância 5432 presente não aceitou as
credenciais ROTAS e não foi usada como substituta.

Consequentemente, esta iteração não publica novos p50/p95, não afirma melhoria
de latência e não altera budgets. A próxima execução deve usar:

1. PostgreSQL/Redis da topologia PR-22;
2. `rotas_app` restrito e sessão administrativa separada;
3. quatro workers do RC;
4. runner externo;
5. métricas de pool, `pg_stat_statements` e PR-20 na mesma janela;
6. dois tenants, corrida idempotente e soak mínimo de duas horas.

PR-22 continua `in_progress`; G4 e PR-26 permanecem bloqueados.
