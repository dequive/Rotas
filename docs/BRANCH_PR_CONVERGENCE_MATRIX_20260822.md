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
| #37 | Dependabot nanoid e advisories atuais | **PORTADO LOCALMENTE EM C3** | slice próprio `0271ae0`, lockfile regenerado, alcance runtime e regressão; sem `audit fix --force` | auditorias e gate PR18 verdes localmente; falta CI completa e revisão supply-chain independente |
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
| #8 | Dependabot Next/Sentry/PostCSS | **ABSORVIDO LOCALMENTE EM C3** | advisories, Next/SWC `16.3.3`, lockfile e alcance runtime validados em `0271ae0`; sem merge cego do PR antigo | auditorias zero, testes e builds locais verdes; falta CI completa e revisão supply-chain independente |
| #7 | Dependabot fast-uri | **ABSORVIDO LOCALMENTE EM C3** | advisory e grafo transitivo reconciliados pelo lockfile limpo de `0271ae0`; sem merge cego do PR antigo | auditorias zero e árvore aceite localmente; falta CI completa e revisão supply-chain independente |
| #6 | Dependabot undici | **ABSORVIDO LOCALMENTE EM C3** | advisory e alcance runtime reconciliados pelo lockfile limpo de `0271ae0`; sem merge cego do PR antigo | auditorias zero e árvore aceite localmente; falta CI completa e revisão supply-chain independente |
| #5 | Ruff histórico | **SUBSTITUIR** | baseline Ruff zero | Ruff global verde na #44 |
| #1 | governação GitHub inicial | **SUBSTITUIR** | proteções, checks e política de release | C0/C3 e controlos remotos provados na #44 |

## 4. Ordem de execução C0-C4

A taxonomia e as dependências foram reconciliadas pela `ADR-011`, mas não
alteram esta fila. O alinhamento comercial de módulos/entitlements pertence a
E0 e só começa depois de C0-C4 e Cliente/Terceiro.

1. **C0:** manter freeze, publicar esta matriz e bloquear merges integrais.
2. **C1:** fechar autorização/ownership Driver e Sync por testes de abuso.
3. **C2:** portar de #41, uma vertical por vez, as jornadas mobile aprovadas.
   Estado parcial: `5286fe1` fechou a fronteira negativa de persona na PWA e
   `e70e79b` publicou Minhas Viagens/histórico tenant+driver-scoped. UI dessas
   listas permanece. `710dc9f` publicou requisitos/documentos e pedidos
   idempotentes, reconciliou pedidos com emissão pelo gestor e bloqueou
   mutações documentais terminais. `4d439ed` fechou localmente o download
   Driver ownership-scoped para storage local/R2. `426e865` publicou a nova
   navegação, listas/histórico paginados, detalhe, documentos e pedidos na PWA.
   `d3b24e1` reconciliou a checklist Manager com a política canónica;
   `443e217` + `22ae117` implementaram cache/recovery das novas leituras por
   identidade e ampliaram Playwright para `4/4`; `1513913` fechou pedido,
   download e erro recuperável em `6/6`. `e0078c6` repetiu backend `980/980`,
   Manager `128/128`/build e Driver `38/38`/build/E2E `6/6` no mesmo HEAD de
   produto. A execução exploratória de 2026-08-24 num Redmi confirmou a jornada
   principal, mas ocorreu sobre working tree sem SHA e não fecha o gate. A
   `ADR-012` acrescenta ao mesmo C2, antes da certificação Android, o diário
   imutável de checklist/combustível/despesas/despacho, contratos Driver de
   leitura e a navegação Hoje/Viagens/Registos/Mais. O primeiro slice da
   ADR-012 removeu localmente o update de combustível no Driver/Sync e passou
   `66/66` focados. `rec15` fez o widen nullable de `trip_id` para checklist e
   combustível, com ownership, FK composta e sem backfill heurístico;
   Driver/Sync/OpenAPI/checklist/fuel `85/85`, backend `987/987`, Ruff, Pyright,
   OpenAPI/cliente e Manager typecheck ficaram verdes. O slice seguinte publicou
   as quatro coleções Driver paginadas e ownership-scoped; despesas mostram
   apenas movimentos pagos pelo motorista e despacho usa `DriverAdvance`, sem
   notas/IDs internos. Driver/OpenAPI `58/58`, backend `1003/1003`, Ruff,
   Pyright, OpenAPI `003054...90f0c`, cliente e Manager typecheck ficaram verdes.
   O slice `rec16` fechou localmente ator/visibilidade e correção de despesas:
   snapshot do motorista, backfill determinístico, trigger append-only, ajuste/
   estorno com lock, idempotência, auditoria e DTOs tipados. Partição `81/81`,
   backend `1009/1009`, Ruff/Pyright, OpenAPI `be1f22...2049d`, Manager
   `128/128`, auditor `208/158/0` e build 74 páginas verdes. O slice PWA seguinte
   publicou cliente/cache segregado, Hoje/Viagens/Registos/Mais e estados
   operacionais completos; Driver `55/55`, build `1805/93/6` e Playwright
   mobile `7/7` ficaram verdes. Sem SHA/PR não há promoção; Android físico no
   mesmo artefacto continua em C2. A passagem física parcial encontrou e fechou
   localmente exposição de `network_error` e CORS ausente para o preview 4174;
   CORS `5/5`, Ruff, Driver `55/55`, build e E2E `7/7` verdes. O Redmi desligou
   antes da repetição pós-correção, portanto o gate físico não foi promovido.
   A segunda passagem, em 2026-08-25, confirmou o CORS e quatro `401` reais:
   a instalação tinha token expirado e nenhum refresh token. A PWA passou a
   oferecer recovery explícito com confirmação antes do purge fail-closed;
   Driver `56/56`, typecheck, build e E2E `7/7` verdes. O Redmi confirmou a
   primeira ação no bundle intermédio. Com autorização, purge físico deixou
   identidade ausente e stores/Workbox a zero. O slice seguinte fixou barra ao
   viewport, safe areas/largura 390–412 e pairing numérico de seis dígitos;
   Driver `60/60`, build e E2E `7/7`. O bundle novo foi carregado e inspecionado
   na PWA autónoma. A origem instalada `4173` reteve cliente/precache antigo;
   após saída real, 18 stores e Workbox ficaram a zero, mas a atualização exigiu
   ativação/limpeza/navegação manual. RED/GREEN preserva o evento pré-mount e
   mostra `Atualizar aplicação` sem sessão. Prova física de dois bundles, pairing
   e jornada online/degradada continuam pendentes; sem promoção de C2.
   O slice seguinte unificou a origem instalável/preview/E2E em
   `http://localhost:4173`, retirou `4174` do CORS, reservou `5174` para dev,
   fixou `strictPort`/loader Vite nativo em preview/build e removeu config/manifesto duplicados.
   O lifecycle atualiza antes do render apenas quando a PWA já tem controlador;
   primeira instalação não bloqueia o bootstrap. A prova Redmi corrigiu bind
   IPv6-only para `0.0.0.0` técnico, preservando `localhost:4173` como origem,
   e manteve somente reverses 4173/8000. O WebAPK autónomo migrou de
   `index-tVgRH7eW.js` para `index-GP13naLz.js`; uma segunda ativação a partir
   do lifecycle novo removeu o JS antigo de `static-assets`. Ficou um alvo
   standalone, worker ativo/controlador e sem waiting/installing. Driver
   `67/67`, build `1806/94/6`, E2E `7/7` e CORS `5/5` verdes localmente.
   Pairing e jornada online/degradada no mesmo SHA continuam pendentes; C2 não
   foi promovido. A passagem física seguinte consumiu pairing real com
   `HTTP 200`, carregou o histórico entregue `Maputo -> Beira` e confirmou o
   detalhe fechado com Load Permit, manifesto e guia, sem ações mutáveis.
   Emulação offline limitada ao WebAPK preservou detalhe/documentos e mostrou
   o aviso operacional; a rede foi restaurada. A continuação removeu os dois
   reverses, confirmou 4173/8000 inacessíveis e reabriu o WebAPK por Service
   Worker. Sessão, lista e detalhe vieram do cache/Dexie com indicação stale e
   somente leitura; após restaurar os túneis, viagens/documentos responderam
   `200` e os avisos desapareceram. Após expiração natural do access, abrir
   Viagens produziu `401 -> refresh 200 -> retry 200`; access/refresh rodaram e
   sessão/viagem permaneceram válidas. O percurso físico funcional está verde
   no working tree baseado em `b00962e`; falta repeti-lo no artefacto fixo.
4. **C3:** portar #35/#40, fechar Pyright/OpenAPI e recuperar CI executável.
   C2 foi congelado em `ae1ede2`/`a978229` e repetido no Redmi com cold start,
   cache, reconciliação e refresh. Os gates locais ficaram verdes, conforme
   `docs/evidence/C2_DRIVER_ANDROID_FIXED_SHA_20260826.md`; isto autoriza iniciar
   C3, não merge, staging ou release.
   A causa remota verificada do `startup_failure` inclui a política
   `sha_pinning_required=true` combinada com quatro Actions referidas por tags;
   `9cb2abe` corrigiu localmente 12 usos, Node e gates Driver, mas a execução
   remota ainda não ocorreu. A baseline Node `20.20.2` revelou 6 high em
   produção, 9 high totais e uma árvore extraneous, invalidando o deferimento
   antigo de #37. `4f7251c` endureceu o agregador contra schema, totais ou exit
   codes contraditórios; `0271ae0` executou o slice: auditorias zero, gate PR18
   verde, SBOM de 759 componentes, suites e builds Manager/Driver verdes. Os
   PRs #6/#7/#8/#37 ficam absorvidos localmente pela linha canónica, sem merge
   cego. Ainda faltam CI remota e revisão supply-chain independente. Ver
   `docs/evidence/C3_DEPENDENCY_REMEDIATION_20260827.md`.
5. **C4:** criar um RC único, executar staging, Android físico, Sentry, segurança,
   observabilidade e piloto no mesmo SHA/artefactos.

O fecho remoto dos PRs substituídos só ocorre após a evidência indicada. C0 não
autoriza encerrar PRs antes da paridade, nem apagar branches/worktrees.

## 5. Responsabilidade e evidência

| Trabalho | Owner | Dependência | Evidência mínima |
|---|---|---|---|
| decisão e freeze C0 | TL + PO | nenhuma | matriz versionada, PR #44 sem merge |
| Driver/Sync C1 | BE + SEC + QA | C0 | testes negativos com JWT Driver real e base de dados |
| jornadas Driver C2 | FE-D + BE + PO | C1 | ADR-012; contratos append-only; unit/integration/E2E + Android físico no mesmo SHA |
| contratos/CI C3 | TL + BE + FE + QA | C2 | Pyright, OpenAPI, builds, Actions por SHA e CI com passos executados |
| certificação C4 | SRE + SEC + QA + PO | C3 | mesmo SHA/RepoDigest em staging, observabilidade, dispositivo e piloto |

Se uma prova de paridade falhar, a linha é reclassificada de **SUBSTITUIR** para
**PORTAR** apenas no item faltante, nunca para merge integral.
