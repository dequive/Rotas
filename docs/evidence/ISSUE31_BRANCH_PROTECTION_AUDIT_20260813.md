# Issue #31 — Auditoria de branch protection

Estado: **parcial / NO-GO**
Data: 2026-08-13
Branch: `codex/issue31-branch-protection`
Base: `codex/engineering-standard` (`5540da7`, PR #32)

## Estado remoto observado

A API do GitHub confirmou proteccao clássica activa em `main`, `master` e na branch padrão `stabilization/p0-2026-q3`:

- status checks estritos: `Backend`, `Frontend` e `E2E`;
- dois approving reviews;
- stale review dismissal;
- CODEOWNER review e aprovação do último push exigidos;
- conversas resolvidas;
- admins sujeitos à protecção;
- histórico linear;
- force-push e deletion desactivados.

Não existe ruleset para cobrir futuras branches `stabilization/**`. O check `Issue PR Contract` ainda não é requerido. A configuração exigia CODEOWNER review, mas nenhum ficheiro `.github/CODEOWNERS` existia na branch protegida.

## Alteração versionável

- Adicionado `.github/CODEOWNERS` com owner padrão e escopos explícitos para GitHub, infra, backend, aplicações, Governance e documentação.
- Mantido o requisito de revisão independente; a presença de apenas um owner conhecido não é tratada como prova de independência.
- Actualizado o estado de adopção em `docs/ENGINEERING_STANDARDS.md`.

## Sequência segura de rollout

1. Resolver o bloqueio externo do issue #33 sem enfraquecer checks.
2. Obter dois reviewers independentes elegíveis.
3. Integrar o PR #32 e confirmar que `Issue PR Contract` executa num SHA válido e num inválido.
4. Integrar esta alteração de CODEOWNERS.
5. Criar ruleset para `main`, `master` e `stabilization/**`, exigindo `Backend`, `Frontend`, `E2E` e `Issue PR Contract`.
6. Exportar a configuração pela API, repetir os casos válido/inválido e obter revisão independente sem drift.

Adicionar `Issue PR Contract` antes de o workflow estar integrado e operacional criaria um bloqueio sem produtor confiável do status. Por isso nenhuma configuração remota foi alterada nesta etapa.

## Limites

- Billing GitHub continua bloqueado pelo issue #33.
- Nenhum check foi removido, ignorado ou tornado opcional.
- Nenhuma base de dados, segredo, ambiente de produção ou billing funcional foi tocado.
