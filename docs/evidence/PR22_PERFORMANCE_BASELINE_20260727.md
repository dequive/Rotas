# PR-22 — Baseline de Performance e Resiliência

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations  
SHA base: `d8a8e52b5f1cb98ef4fd805c945fd70674c98e25` + working tree

## Veredicto

O gate e os budgets foram implementados, mas a baseline local é **vermelha**.
Integridade e disponibilidade passaram; latência sob carga nominal e
concorrência não passaram. O resultado não autoriza staging nem produção.

## Ambiente

- FastAPI/Uvicorn: um processo local em `127.0.0.1:8000`;
- PostgreSQL 16 local em `55432`, revision `rec13`;
- Redis local em `6381`;
- tenant e dados sintéticos já existentes;
- autenticação `DEV_TEST_TOKEN`, permitida apenas em development/test;
- conexão PostgreSQL como owner local, não como `rotas_app`;
- carga gerada por `httpx` na mesma máquina.

Logo, estes números servem para detectar regressões, não para estimar
capacidade de produção.

## Resultados

| Cenário | Volume/concorrência | Resultado | Budget | Estado |
| --- | --- | ---: | ---: | --- |
| API read inicial | 600 / 12 | p95 346,602 ms; p99 908,520 ms | 200 / 500 ms | red |
| API read repetida | 600 / 12 | p95 363,847 ms; p99 880,813 ms | 200 / 500 ms | red |
| Sync batch | 100 batches / 8; 500 operações | p95 780,602 ms; p99 831,267 ms | 500 / 1.000 ms | red |
| Corrida idempotente inédita | 20 / 20 | p95 2.080,793 ms; p99 2.086,943 ms | 500 / 1.000 ms | red |
| Rede degradada simulada | 300 / 12 | HTTP p95 45,313 ms; E2E p95 370,514 ms | 200 / 600 ms | green local |
| Soak local | 4.000 / 12; 68,471 s | p95 350,354 ms; p99 498,923 ms | 200 / 500 ms | red |

Todas as 5.614 chamadas HTTP entregues tiveram o status esperado. No cenário
de rede, 6/300 entregas foram descartadas intencionalmente, exactamente 2%, e
as restantes 294 responderam 200 sem erro inesperado.

O facto de rede degradada ter menor latência HTTP não contradiz o resultado
nominal: o atraso client-side espaçou a chegada e reduziu a pressão simultânea
no servidor. Sob envio contínuo, a API satura o budget de 200 ms.

## Integridade sob concorrência

- sync: 500/500 operações `processed`, zero falhas de domínio;
- corrida com chave inédita: 20 respostas, 1 `idempotency_keys`, 1 efeito
  distinto, zero conflito;
- stock negativo depois do ensaio: 0;
- diários desequilibrados depois do ensaio: 0;
- erros HTTP inesperados: 0.

Isto prova localmente a invariância idempotente do percurso exercitado, mas
não prova isolamento RLS porque a API usou o owner de desenvolvimento.

## Gates de engenharia

```text
Pytest performance:         8 passed
Ruff:                       green
Pyright app + tests:        0 erros, 0 warnings
Validador de budgets:       4 cenários, 5 invariantes, soak staging 7.200 s
API read / soak:            red latency
Sync batch:                 red latency; green correctness
Idempotency race:           red latency; green correctness
Rede degradada client-side: green local
```

## Artefactos

- `infra/performance/PERFORMANCE_BUDGETS.json`;
- `backend/scripts/performance_gate.py`;
- `backend/scripts/validate_performance_policy.py`;
- `docs/PERFORMANCE_AND_RESILIENCE_RUNBOOK.md`;
- `PR22_LOCAL_API_READ_20260727.json`;
- `PR22_LOCAL_API_READ_WARM_20260727.json`;
- `PR22_LOCAL_SYNC_BATCH_20260727.json`;
- `PR22_LOCAL_IDEMPOTENCY_RACE_20260727.json`;
- `PR22_LOCAL_DEGRADED_NETWORK_20260727.json`;
- `PR22_LOCAL_SOAK_20260727.json`.

## Trabalho obrigatório

1. perfilar `/tenants/me` e o lifecycle de sessão/RLS sob concorrência;
2. medir pools Uvicorn, SQLAlchemy/PostgreSQL e Redis, CPU, I/O e locks;
3. optimizar o batch, que hoje confirma cada operação individualmente;
4. repetir no RC/staging com `rotas_app` e dataset representativo;
5. usar gerador externo e proxy TCP/rede móvel, não apenas injecção client-side;
6. executar carga distribuída e soak mínimo de duas horas com PR-20 activo;
7. provar dois tenants e todos os invariantes no intervalo;
8. obter sign-off de QA/SRE.

Assim, PR-22 avança de `pending` para `in_progress`, e G4 permanece vermelho.
