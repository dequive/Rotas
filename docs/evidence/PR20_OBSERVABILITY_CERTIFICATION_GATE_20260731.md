# PR-20 — Gate de Certificação de Observabilidade

Data da evidência: 2026-07-31  
Estado: `implemented_local_not_executed`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementado um agregador fail-closed para os cinco controlos PR-20 do
decisor G4: `metrics`, `logs`, `traces`, `alerts_delivered` e `slo_window`.
O contrato está verde localmente, mas o template devolve deliberadamente
`NO-GO`; nenhum stack remoto nem canal operacional foi certificado.

O output é um `release_evidence_fragment`. Só pode alimentar PR-20 quando
`passed=true`, os cinco controlos estão verdes e os doze relatórios JSON
físicos estão vinculados ao mesmo SHA.

## Contrato exigido

### Métricas

- Prometheus e target Backend saudáveis;
- zero falhas de avaliação de regras;
- dashboard `rotas-release-slos` com pelo menos dez painéis;
- quatro séries SLO canónicas;
- seis métricas de pool/event-loop/CPU;
- scan limpo de labels sensíveis.

### Logs e traces

- stores centralizados e pesquisáveis pelo SHA do release;
- correlação por request ID e controlo de acesso tenant-aware;
- zero findings de PII nos relatórios;
- retenção mínima de 30 dias para logs e sete para traces;
- traces de Backend, Governance e worker, quatro jornadas e uma falha real.

### Alertas

Cada um dos cinco alertas canónicos precisa de `firing`, entrega por canal
real, acknowledgement humano por papel e `resolved`, com quatro timestamps
ordenados e delivery ID.

### Janela SLO

- pelo menos 30 dias completos;
- cobertura mínima de 99%;
- amostras positivas;
- disponibilidade API e target de pelo menos 99,9%;
- latência p95 de no máximo 200 ms;
- zero dead-letter do outbox.

## Artefactos

- `backend/scripts/observability_certification.py`
- `backend/tests/test_observability_certification.py`
- `infra/observability/PR20_OBSERVABILITY_CERTIFICATION_CONTEXT.example.json`
- `docs/observability/PR20_OBSERVABILITY_RUNBOOK.md`
- `.github/workflows/ci.yml`

## Validação local

```text
Pytest do novo gate:         5 passed
Ruff:                        green
Pyright:                     0 errors, 0 warnings
Template JSON:               válido
Template execution:          NO-GO esperado
Stack/canal/RC externo:      não executado
```

## Bloqueadores mantidos

- Prometheus, Alertmanager, Grafana e stores de logs/traces não estão
  promovidos num staging RC;
- nenhum alerta foi entregue, reconhecido e resolvido por canal/on-call real;
- não existem exports runtime vinculados ao SHA;
- não existe janela SLO observada de 30 dias;
- os budgets de latência continuam vermelhos no PR-22;
- SRE/BE ainda não aprovaram os hashes nem os objectivos.

Conclusão: o contrato de certificação está implementado, mas PR-20 permanece
`in_progress` e G4 permanece vermelho.
