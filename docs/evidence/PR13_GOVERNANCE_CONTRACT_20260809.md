# PR13 — Contrato ROTAS → Governance

Data: 2026-08-09

Branch: `codex/pr13-governance-contract`

Base: `0ceafe0` (`codex/pr12-outbox-producers`)

## Resultado

Estado: **done_local para os critérios próprios do PR13**; **não certificado
para release**.

O drainer do transactional outbox passou a enviar eventos para o contrato real
do adaptador ROTAS do Governance:

- `POST /api/v1/adapters/rotas/events`;
- autenticação `X-API-Key` obrigatória e fail-closed;
- envelope do produtor preservado, com identidade idempotente determinística;
- `409` tratado como entrega idempotente já aceite;
- `408`, `425`, `429` e `5xx` classificados como transitórios;
- restantes `4xx` classificados como falhas terminais de contrato/autorização.

Um teste de integração usa o drainer real do backend contra a aplicação FastAPI
real do Governance por ASGI. O primeiro envio criou uma ocorrência e caso; o
replay devolveu a mesma ocorrência.

## Defeitos descobertos e corrigidos pela integração real

### Identificadores humanos multi-tenant

`occurrences.numero` e `cases.reference` eram globais, apesar de a sequência ser
tenant-scoped. Dois tenants podiam gerar `EVT-AAAA-000001` ou
`CASE-AAAA-000001` e colidir.

A revisão Governance `0002` substitui unicidade global por:

- `UNIQUE (tenant_id, numero)`;
- `UNIQUE (tenant_id, reference)`.

Numa base vazia migrada, PostgreSQL confirmou ambos os constraints, RLS ativo e
`FORCE ROW LEVEL SECURITY` em `occurrences` e `cases`.

### Contexto RLS por transação

O tenant era configurado ao nível da sessão PostgreSQL. Depois de um `commit`,
a sessão SQLAlchemy podia obter outra conexão e perder o contexto; uma conexão
de pool também podia conservar contexto entre pedidos.

O Governance agora usa uma sessão própria e reaplica `app.tenant_id` com
`SET LOCAL` no início de cada transação. Isto mantém leituras pós-commit e evita
que o contexto sobreviva quando a conexão regressa ao pool.

### Migração, middleware e SLA

- O runner Alembic passou a usar `psycopg` síncrono, eliminando a falha do
  event loop Proactor no Windows; o runtime continua em `asyncpg`.
- O middleware de request ID já não mascara a exceção original quando o handler
  falha antes de produzir uma resposta.
- A abertura de caso usa o SLA da regra quando presente e, caso contrário, o
  SLA padrão do tipo de caso, restaurando a atividade inicial da timeline.

## Isolamento das bases locais

- A base ROTAS original `rotas`, na porta 55432, permaneceu online.
- Nenhuma migração do PR13 foi aplicada à base original.
- A suite backend completa usou a base descartável `rotas_pr13_gate`, criada e
  migrada separadamente até `rec13`.
- A suite Governance usou `governance_pr13_gate2`, no contentor descartável
  `rotas-pr13-governance-db`, migrada de vazio por `0001 -> 0002`.
- `GOVERNANCE_TEST_DATABASE_URL` passou a ser obrigatório; os testes falham
  antes de abrir uma conexão quando uma base descartável não é indicada.
- Não houve operação destrutiva sobre a base original.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| Contrato backend focado | 22 passed |
| Suite backend integral em DB descartável | 578 passed, 1 skipped |
| Suite Governance integral em DB migrada | 47 passed |
| Migração Governance vazia | `0001 -> 0002` |
| Constraints físicos tenant-scoped | confirmados |
| RLS físico em `occurrences` e `cases` | `rls=true`, `force=true` |
| Ruff backend | verde |
| Pyright backend | 0 erros, 0 avisos |
| OpenAPI backend | `c317303e447a3591896c8a1c7695dcc7f29b29affb76966b353f82d00fa7add1` |
| Ruff focado nos ficheiros Governance alterados | verde |
| `git diff --check` | verde |
| Alterações em billing | 0 ficheiros |

A suite backend emite um aviso herdado de depreciação Pydantic em
`app/modules/accounting/schemas.py`.

## Dívida anterior explicitamente não escondida

O gate Ruff global do Governance continua vermelho com 153 ocorrências
preexistentes. O `alembic check` global também deteta divergência histórica
entre o SQL canónico de `0001` e os modelos ORM (tipos, índices, FKs e
constraints). A revisão `0002` foi, contudo, aplicada numa base vazia e os seus
constraints foram verificados fisicamente.

Essa dívida não deve ser misturada silenciosamente no PR13; precisa de um PR de
reconciliação próprio antes de certificação de release do Governance.

## Limites preservados

- Billing não foi alterado.
- Retry com backoff, concorrência `SKIP LOCKED`, DLQ, alertas, reconciliação e
  replay operacional continuam no PR14.
- Não foi feita migração de produção, deploy, promoção de imagem nem teste live
  contra ambiente externo.

## Decisão de gate

- Critério PR13 — endpoint, autenticação, schema, idempotência e integração real
  local: **verde local**.
- G3 global: **yellow**, porque a resiliência operacional pertence ao PR14 e a
  dívida global Governance ainda não está reconciliada.
- Merge/promoção: **NO-GO** até revisão independente, CI remota e reprodução no
  SHA candidato/RC.
