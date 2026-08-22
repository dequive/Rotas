# PR-22 — Agregação Prometheus Multiprocess

Data: 2026-07-29  
Estado: `validated_local_linux`  
Gate afectado: G4 — continua vermelho

> Actualização: a execução Linux e a curva de carga estão consolidadas em
> `PR22_LOCKED_CONTAINER_RUNTIME_20260729.md`.

## Resultado

Foi corrigida a lacuna que fazia `/metrics` devolver apenas o processo Gunicorn
atingido pelo scrape:

- Docker e Railway carregam `app.gunicorn_conf`;
- o master define `PROMETHEUS_MULTIPROC_DIR` antes de importar a aplicação e
  antes do fork;
- o diretório fica obrigatoriamente dentro do diretório temporário do sistema;
- ficheiros `*.db` obsoletos são removidos antes de iniciar os workers;
- `child_exit` chama `multiprocess.mark_process_dead`;
- ocupação e capacidade do pool usam gauges `livesum`;
- callbacks `set_function`, incompatíveis com agregação multiprocess, foram
  removidos;
- checkout, checkin e close actualizam ocupação por eventos SQLAlchemy.

A capacidade exposta representa agora a soma dos pools vivos. Com quatro
workers e configuração de produção `pool_size=2`, `max_overflow=3`, o esperado
é capacidade máxima agregada de 20 conexões por engine, e não 5 do worker
aleatoriamente atingido.

## Comportamento fail-closed

O diretório multiprocess:

- é inicializado no hook `on_starting`, antes do carregamento da aplicação;
- rejeita caminhos fora do temporário do sistema;
- remove apenas ficheiros de métricas `*.db`, preservando outros ficheiros;
- não é partilhado pelo processo de migrations ou pelo worker ARQ, pois estes
  não iniciam por Gunicorn.

O validador PR-20 falha se:

- os gauges de pool deixarem de usar `livesum`;
- regressar um callback `set_function`;
- faltarem preparação, limpeza ou `mark_process_dead`;
- Docker ou Railway deixarem de carregar o config Gunicorn.

## Validação

```text
Pytest observabilidade/performance/pool/Gunicorn: 18 passed
Teste spawn multiprocess:                         2 + 3 = 5
Validador PR-20:                                  multiprocess_metrics = 1
Ruff:                                             green
Pyright:                                          0 erros, 0 warnings
```

O teste spawn cria dois processos independentes com gauges `livesum` de 2 e 3
e confirma que `MultiProcessCollector` exporta 5.

## Validação Linux posterior

A imagem `rotas-backend:pr22-multiprocess` foi posteriormente construída com
lock e hashes. Quatro workers iniciaram num container read-only e `/metrics`
expôs capacidade agregada 20 para application e 20 para administrative.

O restart PID 26 -> PID 85 removeu a série `livesum` do worker morto, preservou
as quatro séries vivas e manteve capacidade 20/20.

Isto prova localmente:

- boot do container Linux/Gunicorn;
- quatro workers agregados no mesmo `/metrics`;
- remoção das séries após restart de worker;
- capacidade agregada 20/20 com configuração de produção;
- scrape simultâneo durante carga local.

Não prova o mesmo comportamento no RC/staging nem aprova os budgets de
performance. PR-22 permanece `in_progress` e G4 permanece vermelho.
