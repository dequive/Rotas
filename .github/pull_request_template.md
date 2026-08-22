## Issue

Closes #<!-- numero obrigatorio -->

## Tipo

- [ ] Correccao
- [ ] Melhoria
- [ ] Nova funcao

## Mudancas e limites

<!-- O que mudou, o que ficou fora e contratos/migracoes afectados. -->

## Evidencia

- [ ] Arquitectura/arch-contract
- [ ] Lint, format e typecheck
- [ ] Testes unitarios e integracao
- [ ] Playwright E2E quando aplicavel
- [ ] Coverage/Codecov sem regressao
- [ ] Mutation testing quando o risco exige
- [ ] UX: skeleton/loading, progresso, estados, lazy loading e reduced-motion
- [ ] Observabilidade: trace/log/metrica/Sentry/alerta sem PII

Comandos, resultados e artefactos:

<!-- Nao use "passou" sem comando, contagem/resultado e ambiente. -->

## Risco, seguranca e dados

<!-- Tenant/RLS, RBAC, idempotencia, PII, migracao/backfill e compatibilidade. -->

## Deploy e rollback

- SHA/artefacto a promover:
- Ambiente e ordem:
- Smoke tests e sinais de GO/NO-GO:
- Rollback/reversao:

## Certificacao

- [ ] Esta PR prova implementacao/validacao local, nao certificacao runtime.
- [ ] A Issue so sera fechada apos deploy e verificacao pos-deploy do mesmo SHA.
