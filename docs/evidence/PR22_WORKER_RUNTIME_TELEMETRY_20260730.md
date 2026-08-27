# PR-22 — Telemetria de CPU e Event Loop dos Workers

Data: 2026-07-30  
Estado: `validated_local_linux`  
Gate afectado: G4 — continua vermelho

## Resultado

O backend passou a expor duas métricas sem labels dinâmicas:

```text
rotas_event_loop_lag_seconds
rotas_process_cpu_utilization_ratio
```

A primeira representa o maior atraso de agendamento entre workers vivos. A
segunda soma a utilização dos workers em equivalentes de core; `2.0` significa
aproximadamente dois cores consumidos pelo conjunto, não um tenant ou processo
identificado.

O gate PR-22 amostra essas séries pelo mesmo scrape usado para os pools e grava
p95/máximo em `worker_runtime_observation`.

## Agregação multiprocess

| Métrica | Modo | Razão |
| --- | --- | --- |
| Event-loop lag | `livemax` | maior atraso apenas entre workers vivos |
| CPU dos workers | `livesum` | consumo agregado apenas dos workers vivos |

Uma primeira imagem usou `max`. O drill de restart mostrou cinco ficheiros
depois de substituir um dos quatro workers, provando que o pico do processo
morto podia permanecer indefinidamente. Essa versão foi rejeitada.

Depois da alteração para `livemax`, a imagem corrigida apresentou:

```text
Tag local: rotas-backend:pr22-runtime-telemetry-v2
Image ID:  sha256:85ea2b57a2bd67d2a302fb5f7a278aab7415f9457ef46e35a65d88f9fdc41e71
Tamanho:   124360267 bytes

Antes do restart:
  livemax files = 4
  livesum files = 4

Restart:
  worker 25 -> worker 57

Depois do restart:
  workers       = 26, 27, 28, 57
  livemax files = 4
  livesum files = 4
```

As séries permaneceram disponíveis após o restart:

```text
rotas_process_cpu_utilization_ratio 0.007506754023397906
rotas_event_loop_lag_seconds 0.0007196369997473084
```

Os valores são apenas uma prova de funcionamento em idle; não constituem
baseline de capacidade.

## Controlos incorporados

- lifecycle inicia e cancela o sampler junto com cada worker;
- intervalo fixo de 500 ms e cardinalidade zero;
- dashboard PR-20 passou de 8 para 10 painéis;
- validador exige `livemax`, `livesum`, lifecycle e painéis;
- política PR-22 exige runner externo, dois tenants, `pg_stat_statements` e
  métricas de runtime para certificação staging;
- o runbook proíbe exportar texto SQL, parâmetros ou identificadores de negócio
  de `pg_stat_statements`.

## Validação

```text
Pytest focado:                 20 passed
Ruff:                          green
Pyright:                       0 erros, 0 warnings
Validador PR-20:               10 painéis, 2 métricas de runtime
Validador PR-22:               4 controlos de certificação
JSON:                          green
Container read-only/4 workers: green
Restart e limpeza:             green
```

## Limite

Esta evidência confirma a instrumentação e a semântica multiprocess numa imagem
Linux local. Não prova saturação real, capacidade do RC, dois tenants,
`pg_stat_statements`, runner externo ou soak. PR-22 continua `in_progress` e G4
continua vermelho.

