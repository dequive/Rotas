# PR13.2 — Paridade ORM/SQL do Governance

Data: 2026-08-09

Branch: `codex/pr13-2-governance-schema`

Base: `27fd7df` (`codex/pr13-1-governance-quality`)

## Resultado

Estado: **done_local para os critérios próprios do PR13.2**; **não certificado
para release**.

O metadata SQLAlchemy passou a representar fielmente o schema PostgreSQL
canónico criado pelas revisões Governance `0001 -> 0002`. O `alembic check`,
que anteriormente propunha alterações de tipos, remoção de FKs e índices e
troca incorreta de índices parciais por unique constraints, agora devolve:

```text
No new upgrade operations detected.
```

Nenhuma nova migração foi necessária: o defeito estava no metadata ORM, não no
schema físico canónico.

## Reconciliação aplicada

- FKs `tenant_id -> tenants.id ON DELETE CASCADE` modeladas em todas as tabelas
  onde o SQL canónico as exige.
- Constraints compostos tenant-scoped de taxonomia, catálogo, ocorrências,
  casos e regras de transição representados no ORM.
- Índices de tenant, consulta operacional e lookup de caso/ocorrência
  representados com os nomes físicos existentes.
- Índices idempotentes de ocorrências e transições modelados como índices únicos
  parciais com `WHERE idempotency_key IS NOT NULL`, não como constraints globais.
- Índice temporal `(tenant_id, occurred_at DESC)` representado no metadata.
- Tipos reconciliados: `TEXT`, `CHAR(64)` e `SMALLINT` onde definidos pelo SQL.
- O PK composto de `case_occurrences` deixou de ser duplicado por uma segunda
  unique constraint ORM.
- A FK diferida `fk_attachments_case` passou a conservar o nome canónico.

## Prova numa base vazia

Foi criada a base descartável `governance_pr13_schema_gate` no contentor local
`rotas-pr13-governance-db`.

| Verificação | Resultado |
| --- | --- |
| `alembic upgrade head` | `0001 -> 0002` |
| `alembic current` | `0002 (head)` |
| `alembic heads` | `0002 (head)` |
| `alembic check` | sem operações novas |
| Suite Governance sobre a base migrada | 47 passed |
| Ruff global | verde |
| Ruff format | 41 ficheiros conformes |
| OpenAPI | SHA-256 inalterado |

O hash OpenAPI permaneceu:
`ada727b9ca363c29ba21b65506ea5f0dc848a281d24f4dba06d9de52314bedc1`.

## Invariantes físicos

- 17 tabelas possuem `tenant_id`.
- 16 possuem FK física para `tenants`; `tenant_sequences` é a exceção explícita
  do SQL canónico.
- 16 tabelas tenant-scoped operacionais possuem `ENABLE/FORCE RLS`; `api_keys`
  permanece fora de RLS porque é consultada antes de a identidade tenant ser
  conhecida.
- 38 índices de aplicação foram materializados além dos PKs.
- Não há tabela que devesse ter FK tenant e esteja sem ela.
- Não há tabela operacional tenant-scoped sem RLS forçado.
- Os índices idempotentes parciais, identificadores humanos tenant-scoped e o
  índice temporal descendente foram confirmados por `pg_indexes`.

## Prevenção de regressão

O workflow `.github/workflows/governance-quality.yml` executa em PostgreSQL 16:

1. Ruff e verificação de formato;
2. migração de uma base vazia até `head`;
3. `alembic check` obrigatório;
4. suite Governance completa.

O gate é acionado por alterações no Governance, no outbox ROTAS integrado ou no
próprio workflow.

## Isolamento e limites

- Nenhuma migração ou operação destrutiva foi aplicada à base ROTAS original.
- Backend ROTAS e billing não foram alterados.
- A base criada para validação é descartável e separada da base original.
- O PR draft `#21` acionou o workflow Governance remoto, mas o run
  `31331162087` terminou em `startup_failure` antes de criar qualquer job. No
  mesmo evento, o CI global registou explicitamente que os jobs não arrancaram
  porque a conta GitHub está bloqueada por um problema de faturação. Isto é um
  bloqueio externo de execução, não evidência de aprovação do CI.
- Retry/backoff, `SKIP LOCKED`, DLQ e reconciliação operacional continuam no
  PR14.
- Não houve deploy, migração de produção ou promoção de imagem.

## Decisão de gate

- Critério PR13.2 — paridade ORM/SQL e migração vazia: **verde local**.
- A dívida histórica de `alembic check` do Governance está encerrada.
- Próximo passo sequencial: **PR14 — resiliência operacional do outbox**.
- Release global continua **NO-GO** até PR14, desbloqueio e execução efetiva da
  CI remota, revisão independente e reprodução no SHA candidato.
