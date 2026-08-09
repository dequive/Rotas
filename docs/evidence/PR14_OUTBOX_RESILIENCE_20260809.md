# PR14 — Resiliência operacional do outbox Governance

Data: 2026-08-09

Branch: `codex/pr14-outbox-resilience`

Base: `615e7a5` (`codex/pr13-2-governance-schema`)

## Resultado

Estado: **done_local para os critérios próprios do PR14**; **não certificado
para release**.

O canal ROTAS -> Governance passou de uma seleção simples de linhas pendentes
para uma entrega at-least-once com claim transacional, lease, concorrência
`FOR UPDATE SKIP LOCKED`, retry limitado, DLQ, replay auditado e reconciliação
por recibo canónico do Governance.

## Entrega concorrente e recuperação

- Cada ciclo reclama um lote numa transação PostgreSQL curta.
- O claim grava `processing`, proprietário, instante e expiração do lease.
- A transação é confirmada antes do HTTP; não há row lock durante a chamada de
  rede.
- A finalização usa `id + status + claimed_by`; um worker que perdeu o lease não
  pode sobrescrever o novo proprietário e incrementa `lost_claim`.
- Claims expirados ou legados sem expiração podem ser retomados por outro
  worker.
- Crash depois da entrega e antes da finalização pode provocar redelivery; a
  chave idempotente do Governance transforma essa duplicação possível em
  entrega lógica única.

## Retry e DLQ

- Backoff limitado: 60 s, 5 min, 30 min, 2 h, 12 h e 24 h.
- `408`, `425`, `429`, `5xx` e falhas HTTP permanecem retryable.
- `409` é sucesso idempotente.
- Outros `4xx` são terminais e seguem imediatamente para `dead_letter`.
- Erros persistidos são códigos sanitizados e limitados a 500 caracteres; o
  payload e respostas externas não são copiados para `last_error`.
- `attempt_count` representa o ciclo após o último replay;
  `total_attempt_count` preserva o total vitalício.

## Replay e operação

Foram adicionados endpoints platform-scoped:

- `GET /api/v1/platform/outbox/health` — `platform_admin` e
  `platform_support`;
- `GET /api/v1/platform/outbox/dead-letters` — leitura e filtro por tenant sem
  exposição do payload;
- `POST /api/v1/platform/outbox/{event_id}/replay` — apenas `platform_admin`,
  com motivo obrigatório.

O replay conserva operador, motivo, instante e contador, renova o orçamento de
tentativas e não permite replay de eventos fora de DLQ. A mutação e a entrada
imutável em `platform_audit_logs` são confirmadas na mesma transação.

## Reconciliação

O Governance expõe um recibo tenant-scoped por `idempotency_key`:

`GET /api/v1/adapters/rotas/events/receipt`

O recibo devolve `occurrence_id`, número, `case_id` e referência de caso. Isto
recupera a prova completa quando uma entrega idempotente não devolveu o caso no
replay.

Reconciliações usam claim curto e backoff próprios. Recibos ausentes não são
consultados a cada minuto, e uma reconciliação concorrente perdida não pode
sobrescrever o proprietário atual.

## Migração e schema físico

A revisão `rec14` foi aplicada desde uma base PostgreSQL 16 vazia no contentor
descartável `rotas-pr14-backend-db`, porta `55435`.

| Verificação | Resultado |
| --- | --- |
| `alembic upgrade head` | `rec14 (head)` |
| `alembic check` | sem operações novas |
| RLS de `outbox_events` | `ENABLE` e `FORCE` |
| Constraint de estados | `ck_outbox_events_status` |
| Índice de dispatch | `ix_outbox_events_dispatch` |
| Índice de lease | `ix_outbox_events_claim_expiry` |
| Campos operacionais novos | 14 confirmados |
| CRUD `rotas_app` | confirmado; papel NOBYPASSRLS |
| CRUD `rotas_admin` | confirmado; papel administrativo |
| Gate PR-06 | PASS; 114 tabelas tenant-scoped, zero gaps |
| Contrato PR-00 | VALID |

## Testes e contratos

| Gate | Resultado |
| --- | --- |
| Backend completo no working tree final | 588 passed, 1 skipped |
| Governance completo | 49 passed |
| PR14 focado backend | 10 passed |
| Contrato ASGI ROTAS -> Governance | entrega, replay e recibo aprovados |
| Pyright backend completo (`pyright-ci.json`) | 0 erros |
| Ruff do gate CI (`app`, `tests`, scripts de release) | verde |
| Ruff global Governance | verde |
| OpenAPI canónico | SHA-256 `879facecdfc6442b25ac57c01ee360854e283c0d56fb53023849d2bd51222200` |
| Cliente Manager gerado | `openapi-typescript --check` verde |

## Limites e dívida fora do PR14

- O Ruff global sobre absolutamente todos os ficheiros do diretório backend
  ainda encontra 50 violações históricas fora do gate CI, concentradas em
  migrações antigas e scripts auxiliares de raiz; não foram corrigidas aqui.
- O typecheck global do Manager (`--incremental false`) continua com seis erros preexistentes em
  `WorkOrderDetail.test.tsx`, `analytics/page.tsx` e `sheet.tsx`. O cliente
  OpenAPI gerado está sincronizado.
- A suite backend mantém dois testes explicitamente skipped e um warning
  Pydantic histórico em `accounting/schemas.py`.
- A CI GitHub permanece incapaz de iniciar jobs enquanto a conta estiver
  bloqueada por faturação. Billing ROTAS e a configuração da conta não foram
  alterados.
- Não houve carga, soak, chaos, deploy, migração de produção nem validação
  externa independente.

## Isolamento e segurança

- A base ROTAS original online não foi consultada, migrada ou modificada.
- A única base backend modificada foi `rotas_pr14`, criada para descarte.
- Billing ROTAS tem zero alterações.
- Endpoints operacionais são platform-scoped; tokens tenant não atravessam o
  guard de plataforma.
- Listagens de DLQ não devolvem payloads potencialmente sensíveis.

## Decisão de gate

- Critério PR14 — retry, concorrência, DLQ, replay e reconciliação:
  **verde local**.
- O conjunto PR13/PR14 pode seguir para revisão e integração controlada.
- Release global continua **NO-GO** até execução real da CI remota, revisão
  independente, ensaio production-like no SHA candidato e gates operacionais
  de carga, soak, observabilidade e recuperação.
