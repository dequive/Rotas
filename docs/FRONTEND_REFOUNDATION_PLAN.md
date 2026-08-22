# Plano de Refundação do Frontend ROTAS

Status: em execução  
Design authority: `DESIGN.md` v1.3.1  
Escopo: Manager Next.js + Driver PWA

## 1. Diagnóstico inicial

O frontend não parte do zero. Existem rotas e contratos reais, mas também
fragmentação suficiente para impedir uma migração segura por simples
substituição de CSS:

- Manager com duas famílias de componentes UI concorrentes.
- Centenas de botões HTML e estilos de paleta instanciados nas features.
- `globals.css` monolítico com estilos de domínio e aliases antigos.
- Oficina historicamente fragmentada entre contratos reais e dados/fallbacks
  demonstrativos; a vertical F3 já removeu esses fallbacks das jornadas migradas.
- Driver PWA separado, com CSS próprio e requisitos offline/touch distintos.
- Worktree com implementação funcional em curso; a refundação deve preservar
  esses contratos e avançar por ondas verificáveis.

## 2. Arquitetura-alvo

```text
Design tokens versionados
        ↓
Primitivos acessíveis
        ↓
Padrões compostos (page shell, table, form, timeline, kanban)
        ↓
Features por domínio
        ↓
Manager Next.js / Driver PWA
```

O BFF e as APIs existentes continuam fontes de verdade. O design system não
introduz mocks nem escreve diretamente no núcleo transacional.

## 3. Ondas

### Onda F0 — Contrato e baseline

- Manter `DESIGN.md` v1.3.1 como autoridade canónica.
- Medir componentes duplicados, estilos hardcoded e páginas com fallback.
- Separar evidência estrutural, teste local e runtime real.

Gate: inventário registado e nenhuma alteração funcional inadvertida.

### Onda F1 — Fundação

- Tokens light/dark completos.
- Inter + JetBrains Mono.
- Button, StatusBadge, KpiCard, DataTable, FormField, Dialog e feedback.
- Focus ring, reduced motion e touch targets.
- Aliases temporários para código ainda não migrado.

Gate: typecheck, testes de componentes e build.

### Onda F2 — Shell e navegação

- Shell responsivo, sidebar agrupada e topbar contextual.
- Navegação mobile por sheet.
- Tenant/modules sem exposição cruzada.
- Estados globais de sessão, limites e documentos.

Gate: teclado, 360/768/1280/1440px, rotas por módulo e logout.

### Onda F3 — Oficina ponta a ponta

- Recepção progressiva.
- Orçamentos master-detail e suplemento.
- Ordens de serviço/kanban.
- Peças, ferramentas, mão-de-obra e QC.
- Faturação, entrega, garantia e timeline de evidências.

Gate: jornada API real, RBAC, 404 cross-tenant, documentos imutáveis e estados
canónicos.

### Onda F4 — TMS e ERP

- Torre de Controlo, viagens, despacho, frota, terceiros e tarefas.
- Clientes, contratos, cobrança, contas a receber, contabilidade e RH.
- Substituir paletas e controlos diretos por padrões canónicos.

Gate: regressões por domínio, estados vazios/erro/parcial e acessibilidade.

### Onda F5 — Driver PWA

- Tokens compartilhados com densidade mobile.
- Fluxos offline, sincronização e conflitos.
- Captura de prova, manifesto, paragens e entrega.
- Alvos de toque, uso com uma mão e conectividade degradada.

Gate: jornada offline→online, idempotência, conflitos e instalação PWA.

### Onda F6 — Certificação

- Visual regression.
- Axe/keyboard.
- Performance e bundle budgets.
- E2E com backend real e base de dados tenant-scoped.
- Pilotagem e evidência de runtime.

Gate: GO/NO-GO independente; build verde não equivale a certificação.

## 4. Regras de execução

- Não reverter mudanças locais não relacionadas.
- Migrar por vertical funcional, não por substituição global cega.
- Nenhum ecrã novo usa dados fictícios como fallback silencioso.
- Erros da API são explícitos e acionáveis.
- Cada onda inclui implementação, testes, evidência e critério de rollback.
- Aliases legados só podem diminuir; código novo não os consome.

## 5. Primeira vertical de referência

`/oficina/ordens-servico` e `/oficina/ordens-servico/[id]` são a vertical
inicial porque já usam contratos reais de OS, tarefas, mão-de-obra, peças,
rentabilidade e faturação. Depois de aprovada, o mesmo padrão migra Recepção e
Orçamentos antes dos restantes módulos.

## 6. Evidência de execução — 2026-07-26

Estado: **Onda F3 implementada localmente; certificação de runtime pendente**.

Implementado:

- `DESIGN.md` v1.3.1 promovido a autoridade canónica, com contrato de foco
  determinístico, `--r-xl`, sem declaração prematura de conformidade WCAG.
- Estados de fonte de dados separados em `api`, `cache`, `degraded` e
  `unavailable`; o alias `fallback` foi removido da superfície migrada.
- Mutações críticas de receção, orçamento, OS e evidências enviam
  `Idempotency-Key` através do BFF.
- Gate estático impede hex em componentes migrados, hex fora dos blocos de
  tokens, foco legado, fonte `fallback`, semântica KPI `amber` e regressão das
  chaves de idempotência na vertical.
- Dashboard da Oficina derivado de receções, OS, viaturas e garantias reais.
- Check-in sem identidades demonstrativas, com clientes/viaturas reais,
  validação de odómetro, assinatura com hash devolvido pelo servidor e anexação
  das fotografias à receção criada.
- Detalhe de receção fail-closed, sem ficha fictícia em falha de API.
- Orçamentos master-detail com pesquisa/filtro, aceitação rastreável, recusa com
  motivo, bloqueio do documento decidido e suplemento separado ligado à OS.
- Execução com conclusão de tarefas, mão-de-obra, peças e bloqueadores reais
  antes de QC.
- Fecho de QC com custo reconciliado, pipeline de faturação assíncrono, emissão
  fiscal explícita e imutável.
- Entrega bloqueada até fatura emitida; confirmação exige odómetro, condição,
  pessoa e assinatura.
- Faturação e garantias sem dados demonstrativos silenciosos.

Validação local:

- `npm run typecheck`: verde.
- `npm test`: 17 ficheiros, 86 testes verdes.
- `npm run test:design-system`: 3 testes verdes.
- `npm run verify:design-system`: verde.
- `npm run verify:no-demo`: verde.
- `npm run verify:bff`: 98 módulos cliente, 36 handlers, zero violações.
- `npm run build`: verde, 72 rotas Next.js geradas.

Não certificado:

- Jornada E2E contra backend e PostgreSQL reais, incluindo RBAC e 404
  cross-tenant.
- O cliente e o BFF transportam `Idempotency-Key`, mas o OpenAPI atual não
  declara esse contrato nas mutações de receção e orçamento; enforcement,
  replay e auditoria server-side continuam gate de backend/runtime.
- A API de receção ainda expõe estados grossos
  (`received/in_service/ready/delivered`) e não os atualiza atomicamente com as
  transições da OS. O frontend não simula essa sincronização.
- A listagem fiscal genérica ainda não oferece filtro/identidade
  `document_source=workshop`; por isso a vista da Oficina deriva o pipeline das
  OS, sem declarar custo real como faturação emitida.
- Paginação completa, axe/keyboard automatizado, regressão visual e runtime
  mobile real permanecem gates da F6.

## 7. Evidência de execução F4 — 2026-07-27

Estado: **fundação visual F4 aplicada ao Manager; migração funcional por
domínio e certificação de runtime pendentes**.

Implementado:

- Gate v1.3.1 ampliado de Oficina para todo `apps/manager/app`, excluindo
  apenas testes e cliente OpenAPI gerado.
- Focus legado `amber` removido dos formulários Manager e substituído por
  `focus`/`focus-soft`.
- Scorecard de motoristas e documentos operacionais migrados dos badges
  paralelos para `StatusBadge`.
- KPI de manutenção migrou do alias `amber` para `accent`.
- Analytics e páginas de motoristas deixaram de declarar fallbacks de cor
  hexadecimal.
- Recibo salarial passou a usar tokens próprios de documento imprimível,
  preservando contraste e independência de dark mode.
- Inputs antigos encontrados em TMS, ERP, segurança, configurações, tarefas,
  terceiros e Oficina passaram a consumir tokens semânticos de superfície,
  borda, texto e foco.

Validação local:

- `npm run typecheck`: verde.
- `npm test`: 17 ficheiros, 86 testes verdes.
- `npm run test:design-system`: 3 testes verdes.
- `npm run verify:design-system`: verde sobre toda a aplicação Manager.
- `npm run verify:no-demo`: verde.
- `npm run verify:bff`: 98 módulos cliente, 36 handlers, zero violações.
- `npm run build`: verde, 72 rotas Next.js geradas.

Não certificado:

- A migração visual não certifica cálculos, regras legais ou processamento
  salarial; os gates H0–H5/ERP E3 permanecem vinculativos.
- Axe/keyboard, regressão visual, jornadas responsivas e execução contra
  backend/PostgreSQL reais continuam gates F6.
- Aliases CSS permanecem apenas para superfícies legadas ainda não
  recanonicalizadas e devem continuar a diminuir.

## 8. Evidência de execução F6 — 2026-07-28

Estado: **baseline automatizada e jornadas locais verdes; certificação WCAG
independente pendente**.

Implementado:

- axe Playwright A/AA nas cinco superfícies críticas;
- gate estático de idioma, landmarks, imagens, ordem de foco, regiões
  scrollable, tabs, pareamento e reduced motion;
- skip link e `main` único no layout autenticado;
- tabs de OS e viatura operáveis por Left/Right/Home/End;
- Hub 360 em Radix Sheet com gestão de foco;
- seed E2E sintético/idempotente sem skips;
- correcções runtime de contraste, target size, billing paginado e scorecard
  insuficiente.

Validação local:

- Manager: 19 ficheiros/89 testes, typecheck e build de 72 rotas verdes;
- Playwright Manager: 17/17, incluindo axe e jornadas funcionais;
- Driver: 26/26, typecheck e build PWA verdes;
- source accessibility: 167 TSX, zero violações do gate.

Não certificado:

- testes automatizados não provam conformidade WCAG 2.2 AA completa;
- faltam auditoria manual/assistiva, mobile real, zoom/reflow, forced colors,
  cobertura de todas as rotas/papéis/estados e dois tenants;
- falta repetição no CI remoto e no SHA/digests do release candidate.

## 9. Auditoria de convergência frontend-backend — 2026-08-20

Estado: **NO-GO funcional; Issue #42 aberto; feature freeze mantido**.

A auditoria deixou de usar build, testes unitários e presença de páginas como
prova suficiente. O Manager foi exercido contra o backend e PostgreSQL locais,
com sessão real, em 43 rotas estáticas nos viewports 1440x900 e 360x800. A
estrutura base respondeu em 86/86 navegações sem overflow horizontal global,
mas o casamento funcional não está fechado.

Falhas confirmadas:

- a ficha da viatura chama `GET /api/v1/checklists/checklists`, recebe `405` e
  converte a falha em “Nenhuma checklist registada”;
- `POST /api/v1/accounting/manual-entry`, `GET /api/v1/fuel/purchases`,
  `GET /api/v1/payables/orders` e `GET/POST /api/v1/governance/cases`
  devolvem `404` no backend real;
- criação, notas e transições de tarefas não fecham o fluxo com validação
  uniforme de `Response.ok`, permitindo falso sucesso e redirecionamento;
- a Oficina apresenta ao utilizador mensagens técnicas em inglês e
  `[object Object]` quando faltam entitlements/dados;
- existem páginas sem o landmark `main`, estados de erro/forbidden/parcial não
  são uniformes e continuam paletas/controlos paralelos fora dos primitivos;
- os gates atuais de design, acessibilidade, no-demo e BFF passam, mas não
  validam path + método + schema OpenAPI, semântica de erro nem todos os estados
  e tokens visuais;
- a PWA Driver mantém testes unitários verdes já registados, mas não arrancou
  nem compilou na máquina atual: o repositório exige Node 20 e o runtime é Node
  24; a falha `Access is denied`/resolução esbuild repetiu-se numa cópia local
  limpa. Falta reprodução no Node 20 suportado e no release candidate.

Evidência detalhada:

- `docs/evidence/FRONTEND_BACKEND_E2E_AUDIT_20260820.md`;
- GitHub Issue #42.

### 9.1 Onda F7 — Convergência executável

A F7 precede qualquer nova expansão funcional e reabre F4/F5/F6 onde a
evidência contradiz o estado anterior.

| Ordem | Entrega | Owner | Depende de | Evidência de saída |
| --- | --- | --- | --- | --- |
| F7.0 | Fixar Node 20, checkout/RC limpo e CI com jobs reais | TL + QA + SRE | Issue #34 | Manager/Driver typecheck, testes e builds no mesmo SHA; zero `startup_failure`, `jobs=[]` ou job sem steps |
| F7.1 | Criar ledger executável de fluxos e contratos | TL + FE + BE + QA + SEC | F7.0 | cada chamada liga UI, BFF, serviço, persistência/outbox, resposta UI, método, schemas, RBAC, tenant, idempotência e erros |
| F7.2 | Fechar contratos estruturais | TL + BE + FE-M + SEC | F7.1 | response models não vazios; BFF Governance dedicado; decisões de domínio para Fuel/AP/Accounting aprovadas |
| F7.3 | Corrigir os fluxos quebrados sem falso sucesso/vazio | FE-M + FE-D + BE + QA | F7.2 | zero endpoint órfão, zero mutação sem `ok`, erros visíveis e acionáveis |
| F7.4 | Provar idempotência, RBAC e isolamento | BE + SEC + QA | F7.3 | replay igual, conflito de payload, matriz de papéis e tentativas tenant A→B em cada mutação crítica |
| F7.5 | Uniformizar shell, tokens, landmarks e estados | FE-M + FE-D + PO | F7.3 | loading/empty/error/forbidden/partial/degraded em todas as rotas de release |
| F7.6 | Certificar os fluxos F-01 a F-14 | QA + FE + BE + PO | F7.4 + F7.5 | UI→BFF→serviço→DB/outbox→UI, desktop/mobile e offline onde aplicável |
| F7.7 | Revalidar independentemente e promover | TL + SEC + SRE + PO | F7.6 | CI remota, staging, dois tenants, piloto e ledger no mesmo RC |

### 9.2 Gates bloqueantes adicionais

- Toda referência HTTP do frontend deve resolver para contrato versionado com
  método, request e resposta compatíveis; schemas `{}` não contam como contrato
  e “endpoint parecido” não passa.
- Cada contrato deve declarar `401`, `403`, `404`, `409`, `422` e `500`, com
  teste UI correspondente; nenhum deles pode virar silenciosamente vazio,
  `null`, “não encontrado” ou sucesso.
- Toda mutação crítica prova `Idempotency-Key`: mesma chave/payload devolve o
  mesmo resultado sem duplicar; mesma chave/payload diferente falha; decisão,
  persistência e auditoria são verificadas.
- Cada fluxo prova papéis permitidos/proibidos e tentativa cross-tenant real com
  a role restrita da aplicação; dois tenants apenas presentes não bastam.
- Funcionalidade sem backend aprovado fica removida da navegação ou marcada
  explicitamente como indisponível; não pode ser vendida como concluída.
- O crawl deve cobrir rotas dinâmicas, papéis, entitlements e dados suficientes,
  não apenas páginas estáticas com zero registos.
- Governance exige contrato versionado e BFF próprio com tradução de identidade
  e tenant, credencial server-side, timeout, idempotência, indisponibilidade,
  outbox/DLQ e reconciliação; não é uma exceção ao ledger.
- Fuel exige decisão explícita sobre listagem GET versus comando POST e mapeia
  `purchase_reference`, litros, preço e data; AP mapeia `po_number`,
  `issued_at` e `estimated_amount`; Accounting fecha journal e razão sem
  lançamentos duplicados.
- Driver só fecha F5 quando pairing, bootstrap, operação offline, reconciliação
  e troca de identidade forem reproduzidos no Node 20 e no RC.

### 9.3 Fluxos obrigatórios de produto

| ID | Fluxo fechado como uma cadeia única | Estado auditado |
| --- | --- | --- |
| F-01 | onboarding → verificação → login/MFA → sessão → logout/recovery | parcial |
| F-02 | cliente → contrato/tarifa → ordem → atribuição → autorização → viagem | funcional local até viagem iniciada; Chromium 3/3 cobre pedido, aprovação explícita, despacho, km inicial e refresh preventivo; negativos backend tenant/RBAC/replay verdes; staging, fluxo documental obrigatório e piloto pendentes |
| F-03 | pairing Driver → bootstrap → manifesto/paragens → POD → offline/sync | parcial, runtime atual bloqueado |
| F-04 | POD validado → billable → fatura → emissão → pagamento → AR/razão | parcial |
| F-05 | viatura/motorista → documentos → elegibilidade → checklist → histórico | quebrado no checklist |
| F-06 | pedido oficina → receção → diagnóstico → orçamento → aprovação → OS | parcial |
| F-07 | OS → mão-de-obra/peças → QC → fatura → pagamento → entrega/garantia | parcial |
| F-08 | compra combustível → aprovação → receção/tanque → abastecimento → custo | quebrado na compra Manager |
| F-09 | terceiro → PO → receção/match → fatura fornecedor → pagamento → diário | quebrado em PO e não provado integralmente |
| F-10 | lançamento contabilístico → razão/balancete/P&L → reconciliação | quebrado no lançamento manual |
| F-11 | tarefa Workshop/Governance → nota → transição → outbox/DLQ/reconciliação | parcial/funcional local; notas, outbox/DLQ e multi-tenant por fechar |
| F-12 | artigo/armazém → entrada/saída/transferência/contagem → saldo reconciliado | parcial/não provado pela UI |
| F-13 | colaborador → assiduidade/variáveis → payroll → pagamento/diário | parcial; legal e contabilístico não certificado |
| F-14 | factos operacionais → Torre/alerta/analytics/export → drill-down origem | parcial |

Um fluxo só muda para `funcional` quando cada elo tem efeito persistido
verificado, resposta UI correta, negativos, RBAC, isolamento e replay. Um
backend forte ou uma página renderizada isoladamente mantém o fluxo `parcial`.

Decisão: F4, F5 e F6 permanecem **parciais**; nenhum deles autoriza afirmar que
o frontend está terminado ou perfeitamente integrado.

### 9.4 Progresso executado — 2026-08-20

| Entrega | Estado atual | Evidência | Próximo gate |
| --- | --- | --- | --- |
| F7.0 | parcial | Node/npm fixados; Manager 95/95; backend 708/708 executados + 1 skip | repetir Manager/Driver no Node 20.20.2 e CI remota com jobs reais |
| F7.1 | parcial | auditor com 208 referências/162 operações e 160 violações; 9/9 testes | schemas request/response e cobertura de referências dinâmicas |
| F7.2 | contratos fechados, BFF pendente | Fuel/AP/Accounting reconciliados; compatibilidade PGC seed/runtime corrigida; `verify:api-contracts` a 0 violações em 208 referências/158 operações | contrato Governance dedicado |
| F7.3 | parcial | F-05, F-08 e F-10 corrigidos; F-09 backend-real verde; respostas 2xx tipadas em todos os fluxos F-01 a F-14 | repetir F-05/F-09 pela UI e eliminar sete operações órfãs |
| F7.4 | parcial | matriz replay/conflito/escopo por tenant em 15 mutacoes, 46 testes (`test_idempotency_matrix.py` + `test_idempotency_matrix_financial.py`), com controlo negativo sem chave; conflito de payload passa de 2 para 17 das 54 operacoes idempotentes | estender as 37 operacoes restantes e fechar a matriz de papeis RBAC |
| F7.5 | pendente | erros de checklist agora fail-closed; ação inerte removida | estados e console limpo em todas as rotas |
| F7.6 | pendente | duas mutações certificadas localmente pelo Chrome | F-01 a F-14, desktop/mobile/offline |
| F7.7 | pendente | nenhuma evidência remota/staging/piloto nova | revisão independente e promoção do mesmo RC |
| F7.8 | funcional local, não certificado | E2E cliente→contrato→ordem→atribuição→autorização→despacho→início e refresh preventivo 3/3; negativos tenant/RBAC/replay; Gestão de Acessos 2/2; Manager 124/124; backend 723 verdes + 1 skip numa base vazia migrada a rec13 | Load Permit real pela UI; fechar contratos OpenAPI; múltiplas instâncias, Node 20/CI/staging/piloto no mesmo RC |

Prioridade imediata:

1. aprovar a topologia de confiança Manager→Governance e implementar BFF
   server-side sem expor credenciais;
2. tipar respostas OpenAPI usadas pelo frontend e fazer
   `verify:api-contracts` ficar verde sem allowlist de dívida;
3. fechar a jornada UI de AP e os detalhes/notas de tarefas Workshop;
4. repetir tudo no Node 20, em dois tenants e no CI remoto.

### 9.5 Progresso F-11 — 2026-08-20

| Entrega | Estado atual | Evidência | Próximo gate |
| --- | --- | --- | --- |
| BFF Governance | funcional local | sessão ROTAS revalidada; chave por tenant server-only; catálogo em `cases:read`; chave Manager separada do adaptador; 9/9 testes | dois tenants, rotação/revogação e staging implantado |
| Criar/listar/detalhar/transicionar caso | funcional local | Chromium real com 201 e histórico persistido | transições `available`, anexos e negativos RBAC/replay |
| Pedido Workshop criar/listar/detalhar | funcional local parcial | Chromium criar/listar; teste HTTP do detalhe | browser detalhe/notas/status e associação OS |
| Notas Governance | indisponível explícito | UI já não chama endpoint inexistente | especificar contrato append-only ou manter fora do produto |
| Execução/custos na Central | removido da jornada | ações falsas substituídas por encaminhamento Oficina | reabrir só após contrato caso↔OS |
| Contratos frontend/OpenAPI | verde | `verify:api-contracts` 208 referências / 158 operações / **0 violações**; zero operações ausentes e zero schemas 2xx vazios; `test_openapi_contract` 9/9; backend 728 verdes + 1 skip; Manager `tsc` limpo e 124/124 | manter o auditor a 0 como gate de CI remota |

Nova prioridade imediata:

1. automatizar o provisionamento multi-tenant cifrado, rotacionável,
   revogável e auditado das credenciais Governance separadas por consumidor;
2. fechar `available transitions`, campos/anexos, replay/conflito, scopes e
   tenant A→B;
3. ~~eliminar as 72 referências a schemas 2xx vazios, continuando pelos fluxos
   F-01 a F-14~~ — fechado a 2026-08-22: auditor a 0 violações, com os PDF/XLSX
   e downloads declarados por `app/core/openapi_responses.py`;
4. provar refresh concorrente em múltiplas instâncias atrás do balanceador e
   testar expiração/replay/revogação no mesmo RC;
5. completar F-02 documental com criação/anexo de Load Permit, bloqueio e
   reavaliação pela UI, mantendo negativos RBAC/cross-tenant/replay;
6. repetir F-02, F-09 e F-11 em staging, Node 20 e CI remota no mesmo RC;
7. manter F-11 parcial até outbox/DLQ/reconciliação e piloto terem evidência.
