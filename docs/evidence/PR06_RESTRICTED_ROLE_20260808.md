# PR-06 — Restricted application role and tenant isolation

Data: 2026-08-08

Base: PR-05 commit `51d3216`

## Veredicto

PR-06 está `done_local`. A aplicação passa a separar explicitamente a ligação
tenant-facing (`rotas_app`) da ligação administrativa (`rotas_admin`) e recusa
arrancar em produção se `DATABASE_URL` não for exatamente uma role
`NOSUPERUSER` e `NOBYPASSRLS` denominada `rotas_app`.

Este resultado ainda não torna G1 verde: PR-05 continua sem snapshot real
autorizado, a CI GitHub permanece bloqueada externamente e falta reprodução no
mesmo release candidate de produção.

## Fronteira implementada

- `DATABASE_URL`: API tenant-facing e RLS obrigatória;
- `ADMIN_DATABASE_URL`: autenticação bootstrap, onboarding, control-plane e
  operações administrativas;
- `ALEMBIC_DATABASE_URL`: migrations, distinta da ligação da aplicação em
  produção;
- o arranque de produção inspeciona `current_user`, `rolsuper` e
  `rolbypassrls` e falha antes de aceitar tráfego quando a role é privilegiada;
- o fixture fecha ambos os pools entre event loops, impedindo reutilização de
  ligações administrativas entre testes.

## Auditoria read-only

Relatório estruturado:
`docs/evidence/PR06_RLS_GATE_20260808.json`.

| Controlo | Resultado |
| --- | ---: |
| PostgreSQL | 16.14 |
| Tabelas tenant-scoped descobertas | 114 |
| Sem `ENABLE/FORCE RLS` | 0 |
| Sem policy canónica read/write | 0 |
| Grants CRUD ausentes em `rotas_app` | 0 |
| Grants CRUD ausentes em `rotas_admin` | 0 |
| Blockers do auditor | 0 |
| Decisão | PASS |

`rotas_app` foi validada por login direto: `LOGIN`, `NOSUPERUSER`,
`NOBYPASSRLS`. Não possui `CREATE` no schema, leitura de `platform_users` ou
`alembic_version`, nem mutação de `tenants`. `rotas_admin` é
`NOSUPERUSER/BYPASSRLS` e possui os grants exigidos pelos workers.

## Prova comportamental

A partição focada usou dois tenants com identificadores reais e cobriu:

- leitura invisível entre tenants;
- ausência de contexto produz zero linhas tenant-scoped;
- update de registo oculto afeta zero linhas;
- mudança de `tenant_id` é rejeitada pelo `WITH CHECK`;
- relação cross-tenant de OS/viatura é rejeitada;
- ficheiro de outro tenant retorna 404;
- clientes, viaturas, ordens de serviço, ficheiros e outbox;
- todas as tabelas tenant-scoped, policies, grants e atributos das roles.

Resultado:

```text
29 passed, 1 warning
backend completo: 546 passed, 1 skipped, 1 warning
Ruff: PASS
Pyright do escopo alterado: 0 errors
compileall: PASS
workflow YAML e evidence JSON: PASS
production startup with rotas_app: PASS
production startup with privileged DATABASE_URL: REJECTED
```

O warning é a depreciação Pydantic já conhecida em accounting schemas.
O Pyright global mantém exatamente um erro herdado em
`app/modules/billing/service.py` (`existing_paid` possivelmente não ligada).
PR-06 não altera nem oculta billing; todo o seu escopo passou com zero erros.
Uma primeira execução integral expôs reutilização do pool administrativo entre
event loops do pytest no Windows. O pool administrativo passou a usar
`NullPool` exclusivamente em `ENVIRONMENT=test`; os 30 testes afetados e a
suíte integral repetida terminaram verdes. O pooling de produção não mudou.

## Limites

- prova executada em PostgreSQL local, não em staging/produção;
- não substitui pentest, tráfego concorrente ou reprodução no SHA do RC;
- PR-05 e a CI remota continuam gates independentes;
- billing não foi alterado nem contornado.
