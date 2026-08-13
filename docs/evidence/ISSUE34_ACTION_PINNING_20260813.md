# Issue #34 — GitHub Actions fixadas por SHA

Estado: **implementado e verde localmente / NO-GO remoto**  
Data: 2026-08-13  
Branch: `codex/issue34-actions-pinning`  
Base: `codex/pr17-no-demo-runtime` (`4476626`)

## Alteração

- Inventariados os dois workflows e todas as referências `actions/*`.
- `governance-quality.yml` passou a fixar `actions/checkout` e `actions/setup-python` pelos mesmos SHAs completos já aprovados em `ci.yml`, com comentário da versão legível.
- `ci.yml` e `governance-quality.yml` passaram a suportar `workflow_dispatch` para revalidação manual auditável.
- Dependabot já cobre `package-ecosystem: github-actions` semanalmente; não foi necessário alterar essa política.
- Foi adicionado um teste transversal que falha se qualquer workflow usar uma Action sem SHA completo ou não permitir disparo manual.

## Evidência local

- RED antes da correção: o novo teste rejeitou `ci.yml` sem `workflow_dispatch`.
- GREEN após a correção: `backend/tests/test_release_governance.py` — **5/5 passed**.
- Ruff focado — **verde**.
- Nenhum acesso, escrita ou migração foi feito na base de dados online.

## Limite de certificação

O aceite remoto do issue #34 continua bloqueado pelo issue #33: os runners GitHub falham antes de criar qualquer step por causa do estado de billing da conta. Não foram enfraquecidos nem ignorados checks. O PR deve permanecer draft/NO-GO até Backend, Frontend, Governance Quality e E2E executarem no mesmo SHA.
