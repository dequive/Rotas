# PR11 — Unit of Work por caso de uso crítico

Data: 2026-08-09

Branch: `codex/pr11-unit-of-work`

Base: `40c3a58` (`codex/pr10-http-contract`)

## Resultado

Estado: **done_local para os critérios próprios do PR11**; **não certificado
para release**.

A fronteira HTTP idempotente passou a ser uma unidade transacional única. A
reserva da chave, a mutação de negócio, audit, movimentos contabilísticos,
eventual linha de outbox e resposta persistida são confirmados em conjunto. Se
o caso de uso falhar, todos os efeitos dessa sessão são revertidos, incluindo
`commit()` legado chamado por serviços internos. Sessões auxiliares continuam
independentes e não são capturadas pela fronteira.

O pagamento a fornecedor é a implementação vertical de referência: bloqueia a
fatura com `FOR UPDATE`, calcula o saldo confirmado, impede sobrepagamento,
valida as contas antes da mutação e grava pagamento, estado da fatura, diário,
audit e resposta idempotente na mesma transação.

## Contratos e isolamento

- `Idempotency-Key` é obrigatório em
  `POST /api/v1/payables/invoices/{invoice_id}/pay`.
- A repetição com a mesma chave e payload devolve a resposta original sem criar
  outro pagamento, diário ou audit.
- Duas chaves concorrentes para a mesma fatura são serializadas pelo lock: uma
  liquidação integral confirma e a outra recebe HTTP 409.
- Uma falha após um `commit()` interno reverte mutação, audit, outbox e reserva
  idempotente; um commit executado numa sessão auxiliar permanece confirmado.
- O contrato OpenAPI e o cliente Manager foram regenerados para refletir o
  header obrigatório.

## Limites preservados

- Nenhum ficheiro em `backend/app/modules/billing/` foi alterado; billing
  permaneceu funcionalmente congelado.
- O PR11 prova que uma linha de outbox participa atomicamente na unidade de
  trabalho, mas não liga novos produtores. Essa integração permanece no PR12.
- Retry, DLQ, reconciliação e operação do outbox permanecem nos PRs 12–14.

## Evidência local

| Verificação | Resultado |
| --- | --- |
| Testes focados UoW/idempotência/pagamento | 6 passed |
| Partição financeira e idempotência anterior à revisão final | 65 passed |
| Suite backend integral | 559 passed, 1 skipped |
| Papel restrito/RLS + contrato OpenAPI | 11 passed |
| Ruff em `app`, `tests` e `scripts` | verde |
| Pyright `pyright-ci.json` | 0 erros, 0 avisos |
| OpenAPI determinístico | `c317303e447a3591896c8a1c7695dcc7f29b29affb76966b353f82d00fa7add1` |
| Cliente TypeScript gerado (`--check`) | verde |
| `git diff --check` | verde |
| Alterações em código-fonte billing | 0 |

A suite emite um aviso herdado de depreciação do `Config` Pydantic em
`app/modules/accounting/schemas.py`; não representa falha do PR11.

Após a suite integral, o teste de rollback foi reforçado para comprovar também
audit e outbox. A partição afetada foi repetida e aprovou 6 testes; não houve
alteração posterior em código de produção.

## Decisão de gate

- Critério PR11 (mutação, audit, movimentos e outbox atómicos): **verde local**.
- G3 global: **yellow**, porque os produtores, entrega, DLQ e reconciliação
  pertencem aos PRs seguintes e ainda precisam das respetivas provas.
- Merge/promoção: **NO-GO** até revisão independente, CI remota, integração da
  pilha de PRs e reprodução no SHA candidato/RC.
