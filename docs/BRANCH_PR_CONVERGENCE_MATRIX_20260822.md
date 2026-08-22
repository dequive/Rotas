# Matriz Canónica de Convergência de Branches e PRs — 2026-08-22

- Estado: vinculativo para C0
- Fonte remota consultada: GitHub, 2026-08-22
- Branch de integração: `codex/issue42-convergencia-manager-driver-backend`
- Commit documental de partida: `ddb04dad59f524398765e5c43e5da54968bbc47c`
- Decisão de release: `NO-GO`

## 1. Finalidade

Esta matriz impede merges em cadeia, cherry-picks por intuição e regras
divergentes entre agentes. Cada linha Git aberta recebe um destino explícito e
uma prova obrigatória antes de ser encerrada.

As classificações significam:

- **INTEGRAR:** linha canónica onde C0-C4 serão consolidados;
- **PORTAR:** extrair apenas commits/ficheiros contratuais identificados, com
  teste RED na linha canónica antes da implementação;
- **SUBSTITUIR:** não fundir; fechar quando a linha canónica provar paridade do
  resultado e preservar a evidência aplicável;
- **DEFERIR:** não tocar antes do gate/dependência indicado;
- **DESCARTAR:** fechar sem port quando a função contradiz o contrato atual ou
  já foi substituída com prova.

Nenhuma classificação equivale a autorização de merge ou release.

## 2. Topologia verificada

- Existem **29 PRs abertos**.
- O PR #44 está `BLOCKED`, exige revisão e o check `Issue PR Contract` falha.
- A pilha #1 -> #5 -> #9..#24 -> #36 -> #38 é divergente da linha #44; os
  respetivos tips não são ancestrais da branch canónica.
- A branch #41 tem 75 commits exclusivos e está 41 commits atrás da branch
  canónica. Contém a experiência Android aprovada e também toda a pilha antiga;
  por isso não pode ser fundida integralmente.
- Os commits `ebb583b` e `50955e1` fecham partes do lifecycle documental do
  Driver, mas só existem na linha #41.
- `codex/engineering-standard` é ancestral da linha canónica. CODEOWNERS e
  pinning integral de Actions continuam fora dela.
- Os worktrees existentes pertencem a linhas ativas ou históricas e não devem
  ser removidos durante C0-C4.

## 3. Matriz por PR aberto

| PR | Assunto/linha | Decisão C0 | Conteúdo a preservar | Condição de fecho |
|---|---|---|---|---|
| #44 | Issue #42 — convergência Manager/Driver/backend | **INTEGRAR** | única linha para C0-C4 | CI executa, revisão independente e todos os P0/P1 fechados; até lá sem merge |
| #41 | Issue #25 — Android, jornadas e documentos | **PORTAR** | shell mobile, viagens atribuídas/histórico, documentos/pedidos, cache de sessão, telemetria sem PII, validador externo; incluindo intenção de `ebb583b`/`50955e1` | cada vertical portada com RED/GREEN na #44; depois substituir #41 |
| #40 | CODEOWNERS | **PORTAR** | contrato CODEOWNERS de `09764a0` | regra presente e validada na #44; depois substituir #40 |
| #39 | pinning de Actions empilhado | **SUBSTITUIR** | nenhum merge da pilha; comparar apenas o pinning final | #35 portado e gate de pins verde na #44 |
| #38 | remoção de demo runtime | **SUBSTITUIR** | ausência de fallback demo | gate `no-demo-runtime` e jornadas reais verdes na #44 |
| #37 | Dependabot nanoid | **DEFERIR** | advisory, lockfile e alcance runtime | depois de C0-C4, PR próprio, CI completo e revisão supply-chain |
| #36 | identidade offline Driver | **SUBSTITUIR** | isolamento tenant/driver/sessão e purge | ownership/device/replay provados na #44 e vertical #41 portada |
| #35 | pinning isolado de Actions | **PORTAR** | commit isolado `9ad9355` ou patch mínimo equivalente | todas as Actions por SHA imutável e validador verde na #44 |
| #32 | padrão Issue->PR->Deploy | **SUBSTITUIR** | regra já ancestral + instruções canónicas atuais | confirmar paridade do contrato remoto e fechar #32 sem novo merge |
| #24 | lifecycle offline Driver | **SUBSTITUIR** | retry, conflito, dead-letter e recuperação | suite C1/C2 equivalente verde na #44 |
| #22 | resiliência do outbox | **SUBSTITUIR** | replay/reconciliação idempotentes | paridade focada e gates outbox verdes na #44 |
| #21 | schema Governance | **SUBSTITUIR** | reconciliação ORM/SQL | Alembic vazio + upgrade histórico + testes Governance verdes na #44 |
| #20 | qualidade Governance | **SUBSTITUIR** | Ruff/qualidade sem dívida | Ruff global verde na #44 |
| #19 | contrato Governance | **SUBSTITUIR** | auth, schema, idempotência e tenant scope | testes de contrato reais verdes na #44 |
| #18 | produtores via outbox | **SUBSTITUIR** | atomicidade dos eventos críticos | zero dispatch não transacional e testes de rollback verdes na #44 |
| #17 | unit of work | **SUBSTITUIR** | transações críticas atómicas | testes de rollback/concorrência verdes na #44 |
| #16 | contrato HTTP comum | **SUBSTITUIR** | timeout, retry seguro, erro e idempotência | gates HTTP Manager/Driver verdes na #44 |
| #15 | cliente OpenAPI | **SUBSTITUIR** | geração e drift bloqueante | schemas públicos completos, cliente regenerado e drift zero na #44 |
| #14 | fronteira Manager BFF | **SUBSTITUIR** | browser sem token/API direta | gates BFF/no-direct-api verdes na #44 |
| #13 | entitlements da plataforma | **SUBSTITUIR** | tenant não autoativa módulos | testes platform-admin/tenant negativos verdes na #44 |
| #12 | role restrita e RLS | **SUBSTITUIR** | `NOBYPASSRLS`, FORCE RLS e separação admin/app | prova runtime cross-tenant com role restrita na #44 |
| #11 | snapshot/upgrade | **SUBSTITUIR** | restore, fingerprint, locks e forward-fix | snapshot autorizado, rollback e upgrade histórico provados no RC |
| #10 | base vazia Alembic | **SUBSTITUIR** | zero-to-head e drift check | `upgrade head` + `check` em PostgreSQL vazio na #44 |
| #9 | Pyright | **SUBSTITUIR** | gate tipado bloqueante | zero erros Pyright na #44 |
| #8 | Dependabot Next/Sentry/PostCSS | **DEFERIR** | advisories e alcance runtime | depois de C0-C4; separar upgrades e provar build/runtime |
| #7 | Dependabot fast-uri | **DEFERIR** | advisory e grafo transitivo | depois de C0-C4; PR isolado e CI completo |
| #6 | Dependabot undici | **DEFERIR** | advisory e alcance runtime | depois de C0-C4; PR isolado e CI completo |
| #5 | Ruff histórico | **SUBSTITUIR** | baseline Ruff zero | Ruff global verde na #44 |
| #1 | governação GitHub inicial | **SUBSTITUIR** | proteções, checks e política de release | C0/C3 e controlos remotos provados na #44 |

## 4. Ordem de execução C0-C4

1. **C0:** manter freeze, publicar esta matriz e bloquear merges integrais.
2. **C1:** fechar autorização/ownership Driver e Sync por testes de abuso.
3. **C2:** portar de #41, uma vertical por vez, as jornadas mobile aprovadas.
   Estado parcial: `5286fe1` fechou a fronteira negativa de persona na PWA e
   `e70e79b` publicou Minhas Viagens/histórico tenant+driver-scoped. UI dessas
   listas, documentos/pedidos, terminal read-only, E2E e Android permanecem.
4. **C3:** portar #35/#40, fechar Pyright/OpenAPI e recuperar CI executável.
5. **C4:** criar um RC único, executar staging, Android físico, Sentry, segurança,
   observabilidade e piloto no mesmo SHA/artefactos.

O fecho remoto dos PRs substituídos só ocorre após a evidência indicada. C0 não
autoriza encerrar PRs antes da paridade, nem apagar branches/worktrees.

## 5. Responsabilidade e evidência

| Trabalho | Owner | Dependência | Evidência mínima |
|---|---|---|---|
| decisão e freeze C0 | TL + PO | nenhuma | matriz versionada, PR #44 sem merge |
| Driver/Sync C1 | BE + SEC + QA | C0 | testes negativos com JWT Driver real e base de dados |
| jornadas Driver C2 | FE-D + BE + PO | C1 | unit/integration/E2E + Android físico |
| contratos/CI C3 | TL + BE + FE + QA | C2 | Pyright, OpenAPI, builds, Actions por SHA e CI com passos executados |
| certificação C4 | SRE + SEC + QA + PO | C3 | mesmo SHA/RepoDigest em staging, observabilidade, dispositivo e piloto |

Se uma prova de paridade falhar, a linha é reclassificada de **SUBSTITUIR** para
**PORTAR** apenas no item faltante, nunca para merge integral.
