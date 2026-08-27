# ROTAS — Instruções Canónicas para Agentes

- Estado: vinculativo
- Atualizado em: 2026-08-24
- Decisão de release: `NO-GO`

Este ficheiro é o ponto de entrada obrigatório para qualquer agente humano ou
automatizado que trabalhe no ROTAS. Nenhum agente pode criar regras locais que
contradigam esta hierarquia, reclassificar gates por iniciativa própria ou usar
um relatório histórico como estado atual.

## 1. Ordem obrigatória de leitura

Antes de planear ou alterar código, ler nesta ordem:

1. `AGENTS.md` — instruções e precedência documental;
2. `docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md` — baseline auditada e
   bloqueios atuais;
3. `docs/BRANCH_PR_CONVERGENCE_MATRIX_20260822.md` — destino vinculativo de
   cada linha Git/PR durante C0-C4;
4. `docs/ROTAS_MASTER_DELIVERY_PLAN.md` — escopo, dependências e sequência;
5. `docs/ENGINEERING_STANDARDS.md` — padrões de arquitetura, segurança e
   qualidade;
6. `docs/MODULE_CLOSURE_MATRIX.md` — maturidade funcional por domínio;
7. `docs/PRODUCTION_RELEASE_LEDGER.md` — única decisão GO/NO-GO;
8. ADRs aplicáveis em `docs/adr/`.

`docs/evidence/`, commits, corpos de PR, `IMPLEMENTATION_STATUS.md` e logs são
evidência ou histórico. Não substituem os documentos canónicos acima.

Se houver conflito, prevalece a regra mais segura e o gate mais restritivo. O
agente deve parar, registar a divergência e atualizar os documentos canónicos na
mesma mudança; não pode escolher silenciosamente a versão conveniente.

## 2. Objetivo e fronteira do produto

O ROTAS será um ERP/TMS SaaS enterprise multi-tenant:

`Operador ROTAS SaaS -> tenant independente -> entidades legais/filiais ->
clientes, fornecedores, colaboradores e operações próprias do tenant`.

O produto só é vendável quando os fluxos transacionais, segurança, operação,
BI e piloto forem comprovados no mesmo release candidate. Presença de páginas,
models, endpoints ou testes isolados não significa módulo fechado.

Aplicar a taxonomia da `ADR-011`: módulos de negócio do tenant, capacidades de
governação e fundações técnicas são níveis distintos. `tms` e `oficina` são
bundles legados, não prova de catálogo/entitlements enterprise; identidade,
auditoria, ficheiros e sync/offline são fundações obrigatórias, não módulos
vendáveis. Cobrança pertence a Clientes/Vendas/Cobrança; Custos e Margem apenas
consome receita certificada para reconciliar margem.

## 3. Estado vinculativo atual

- A branch auditada `codex/issue42-convergencia-manager-driver-backend`, no SHA
  `c912cb1c9e098b8cd4899c138232af7a02432c54`, é uma tentativa de convergência,
  não um release candidate.
- O PR #44 não está autorizado para merge enquanto os P0/P1 da baseline de
  convergência estiverem abertos.
- CI remota, staging, piloto e produção permanecem `NO-GO`.
- Issue #42 continua aberta e tem precedência sobre Issue #43 e expansão
  funcional nova.
- Billing permanece funcionalmente congelado: só pode ser alterado por uma
  Issue explicitamente aprovada ou por correção necessária para um gate
  bloqueante, com regressão e reconciliação demonstradas.

## 4. Sequência que nenhum agente pode saltar

1. Convergir Driver/Sync e fechar autorização, ownership, pairing,
   idempotência e contratos OpenAPI.
2. Consolidar branches/PRs numa linha canónica e recuperar todos os gates
   locais, incluindo Pyright e supply chain.
3. Fechar Cliente <-> Terceiro por `widen-migrate-narrow`.
4. Executar E0 SaaS Boundary.
5. Executar E1 Procure-to-Pay e inventário.
6. Executar E2 Order-to-Cash, Oficina e fecho financeiro.
7. Executar E3 Pessoas, payroll e ativos.
8. Executar E4 Trusted BI.
9. Executar E5 piloto e certificação comercial.

Uma etapa posterior não pode ser promovida para `fechada` enquanto a anterior
tiver gate bloqueante vermelho.

## 5. Contrato obrigatório do Driver

- Gestor cria, planeia, autoriza, atribui e encerra viagens.
- Motorista vê e executa apenas viagens que lhe foram atribuídas.
- Motorista não cria/atribui viagens e não emite Load Permit, manifesto, guia
  ou outro documento administrativo/de carga.
- O Load Permit/Autorização de carregamento é emitido pelo cliente final/dono
  da carga; o motorista apenas consulta ou solicita o documento em falta.
- Motorista pode solicitar documento em falta e consultar documentos emitidos.
- Viagem fechada é somente leitura e não aceita novos documentos/pedidos.
- Histórico exclui rascunhos e inclui viagens atribuídas concluídas/canceladas.
- Checklist, combustível, despesas e despacho de viagem formam um diário
  operacional imutável. Depois da submissão, correções são novos eventos
  referenciados; nunca `PATCH` destrutivo sobre o facto original.
- “Despacho de viagem” é o allowance emitido por gestor/sistema/tesouraria; o
  motorista apenas consulta e acusa receção. “Autorização de saída” é um gate
  operacional distinto.
- Depois de `delivered`, `closed` ou `cancelled`, o diário não aceita novos
  checklists, abastecimentos, despesas ou despachos; a prova de descarga segue
  o lifecycle próprio.
- Toda mutação offline valida `(tenant_id, driver_id, device_id)`, ownership da
  entidade, operação permitida e estado do lifecycle.
- Idempotência e cache não podem ser partilhadas entre motoristas/dispositivos.
- API Driver/Sync usa schemas públicos próprios; nunca o serializer integral de
  gestor nem campos internos de custo, receita ou margem.
- Aplicar a `ADR-012` em qualquer alteração de checklist, combustível, despesas,
  despacho de viagem, navegação ou histórico da PWA Driver.

## 6. Definition of Closed

Um fluxo só pode ser chamado `fechado` quando possui, conjuntamente:

- fonte de verdade e máquina de estados explícitas;
- autorização RBAC e ownership intra-tenant;
- RLS provada com role restrita, não superuser/BYPASSRLS;
- idempotência, concorrência, replay e conflito;
- auditoria e exceções operacionais visíveis;
- migrations e backfill/rollback quando aplicável;
- contrato API tipado e consumidor alinhado;
- testes unitários, integração e E2E da jornada real;
- estados UX loading/empty/error/forbidden/degraded/success;
- observabilidade sem PII;
- evidência no mesmo SHA/artefacto.

`Implementado`, `verde local`, `CI verde`, `staging validado`, `piloto` e
`release-certified` são estados diferentes e não intercambiáveis.

## 7. Regras de execução e Git

- Seguir Issue -> branch curta -> PR dedicado -> CI/revisão -> deploy do SHA ->
  verificação pós-deploy -> fecho da Issue.
- Uma correção, melhoria ou função não pode misturar domínios sem dependência
  explícita.
- Não fazer merge cego entre as branches Issue #25 e Issue #42. Portar por
  verticais contratuais com testes RED antes da implementação.
- Preservar alterações não relacionadas e worktrees de outros agentes.
- Não declarar sucesso com jobs ausentes, `startup_failure`, testes skipped ou
  evidência de outro SHA.
- Não reduzir/remover gate para fazer a pipeline passar.
- Alterações de documentação devem atualizar, quando afetados, baseline atual,
  plano mestre, matriz e ledger; não criar um novo plano paralelo.

## 8. Próximo gate obrigatório

C1-I0 está implementado localmente pelos commits `0b7a36c` e `3acabde`, conforme
`docs/adr/ADR-010-base-de-dados-descartavel-para-testes.md`. Todo pytest backend
mutável deve ser executado exclusivamente por
`python -m scripts.run_isolated_pytest <argumentos pytest>`, que cria uma base
`rotas_test_*`, aplica Alembic `head` e elimina a base no fim. A coleção direta
falha sem `TEST_DATABASE_URL`; nenhum agente pode contornar o gate, reutilizar
`localhost:55432/rotas`, limpar essa base ou assumir que é descartável.

O runner atual é deliberadamente serial e rejeita `xdist -n`. Paralelismo só
pode ser ativado depois de existir uma base efémera independente por worker.

Os incrementos C1/C3 até `97e365d` já produziram testes e contratos com token
Driver real que provam:

- criar viagem, listar frota geral e emitir documentos retorna `403`;
- dispositivo divergente é rejeitado;
- viagem/viatura/documento de outro motorista do mesmo tenant é rejeitado;
- replay entre motoristas/dispositivos é rejeitado, incluindo corrida entre
  dois dispositivos com exatamente um efeito físico;
- duas requisições de pairing concorrentes aceitam exatamente um consumidor e
  a identidade física do dispositivo é única por tenant/motorista;
- endpoints Driver/Sync reais possuem DTOs públicos não vazios e sem campos de
  custo/receita/margem; operações sempre proibidas documentam apenas `403`.

A regressão backend integral no SHA `97e365d`, numa base descartável migrada de
`template0` até `rec14`, passou `968/968` sem skips. Ruff `app tests`, Pyright,
drift OpenAPI e gates Manager ficaram verdes localmente; isto não equivale a CI,
staging, Android físico ou release candidate.

Os slices C2 até `22ae117` removeram ações administrativas da PWA, publicaram
Minhas Viagens, histórico, detalhe, requisitos canónicos, documentos, download,
pedido em falta e terminal read-only, reconciliaram a checklist legada do
Manager e recuperam listas/documentos offline por tenant, motorista e sessão.
`1513913` fechou localmente pedido, download e erro recuperável em Playwright
mobile `6/6`. No HEAD de produto `e0078c6`, backend `980/980`, Ruff, Pyright,
OpenAPI, Manager `128/128`/build de 74 páginas e Driver `38/38`/build/E2E `6/6`
ficaram verdes. A execução Redmi de 2026-08-24 foi exploratória e sem SHA, logo
não fecha o gate Android.

A `ADR-012` acrescentou ao mesmo C2 o diário operacional imutável. O primeiro
incremento removeu update destrutivo de combustível no Driver/Sync. O segundo
aplicou o `widen` `rec15`: novos checklists e abastecimentos podem guardar a
viagem explícita, com FK composta tenant+trip, índice e ownership; históricos permanecem nullable e
não recebem backfill heurístico. No working tree, Driver/Sync/OpenAPI passou
`85/85`, a regressão descartável `987/987`, Ruff `app tests`, Pyright `0/0/0`,
OpenAPI `24d842...3188c`, cliente gerado e Manager typecheck ficaram verdes.
Isto é verde local sem promoção. O terceiro incremento publicou quatro leituras
paginadas e ownership-scoped: `/driver/records/checklists`, `/fuel`, `/expenses`
e `/advances`. Custos internos pagos pela empresa ficam fora do contrato;
despacho vem de `DriverAdvance`; notas internas e UUIDs de comprovativo sem
download dedicado não são expostos. Driver/OpenAPI passou `58/58`, a regressão
descartável `1003/1003`, Ruff e Pyright globais ficaram verdes, OpenAPI
`003054...90f0c`, cliente gerado e Manager typecheck ficaram alinhados.

O quarto incremento introduziu `rec16` para despesas: cada `TripCost` congela
motorista, visibilidade e tipo de ator; históricos são migrados de forma
determinística pela viagem e origem armazenadas. `UPDATE/DELETE` são rejeitados
por trigger e correções criam ajuste assinado ou estorno referenciado, com lock,
idempotência, auditoria e reconciliação. A API Manager e o DTO Driver ficaram
tipados. A partição integrada passou `81/81`, a regressão descartável
`1009/1009`, Ruff/Pyright e Manager `128/128`/build de 74 páginas ficaram verdes;
OpenAPI `be1f22...2049d`. Billing e a base online ficaram intocados.

O quinto incremento levou as quatro coleções ao cliente tipado e ao cache Dexie
por tenant, motorista e sessão. A PWA usa a navegação canónica
Hoje/Viagens/Registos/Mais, mantém o histórico dentro de Viagens, traduz códigos
internos e distingue loading, vazio, 403, indisponível e snapshot degradado
somente leitura. Dependências Google Fonts foram removidas do artefacto
offline-first. Driver passou `55/55`, typecheck e build de produção
`1805/93/6`; Playwright mobile passou `7/7`, incluindo diário online/offline.

O próximo gate obrigatório continua em C2: fixar um SHA/artefacto e repetir a
jornada completa no Android físico ligado, incluindo Registos e rede degradada.
Uma prova física parcial de 2026-08-24 confirmou o novo service worker, a
navegação e a tradução de `loaded_empty`, mas expôs dois defeitos: erro técnico
cru no painel Sync e CORS ausente para o preview `localhost:4174`. Ambos foram
fechados por teste: a PWA oculta o detalhe interno, usa linguagem operacional e
reconcilia o painel; o preflight 4174 passa na suíte CORS `5/5`. O telefone
desligou antes da repetição pós-CORS, portanto esta prova não fecha Android.
Uma segunda passagem em 2026-08-25 confirmou quatro respostas backend `401`,
sem códigos internos, e diagnosticou uma sessão legada expirada sem refresh
token. A PWA oferece agora `Voltar a emparelhar` e exige confirmação explícita
`Limpar e emparelhar` antes do purge fail-closed. Após autorização, o Redmi
removeu os três registos QA e a identidade legada; chaves ausentes e stores/
Workbox a zero foram comprovados. O slice F5 seguinte fixou nav ao viewport,
safe areas/largura integral e pairing numérico de seis dígitos, sem erros
técnicos visíveis. Driver `60/60`, typecheck, build `1806/93/6` e E2E `7/7`
ficaram verdes. Em 2026-08-25 o bundle novo foi carregado na PWA instalada e a
tela autónoma de ativação foi inspecionada no Redmi. A instalação `4173` reteve
um cliente/precache antigo separado do Chrome `4174`; o fluxo real de saída
removeu a identidade e a verificação contou 18 stores e Workbox a zero. O
worker novo só assumiu após `SKIP_WAITING`, remoção do precache antigo e
navegação real. RED/GREEN adicionou um coordenador que preserva o worker em
espera antes do mount e uma ação `Atualizar aplicação` na tela sem sessão. Falta
provar a transição entre dois bundles no Redmi. Novo pairing e jornada
online/degradada no mesmo SHA/artefacto permanecem
pendentes, logo C2 continua aberto. A convergência visual prossegue depois por Hoje, Viagens/
Documentos, Registos e Mais, sem alterar a fronteira da persona.
O slice seguinte tornou `http://localhost:4173` a única origem local instalável
e de E2E do Driver. `4174` foi retirada da allowlist e recebe `400`; `5174` fica
reservada a desenvolvimento e nunca deve ser instalada. Playwright, preview e
WebAPK usam literalmente `localhost:4173`; o preview faz bind técnico IPv4 em
`0.0.0.0` para o reverse ADB, mas esse endereço nunca é origem consumidora.
Configuração e manifesto duplicados foram
removidos, a porta é estrita e preview/build usam o loader nativo do Vite. O ciclo de
update verifica antes do render apenas quando já existe controlador; primeira
instalação renderiza imediatamente. Worker em espera recebe `SKIP_WAITING`,
recarrega só em `controlling` e volta a verificar no foreground/retorno da rede.
Driver `67/67`, typecheck, build `1806/94/6`, E2E `7/7` e CORS isolado `5/5`
estão verdes localmente. No Redmi, somente os reverses 4173 e 8000 ficaram
ativos; o WebAPK autónomo migrou de `index-tVgRH7eW.js` para
`index-GP13naLz.js`, ativou um segundo worker produzido pelo novo lifecycle e
removeu o JavaScript antigo do cache runtime. Ficou um único alvo autónomo
4173, worker ativo/controlador, sem waiting/installing nem findings de console.
Pairing real e jornada online/degradada no mesmo SHA/artefacto continuam
pendentes; C2 permanece aberto.
Na passagem seguinte de 2026-08-25, o Manager emitiu um código real para o
único motorista da base piloto e o WebAPK consumiu-o no Redmi com `HTTP 200`,
sem imprimir código, tokens ou identidade física. A PWA carregou Joao Manuel,
o histórico `Maputo -> Beira` entregue e o detalhe somente leitura com
documentação completa: Load Permit, manifesto e guia de transporte. Emulação
de rede limitada ao alvo confirmou `navigator.onLine=false`, o aviso
`Sem ligação — a gravar localmente` e retenção do detalhe/documentos; a rede
foi restaurada com `navigator.onLine=true`. Pairing e leitura degradada ficam
fisicamente provados apenas no working tree baseado em `b00962e`, não num RC.
Na continuação física, os reverses 4173/8000 foram removidos e confirmados
inacessíveis no próprio Redmi; após `force-stop` e nova abertura, o WebAPK
arrancou pelo Service Worker, preservou a sessão e recuperou do Dexie a lista e
o detalhe entregue, identificando explicitamente viagens/documentos guardados
e somente leitura. Depois de restaurar apenas os dois reverses, viagens e
documentos reconciliaram com `200`, os avisos stale desapareceram e a sessão
permaneceu válida. Após a expiração natural do access token, abrir Viagens
produziu `GET 401 -> POST /auth/refresh 200 -> GET 200`; access e refresh foram
ambos substituídos, sem expor valores, e sessão/viagem permaneceram visíveis.
O percurso físico funcional C2 está provado no working tree. Falta congelar e
repetir o conjunto no mesmo SHA/artefacto fixo; C2 ainda não é promovido.
O congelamento seguinte criou `ae1ede2` para backend e `a978229` para a PWA;
backend `1010/1010`, Ruff/Pyright, Driver `67/67`/build/E2E `7/7`, Manager
`128/128`/build e OpenAPI ficaram verdes. Backend e preview foram reiniciados a
partir desse produto; o Redmi repetiu cold start com API bloqueada e o backend
registou `GET 401 -> POST refresh 200 -> GET 200`, mantendo bundle
`index-GP13naLz.js`, sessão e viagem. C2 fica fechado local+físico para o
conteúdo de `a978229`; CI, staging e release continuam `NO-GO`. O próximo gate
obrigatório passa a C3: Actions por SHA, supply chain e CI efetivamente
executada. Ver `docs/evidence/C2_DRIVER_ANDROID_FIXED_SHA_20260826.md`.
O `narrow` de checklist/combustível continua proibido até política/backfill
próprios. Só depois seguem Actions, supply chain e CI. Estado: `NO-GO`.
