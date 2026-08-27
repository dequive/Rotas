# PR-00 Release Governance Baseline — 2026-08-01

## Objetivo

Formalizar owners, feature freeze, política de branch e formação do release
candidate sem confundir um contrato versionado com controlos aplicados no
GitHub.

## Contrato implementado

- `infra/release/PR00_RELEASE_GOVERNANCE.json` define as oito funções da
  secção 15.3, freeze P0/P1 e política mínima de branch/RC;
- `.github/CODEOWNERS` cobre o repositório e os escopos críticos;
- `backend/scripts/validate_release_governance.py` valida o contrato de forma
  fail-closed;
- a CI valida o contrato e passa a executar em `stabilization/**`;
- `backend/tests/test_release_governance.py` cobre o caso válido, owner ausente,
  branch policy fraca e escopo CODEOWNERS ausente.

Resultado local:

```text
policy:          PR00-RELEASE-GOVERNANCE-V1
decision:        VALID
roles:           8
distinct owners: 1
tests:           4 passed
Ruff:            green
JSON:            valid
```

`VALID` significa somente que o contrato fonte está completo. Não prova
proteção de branch, revisão, CI remota ou formação de RC.

## Auditoria remota inicial

Consulta ao repositório `dequive/Rotas` em 2026-08-01:

- repositório público, default branch `master`;
- único colaborador: `dequive`, com papel `admin`;
- `master` em `9594b9f308a287400e0424166194b6429d65e77b`, sem proteção;
- `main` em `549747973ce0b892f07644b189d87a738da09f6b`, sem proteção;
- nenhum ruleset configurado;
- branch remota `stabilization/p0-2026-q3` inexistente; a consulta de proteção
  devolveu HTTP 404.

Estado local auditado:

- branch `stabilization/p0-2026-q3`;
- HEAD `d8a8e52b5f1cb98ef4fd805c945fd70674c98e25`;
- 525 entradas modificadas/não rastreadas no working tree no momento da
  auditoria.

## Correções GitHub aplicadas

- `stabilization/p0-2026-q3` foi publicada no SHA
  `d8a8e52b5f1cb98ef4fd805c945fd70674c98e25`, sem incluir o working tree;
- branch limpa `codex/pr00-github-governance` e commit
  `1012ecf718b7a211a71d49904b5a8434c5affd43` contêm somente oito ficheiros de
  governança/CI;
- PR `https://github.com/dequive/Rotas/pull/1` foi aberto contra a branch de
  estabilização;
- `master`, `main` e `stabilization/p0-2026-q3` ficaram protegidas inclusive
  para admins: PR obrigatório, dois approvals, CODEOWNERS, stale-review
  dismissal, aprovação distinta do último push, conversas resolvidas, histórico
  linear, checks Backend/Frontend/E2E, sem force-push ou delete;
- vulnerability alerts, Dependabot security updates, secret scanning, push
  protection e private vulnerability reporting foram activados;
- Actions passou a aceitar somente actions GitHub-owned, exigir SHA pinning,
  usar token read-only e impedir aprovação de PR por workflow;
- auto-merge, update branch e delete-after-merge foram activados;
- a default branch foi alterada de `master` para
  `stabilization/p0-2026-q3` após autorização explícita e a proteção foi
  revalidada;
- a auditoria de secret scanning encontrou zero alertas abertos.

O PR está `BLOCKED`: Backend e Frontend falharam antes de qualquer step e E2E
foi skipped. As duas annotations confirmam a causa externa exacta: a conta
GitHub está locked por billing. O scan multi-ecossistema do Dependabot passou
a revelar 60 findings abertos: 26 high, 30 medium e 4 low. A issue
`https://github.com/dequive/Rotas/issues/2` rastreia billing, reviewers, checks,
default branch e merge.

## Blockers de fecho

1. Regularizar o billing da conta GitHub e repetir os checks do PR 1.
2. Nomear pessoas responsáveis. `dequive` é owner interino das oito funções,
   como permitido pelo plano, mas uma única identidade não consegue produzir
   duas revisões independentes nem os sign-offs segregados exigidos por G4.
3. Obter dois approvals e mergear o PR 1 somente depois de Backend, Frontend e
   E2E passarem.
4. Tratar os 60 alerts Dependabot multi-ecossistema através do PR-18; a
   mudança da default branch não substitui remediação, waiver ou reteste.
5. Curar as 525 alterações locais e formar o próximo RC limpo.
6. Secret-scanning validity checks e non-provider patterns permaneceram
   indisponíveis/desactivados pela plataforma e não foram alegados como verdes.

## Decisão

PR-00 permanece `in_progress`. Branch, proteção e controlos GitHub foram
aplicados e a estabilização é agora default; revisão independente, billing/CI
verde, merge do contrato e RC limpo continuam ausentes. G0 não é promovido.
