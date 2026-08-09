# PR12 — Produtores críticos ligados ao transactional outbox

Data: 2026-08-09

Branch: `codex/pr12-outbox-producers`

Base: `0b43265` (`codex/pr11-unit-of-work`)

## Resultado

Estado: **done_local para os critérios próprios do PR12**; **não certificado
para release**.

O produtor central de exceções operacionais deixou de executar envio HTTP
fire-and-forget com `asyncio.create_task`. Exceções `high` e `critical` agora
persistem uma linha tenant-scoped no transactional outbox, na mesma sessão e
transação que a exceção, o alerta e os registos de audit. A entrega de rede fica
exclusivamente a cargo do worker após o commit.

Esse produtor é usado pelos fluxos críticos de carga, combustível, viagens,
oficina e checklists. Exceções `low` e `medium` permanecem internas e não criam
evento externo.

## Contrato do produtor

- `OutboxEvent.id` reutiliza o identificador da exceção para dar identidade
  determinística ao evento.
- `tenant_id`, `aggregate_type=operational_exception`, `aggregate_id` e
  `event_type` são persistidos com o payload.
- UUIDs e datas do payload são convertidos para JSON antes da gravação em
  `JSONB`.
- Uma repetição sequencial de `ensure_exception` devolve a exceção ativa e não
  cria outro evento.
- Rollback do chamador remove conjuntamente exceção, alerta, audit e outbox.
- Eventos de tenants diferentes permanecem identificados e isolados pelo seu
  `tenant_id`, inclusive quando referenciam o mesmo identificador operacional.

## Gate contra regressão

Um teste AST percorre `backend/app/**/*.py` e falha se encontrar:

- qualquer chamada `create_task(...)` ou `asyncio.create_task(...)`;
- import direto de `app.modules.governance.client` por um produtor.

O cliente legado permanece disponível dentro do módulo Governance, mas não
possui callsites no backend operacional. Novos produtores precisam entrar pelo
outbox.

## Limites preservados

- Nenhum ficheiro de billing foi alterado.
- O PR12 não muda o endpoint, autenticação ou schema usado para entregar ao
  Governance; essa correção pertence ao PR13.
- Retry, DLQ, alertas operacionais, reconciliação e replay pertencem ao PR14.
- Não foram adicionados produtores internos de faturação nem alterações ao
  domínio fiscal.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| Testes focados de produtores e exceções | 6 passed |
| Suite backend integral | 564 passed, 1 skipped |
| Pyright `pyright-ci.json` | 0 erros, 0 avisos |
| Ruff em `app`, `tests` e `scripts` | verde |
| Gate AST de fire-and-forget | 0 violações |
| Pesquisa `create_task` no backend | 0 ocorrências |
| OpenAPI determinístico | `c317303e447a3591896c8a1c7695dcc7f29b29affb76966b353f82d00fa7add1` |
| `git diff --check` | verde |
| Alterações em código-fonte billing | 0 |

A primeira tentativa da suite integral foi interrompida quando PostgreSQL e
Redis foram encerrados simultaneamente pelo runtime local. Ambos apresentaram
saída 255 e `OOMKilled=false`. Depois de reiniciar os mesmos contentores, a
suite integral aprovou sem mudança de código.

A suite emite um aviso herdado de depreciação do `Config` Pydantic em
`app/modules/accounting/schemas.py`; não representa falha do PR12.

## Decisão de gate

- Critério PR12 (produtores críticos no outbox e zero `create_task`): **verde
  local**.
- G3 global: **yellow**, porque contrato real de entrega, retry, DLQ e
  reconciliação pertencem aos PRs seguintes.
- Merge/promoção: **NO-GO** até revisão independente, CI remota, integração da
  pilha e reprodução no SHA candidato/RC.
