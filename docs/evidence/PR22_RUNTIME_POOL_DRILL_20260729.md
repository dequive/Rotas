# PR-22 — Drill HTTP com Pool PostgreSQL

Data: 2026-07-29  
Estado: `in_progress`  
Classe: evidência local de engenharia  
Efeito em G4: nenhum; continua vermelho

## Veredicto

A topologia local do ROTAS voltou a estar disponível e permitiu executar a
leitura concorrente com quatro workers, JWT real, `rotas_app` sem
`SUPERUSER/BYPASSRLS`, sessão administrativa separada, PostgreSQL 16/`rec13`,
Redis e 42.048 tenants sintéticos.

O resultado não é estável nem promove PR-22:

| Execução | p50 | p95 | p99 | HTTP 200 | Erros | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Arranque frio | 131,579 ms | 250,521 ms | 1.150,118 ms | 600/600 | 0 | falhou |
| Aquecida | 107,667 ms | 142,951 ms | 304,934 ms | 595/600 | 5 | passou no limite |
| Repetição tipada | 89,315 ms | 322,902 ms | 10.138,896 ms | 591/600 | 9 `ReadTimeout` | falhou |

Todos os ensaios usaram 600 pedidos, concorrência 12 e o endpoint
`GET /api/v1/tenants/me`. A passagem aquecida não é aceite isoladamente: houve
1,5% de `ReadTimeout` na repetição, acima do máximo de 1%, e o p95 voltou a
falhar.

## Correlação com o pool

Uma execução diagnóstica separada amostrou `/metrics` durante a carga:

| Sinal | Resultado |
| --- | ---: |
| Scrapes / erros de scrape | 50 / 0 |
| Aplicação — máximo observado | 2 / 15 conexões, 13,33% |
| Administração — máximo observado | 1 / 15 conexões, 6,67% |
| Invalidações observadas | 0 |
| HTTP p95 diagnóstico | 270,448 ms |
| HTTP p99 diagnóstico | 401,515 ms |

Não foi observada saturação do pool no processo atingido por cada scrape. O
sampler usa o endpoint HTTP e, em Uvicorn multiprocess no Windows, cada resposta
é process-visible; não representa a soma atómica dos quatro workers. O pool
local em `ENVIRONMENT=test` também tem capacidade 15 por engine, enquanto a
configuração de produção usa 5. Portanto, esta medição elimina apenas a hipótese
de saturação evidente neste drill; não dimensiona o RC.

Os percentis diagnósticos continuaram dominados por `auth_identity` e
`tenant_lookup`. `pg_stat_statements` não está instalado nesta instância, logo
não existe evidência de planos/tempo agregado por query para a mesma janela.

## Melhoria do gate

O gate PR-22 passou a:

- persistir `error_types`, distinguindo timeout de status HTTP e perda simulada;
- aceitar `--metrics-url` para amostrar o pool durante a carga;
- registar máximo observado e utilização por `application`,
  `administrative` ou `shared`;
- declarar a recolha como `http_scrape_process_visible`, evitando alegar
  agregação multiprocess que o runtime não fornece.

O parser só aceita métricas e labels fixos do pool. Tenant, utilizador, query,
token e identificadores não entram no artefacto.

Após este drill, a agregação multiprocess foi implementada e validada em teste
spawn; ver `PR22_MULTIPROCESS_METRICS_20260729.md`. A imagem Linux/Gunicorn
continua por validar, portanto este artefacto histórico permanece
`process_visible`.

## Artefactos

- `PR22_LOCAL_API_READ_POOL_20260729.json` — arranque frio;
- `PR22_LOCAL_API_READ_POOL_WARM_20260729.json` — execução aquecida;
- `PR22_LOCAL_API_READ_POOL_SAMPLED_20260729.json` — diagnóstico com pool;
- `PR22_LOCAL_API_READ_REPEAT_20260729.json` — repetição com erros tipados.

## Próxima prova obrigatória

1. executar gerador fora do host do serviço;
2. usar imagem e configuração do RC, incluindo pool de produção;
3. validar na imagem RC a agregação multiprocess já implementada;
4. activar `pg_stat_statements` e correlacionar queries, CPU, event loop e pool;
5. repetir leitura, sync, corrida, rede degradada e soak de duas horas;
6. exercitar dois tenants e invariantes transaccionais na mesma janela.

PR-22 continua `in_progress`; G4, PR-26 e a promoção permanecem bloqueados.
