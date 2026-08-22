# PR-22 — Diagnóstico de Cauda e Saturação

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations  
SHA base: `d8a8e52b5f1cb98ef4fd805c945fd70674c98e25` + working tree

## Veredicto

A latência residual foi decomposta por fase. A leitura passa em execução
serial, mas falha sob concorrência no worker local. No sync, reduzir cinco
lookups idempotentes a uma prefetch melhorou a mediana dessa fase, sem eliminar
outliers de aquisição/execução de sessão.

Não foram introduzidos cache de identidade, relaxamento de revogação, aumento
de budgets ou tuning de pool sem evidência.

## Instrumentação

`PERFORMANCE_DIAGNOSTICS=true` activa, apenas fora de produção:

- tempos request-scoped com nomes de fase fixos e baixa cardinalidade;
- `Server-Timing` sem SQL, tenant, user, token ou identificadores;
- decomposição de auth, SQL admin/app, RLS, tenant lookup, idempotência,
  dispatch, flush e commit;
- recolha e percentis pelo gate PR-22.

Produção rejeita a configuração no startup. O default é `false`.

## Leitura concorrente

600 pedidos, concorrência 12, um worker, JWT real e `rotas_app`:

| Fase | p50 | p95 | Máximo |
| --- | ---: | ---: | ---: |
| HTTP total | 196,687 ms | 303,856 ms | 1.638,883 ms |
| Auth total | 69,662 ms | 130,886 ms | 967,070 ms |
| SQL admin | 19,349 ms | 35,465 ms | 233,928 ms |
| Tenant lookup | 60,027 ms | 101,504 ms | 602,473 ms |
| SQL app acumulado | 29,079 ms | 52,879 ms | 458,973 ms |
| RLS `set_config` | 18,949 ms | 35,440 ms | 286,905 ms |

Uma hipótese de devolver o tenant completo carregado durante auth removeu o
segundo percurso RLS, mas elevou auth p95 para 323,902 ms e HTTP p95 para
427,767 ms. Foi rejeitada e revertida integralmente.

## Leitura serial

100 pedidos, concorrência 1, mesmas credenciais e endpoint:

| Fase | p50 | p95 |
| --- | ---: | ---: |
| HTTP total | 43,267 ms | 53,138 ms |
| Auth total | 11,232 ms | 13,043 ms |
| SQL admin | 3,079 ms | 3,992 ms |
| Tenant lookup | 11,022 ms | 12,285 ms |
| SQL app | 4,851 ms | 5,521 ms |
| RLS | 3,418 ms | 3,983 ms |

O budget p95 200 ms passa serialmente. A degradação é função da concorrência e
da cauda local, não de uma consulta isolada permanentemente lenta.

## Sync

Vinte batches de cinco operações, concorrência 4:

| Fase | Antes da prefetch p50/p95 | Depois p50/p95 |
| --- | ---: | ---: |
| HTTP total | 347,660 / 1.015,039 ms | 381,422 / 1.733,040 ms |
| Auth | 27,165 / 279,914 ms | 30,777 / 877,430 ms |
| Idempotência | 47,737 / 385,191 ms | 27,075 / 420,590 ms |
| Dispatch | 140,241 / 174,754 ms | 159,485 / 179,728 ms |
| Flush | 67,119 / 88,331 ms | 82,861 / 108,738 ms |
| Commit | 11,668 / 22,966 ms | 16,685 / 35,690 ms |

A prefetch reduz cinco SELECTs tenant-scoped para um e melhora a mediana da
fase idempotente. O p95 global não melhorou porque outliers de auth/sessão
dominaram a pequena amostra. As duas execuções processaram 100/100 operações,
sem falha de domínio.

## Controlos e regressão

```text
Pytest diagnóstico/performance/auth/sync/RLS: 59 passed
Ruff:                                     green
Pyright app + tests:                      0 erros, 0 warnings
Produção + diagnostics:                   startup rejeitado
Identificadores em Server-Timing:         zero
Snapshot de tenant mais lento:            revertido
Pool 3+2 sem ganho:                       revertido
```

## Artefactos

- `PR22_LOCAL_API_READ_DIAGNOSTIC_20260727.json`;
- `PR22_LOCAL_API_READ_SERIAL_DIAGNOSTIC_20260727.json`;
- `PR22_LOCAL_API_READ_SNAPSHOT_DIAGNOSTIC_20260727.json`;
- `PR22_LOCAL_SYNC_DIAGNOSTIC_20260727.json`;
- `PR22_LOCAL_SYNC_PREFETCH_DIAGNOSTIC_20260727.json`.

## Próxima prova necessária

1. runner externo para que gerador e servidor não disputem a mesma máquina;
2. quatro workers do container RC com CPU/memória limitadas como staging;
3. `pg_stat_statements`, pool checkout/in-use e PR-20 correlacionados;
4. PostgreSQL/Redis na topologia real, incluindo latência de rede;
5. repetição nominal, corrida, rede degradada e soak mínimo de duas horas;
6. dois tenants e invariantes transaccionais no mesmo intervalo.

PR-22 permanece `in_progress`; G4 permanece vermelho.
