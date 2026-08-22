# PR-20 — Baseline de SLI, SLO e Alertas

Data da evidência: 2026-07-27  
Estado: `in_progress`  
Gate afectado: G4 — Production Operations

## Resultado

Foi implementada uma baseline local, provider-neutral, para observabilidade do
release candidate. Ela torna métricas, regras, dashboard e routing
reproduzíveis, mas não prova entrega de alertas, traces ou SLOs num staging real.

O código já possuía:

- métricas HTTP Prometheus em `/metrics`;
- contador de outcomes do transactional outbox;
- logs estruturados com request ID e scrub de PII;
- Sentry opcional no Backend, Manager e Driver;
- `/health/deep` com PostgreSQL, Redis e heartbeat do worker.

O PR-20 acrescentou:

- Prometheus 3.11.3 distroless por digest;
- Alertmanager 0.32.1 por digest e webhook em secret externo;
- Grafana 13.1.0 por digest, sem acesso anónimo ou self-signup;
- rede interna de observabilidade e zero exposição pública de Prometheus ou
  Alertmanager;
- dashboard provisionado `rotas-release-slos`, com sete painéis;
- quatro SLIs canónicos e cinco alertas com severity, owner e runbook;
- validação fail-closed que proíbe identificadores de tenant, utilizador,
  documento ou evento nas superfícies Prometheus.

Fontes das versões:

- https://github.com/prometheus/prometheus/releases/tag/v3.11.3
- https://github.com/prometheus/alertmanager/releases/tag/v0.32.1
- https://github.com/grafana/grafana/releases/tag/v13.1.0

## Catálogo inicial

| SLI | Objectivo inicial | Fonte | Alerta |
| --- | --- | --- | --- |
| Disponibilidade da API | 99,9% em 30 dias | `http_requests_total` | `RotasApiHighErrorRate` |
| Latência API p95 | menor ou igual a 200 ms | histogram HTTP | `RotasApiLatencyBudget` |
| Dead-letter do outbox | zero | outcomes do outbox | `RotasOutboxDeadLetter` |
| Target de métricas backend | 99,9% em 30 dias | `up` | `RotasBackendDown` |

O catálogo canónico está em
`docs/observability/ROTAS_SLO_CATALOG.json`. Estes objectivos ainda exigem
aprovação formal de Produto/SRE e medição sob carga real.

## Gates locais reproduzidos

```text
Validador da política:                4 SLOs, 5 alertas, 7 painéis, 3 imagens
Pytest observabilidade/staging:       11 passed
Ruff:                                 green
Pyright:                              0 erros, 0 warnings
promtool check config:                SUCCESS
promtool check rules:                 SUCCESS — 10 rules
promtool test rules:                  SUCCESS
amtool check-config:                  SUCCESS — 1 receiver
Compose config:                       green
Grafana /api/health:                  database=ok, version=13.1.0
Dashboard Grafana:                    uid=rotas-release-slos provisionado
```

Os testes temporais provaram firing das cinco condições e resolução do alerta
de target down. O container Grafana usado no smoke foi removido no fim.

## Limites e evidência ainda necessária

- Prometheus, Alertmanager e Grafana ainda não foram promovidos para staging;
- nenhum alerta foi entregue por um canal real nem reconhecido pelo on-call;
- não existe ainda stack central de logs nem retenção pesquisável comprovada;
- Sentry continua opcional e não há traces correlacionados no SHA do RC;
- não há SLO/burn-rate por tenant; acrescentar `tenant_id` como label
  Prometheus foi deliberadamente proibido por privacidade e cardinalidade;
- os thresholds ainda não foram validados por PR-22 sob carga, concorrência e
  rede degradada;
- não existe janela de 30 dias nem cálculo de error budget real;
- acesso, backup e restore do Grafana/Prometheus não foram exercitados;
- falta testar todos os alertas ponta a ponta até `firing`, entrega,
  acknowledge e `resolved`.

Assim, PR-20 está `in_progress`, não `done_local`, e G4 permanece vermelho.
