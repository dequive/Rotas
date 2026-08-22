# Auditoria frontend-backend ponta a ponta — 2026-08-20

Issue: #42  
Escopo: Manager Next.js, BFF, Driver PWA e contratos backend  
Decisão: **NO-GO**

## 1. Método e limites

- Inventário: 51 rotas Manager, 52 componentes de feature, 15 primitivos UI e
  seis vistas Driver, além do shell principal.
- Contrato: referências HTTP comparadas com
  `backend/openapi/rotas-v1.json`, cujo drift check passou no source atual.
- Runtime: backend/PostgreSQL/Redis locais e Manager em modo dev, com login E2E
  real e tenant autenticado.
- Browser: Playwright Chromium isolado, porque Chrome DevTools MCP não estava
  disponível nesta sessão.
- Cobertura de navegação: 43 rotas estáticas em 1440x900 e 360x800, totalizando
  86 verificações; rota dinâmica de viatura validada separadamente.
- Limite: não houve staging, dispositivo físico, CI remota verde nem RC. A PWA
  Driver não pôde ser exercida no browser devido à toolchain local incompatível.
- Proveniência: branch `codex/engineering-standard`, HEAD
  `5540da7a715fadea271ef6a2b978da1614e702c1`, working tree com 529 entradas
  (358 modificadas, 169 não rastreadas e duas eliminadas) e Node `v24.16.0`.
  Esta baseline diagnostica o checkout, mas não é evidência promovível de RC.

## 2. Resultado por camada

| Camada | Resultado | Evidência |
| --- | --- | --- |
| Estrutura Manager | parcial | 86/86 navegações renderizaram; sem overflow global |
| Uniformidade visual | parcial | shell coerente, mas paletas, badges, landmarks e estados paralelos persistem |
| Acessibilidade automática | parcial | gate estático passa; não cobre todas as regras/rotas/estados |
| BFF boundary | parcial | browser não chama backend diretamente, mas path/método/schema não são validados |
| OpenAPI | parcial | artefacto sem drift; consumidores ainda usam endpoints ausentes |
| Backend real | falha | cinco famílias de chamadas frontend confirmadas com 404/405 |
| Tratamento de erro | falha | erro de checklist convertido em vazio; tarefas podem produzir falso sucesso |
| Driver PWA | bloqueado | Node 20 requerido; Node 24 falha em workspace e cópia temporária limpa |
| Release | falha | sem CI remota executada, staging, piloto e evidência no mesmo RC |

## 3. Desencontros de contrato confirmados

| Consumidor | Chamada atual | Contrato/backend | Resultado |
| --- | --- | --- | --- |
| Viatura/overview | `GET /api/v1/checklists/checklists` | `GET /api/v1/checklists` | 405 e falso vazio |
| Contabilidade manual | `POST /api/v1/accounting/manual-entry` | apenas `journal-entries` no OpenAPI | 404 |
| Compras de combustível BFF | `/api/v1/fuel/purchases` | `/api/v1/fuel-operations/purchases` | 404 |
| Terceiro/AP | `/api/v1/payables/orders` | `/api/v1/payables/purchase-orders` | 404 |
| Tarefas | `/api/v1/governance/cases*` no backend ROTAS | serviço Governance requer contrato próprio | 404 |

O problema não é apenas nomenclatura. Cada correção precisa reconciliar método,
payload, resposta, autorização, tenancy, idempotência e semântica de erro.

As revisões adversariais confirmaram incompatibilidades mais profundas:

- Fuel: o Manager oferece GET+POST e envia `vehicle_id`, `liters`, `unit_cost`,
  fornecedor, posto e odómetro; o contrato canónico de compra requer
  `purchase_reference`, `ordered_liters`, `unit_price` e `ordered_at`, e não
  expõe a mesma listagem GET;
- AP: a UI cria/lê `order_number` e `estimated_cost`, enquanto o backend exige
  `po_number`, `issued_at` e `estimated_amount`;
- Accounting e purchase orders não provam idempotência efetiva server-side,
  apesar de o cliente poder enviar a chave;
- Checklists e Fuel têm respostas OpenAPI com schema vazio em operações
  relevantes; drift verde não prova o formato consumido;
- Governance mistura leitura server-side direta com mutações enviadas ao proxy
  ROTAS, portanto requer topologia e contrato próprios, não simples rename.

## 4. Matriz dos fluxos ponta a ponta

| ID | Fluxo | UI/BFF/API | Persistência/efeito esperado | Estado |
| --- | --- | --- | --- | --- |
| F-01 | onboarding→verify→login/MFA→sessão→logout/recovery | páginas públicas, `/api/auth/*`, `/api/onboarding/*` | tenant/user, tokens/cookies e sessões revogáveis | parcial |
| F-02 | cliente→contrato→ordem→atribuição→autorização→viagem | Clientes/Contratos/Viagens/Despacho; clients/contracts/trip-orders/trips | cliente, contrato, trip order, trip e audit | parcial |
| F-03 | pairing→bootstrap→manifesto/paragens→POD→offline/sync | Manager pairing + Driver APIs/sync | device/session, cache scoped, fila e prova | parcial; runtime bloqueado |
| F-04 | POD→billable→fatura→emissão→pagamento→AR/razão | Carga/Cobrança/AR; cargo/billing/payments/accounting | POD, documento imutável, pagamento e diário | parcial |
| F-05 | frota/pessoas→docs→elegibilidade→checklist→histórico | Viaturas/Motoristas/Manutenção | ativos, documentos, checklist e disponibilidade | quebrado no checklist |
| F-06 | pedido oficina→receção→diagnóstico→orçamento→aprovação→OS | Oficina/Receção/Orçamentos/OS | receção, snapshot, orçamento e OS | parcial |
| F-07 | OS→labor/peças→QC→fatura→pagamento→entrega/garantia | detalhe OS/Faturação/Garantias | consumos, custos, QC, documento e entrega | parcial |
| F-08 | compra fuel→aprovação→receção/tanque→abastecimento→custo | Fuel board/modal | compra, recibo, movimento de tanque e custo | quebrado na compra Manager |
| F-09 | terceiro→PO→receção/match→invoice→pagamento→diário | Terceiros/AP | PO, receção/match, AP, payment e journal | quebrado/parcial |
| F-10 | lançamento→razão/balancete/P&L→reconciliação | Contabilidade/Financeiro | journal balanceado e read models financeiros | quebrado no lançamento |
| F-11 | tarefa→nota→transição→outbox/DLQ/reconciliação | Central de Tarefas + Governance | case/maintenance request, evento e estado reconciliado | quebrado/P0 |
| F-12 | artigo/armazém→movimento/transferência/contagem→saldo | Armazém | ledger de stock e saldo reconciliado | parcial/não provado UI |
| F-13 | colaborador→assiduidade/variáveis→payroll→payment/journal | RH/Processamento | snapshots payroll, aprovação, pagamento e diário | parcial/não certificado |
| F-14 | factos→Torre/alerta/analytics/export→drill-down | Dashboard/Operações/Alertas/Analytics | read model derivado e ligação à origem | parcial |

Nenhum fluxo está release-certified. F-02/F-04 têm a evidência backend mais
forte; F-05, F-08, F-09, F-10 e F-11 têm quebras frontend-backend confirmadas.

## 5. UX e uniformidade

Confirmado no browser:

- dashboard desktop tem hierarquia e shell consistentes;
- dashboard 360 não tem overflow global, mas a navegação horizontal de contexto
  fica visualmente truncada e exige affordance explícita;
- formulário de tarefa 360 comprime opções de domínio e texto, ainda utilizável
  mas abaixo do padrão de clareza comercial esperado;
- Oficina expõe “This functionality is not enabled for your subscription” e
  `[object Object]`, em vez de mensagem localizada, deduplicada e acionável;
- `faturacao` e `verify-email` não fornecem o landmark `main` esperado;
- a amostragem estática encontrou cobertura desigual de loading, error, empty,
  forbidden e partial/degraded; presença de página não equivale a estado
  completo.

## 6. Por que os gates atuais deram verde

- design-system procura sobretudo hex, alguns aliases/focus e um conjunto
  limitado de ficheiros/chaves;
- accessibility procura padrões sintáticos selecionados, não WCAG integral;
- no-demo usa uma lista curta e não detetou viaturas hardcoded nem UUID zero em
  tarefas;
- BFF boundary impede fetch direto e headers inseguros, mas não valida o
  endpoint, o método, o schema ou `Response.ok`;
- tipos gerados provam que o OpenAPI foi gerado, não que todas as chamadas o
  consomem corretamente.

## 7. Evidência de engenharia disponível

- Manager unitário: 89/89.
- Driver unitário: 26/26.
- Manager build: 72 rotas geradas.
- Manager Playwright: 16 passaram e uma falhou por timeout axe em `/oficina` na
  execução ampla mais recente.
- Backend integral: 706 passaram, uma falhou e uma foi ignorada; a falha do
  outbox passou isoladamente, caracterizando não-hermeticidade da suíte/base.
- Auditoria npm: seis vulnerabilidades high de produção e nove high no grafo
  completo na verificação atual.

Estes números são evidência local útil, mas não anulam as falhas de runtime.

Os comandos, requests/responses sanitizados, traces e screenshots devem compor
um evidence pack versionado por SHA na execução F7; os números desta baseline,
por si só, não podem ser promovidos.

## 8. Segunda opinião e reconciliação

Duas revisões adversariais independentes confirmaram o NO-GO e rejeitaram a
primeira versão de F7 por permitir falso verde. A versão reconciliada passou a
exigir ledger por fluxo/endpoint, schemas não vazios, idempotência/replay,
RBAC/cross-tenant, contrato/BFF Governance e decisões de domínio para Fuel,
AP e Accounting. Segurança e QA participam desde F7.1, não apenas na promoção.

## 9. Plano de recuperação

Executar a Onda F7 de `docs/FRONTEND_REFOUNDATION_PLAN.md` e o replaneamento da
secção 15.11 de `docs/ROTAS_MASTER_DELIVERY_PLAN.md`. A prioridade é fechar
verticais, não aumentar o número de páginas:

1. toolchain/CI reproduzível;
2. ledger por fluxo com path, método, schemas, RBAC, tenant, idempotência,
   persistência, erros e retorno UI;
3. response models e contratos estruturais, incluindo Governance dedicado;
4. cinco famílias quebradas e restantes gaps da matriz;
5. erro fail-closed, replay/cross-tenant e estados uniformes;
6. fluxos F-01 a F-14 reais, desktop/mobile e offline;
7. revalidação independente, staging, piloto e promoção.

## 10. Veredito

O frontend é uma aplicação real em construção, não apenas um mock. Contudo,
não é uniforme nem está perfeitamente casado com o backend, e ainda consegue
mostrar ausência ou sucesso onde houve erro. Não está fechado nem pronto para
venda. O produto permanece NO-GO até os critérios do Issue #42 e os gates G0 a
G5 serem comprovados no mesmo release candidate.

## 11. Incremento de recuperação executado em 2026-08-20

Estado: **melhoria local comprovada; produto continua NO-GO**.

Entregue:

- toolchain declarada em Node `20.20.2` e npm `10.8.2`, com instalação
  fail-closed fora da versão suportada;
- auditor estático UI/BFF/OpenAPI com 9/9 testes: 208 referências, 162
  operações distintas, 160 violações atuais, das quais 153 são respostas 2xx
  sem schema e sete são operações ausentes concentradas em Tarefas/Governance;
- F-05: checklist corrigida para `GET /api/v1/checklists` e erro deixou de ser
  apresentado como lista vazia;
- F-08: compra de combustível reconciliada com
  `POST /api/v1/fuel-operations/purchases`, payload canónico e
  `Idempotency-Key` preservada pelo BFF;
- F-09: PO reconciliada com `/payables/purchase-orders`, nomes de campos
  canónicos e pagamento movido para a operação atómica
  `/payables/invoices/{id}/pay`; ação visual inerte “Nova Fatura” removida;
- F-10: lançamento movido para `/accounting/journal-entries`, `lines` canónico
  e bug de estado React que anulava débito/crédito corrigido;
- backend financeiro passou a resolver os códigos PGC sem ponto legados e os
  códigos canónicos `4.2`, `1.2` e `6.3` criados pelo seed oficial.

Evidência local:

- Manager: 22 ficheiros, 95/95 testes; typecheck verde;
- auditor de contratos: 9/9 testes;
- backend: 708 passaram, um ignorado; Ruff verde nos ficheiros alterados;
- Chrome isolado: compra de combustível pela UI devolveu 200 e fechou o modal;
- Chrome isolado: lançamento equilibrado manteve `1/0` e `0/1`, habilitou o
  submit, devolveu 201 e apresentou “Lançamento Gravado”;
- backend autenticado/PostgreSQL: checklist GET, compra fuel, journal, criação
  de fornecedor, PO, invoice e pagamento atómico produziram efeitos reais.

Limites que impedem promoção:

- F-09 ainda não tem repetição integral pelo browser; a sessão do controlador
  tornou-se instável na navegação do detalhe do terceiro;
- F-11 continua com sete referências sem contrato ROTAS e mistura um serviço
  Governance de autenticação própria; exige BFF dedicado e decisão de
  identidade/tenant, não um rename inseguro;
- 153 operações consumidas continuam com resposta OpenAPI 2xx sem schema;
- a execução atual continua em Node 24; falta repetir Manager e Driver no Node
  20.20.2 suportado;
- o browser registou um bloqueio de rede externo e um 404 na página de login;
  as origens ainda precisam ser identificadas para console limpo;
- faltam CI remota, staging, dois tenants, negativos RBAC/cross-tenant,
  replay/conflito e certificação independente no mesmo SHA.

## 12. Incremento F-11 executado em 2026-08-20

Estado: **F-11 parcialmente funcional e provado localmente; produto continua
NO-GO**.

Correções entregues:

- BFF Governance dedicado em `/api/governance/**`, com URL upstream fixa,
  timeout, limite de payload/resposta, validação UUID/schema e erro canónico;
- sessão ROTAS revalidada em `/api/v1/tenants/me` antes de escolher a credencial;
- chave Governance tenant-scoped, apenas no servidor, suportando mapa por tenant
  e Docker secret file; Bearer ROTAS e `X-Tenant-Id` não atravessam a fronteira;
- contratos corrigidos para `/api/v1/cases/`, `case_type_code`,
  `Idempotency-Key` e `/{case_id}/transitions`;
- novo contrato tenant-scoped de leitura de tipos de caso ativos em
  `/api/v1/cases/types/`, protegido por `cases:read`, sem exigir `admin:read`;
- formulário usa viaturas e tipos de caso reais; UUID zero e viaturas hardcoded
  foram removidos;
- detalhe Workshop real adicionado; histórico Governance usa transições
  append-only; notas inexistentes são explicitamente indisponíveis;
- falso painel “Iniciar Execução”/ações inertes removido da jornada;
- staging separa a chave do Manager da chave do adaptador ROTAS, monta ambas
  como Docker secrets e exige o UUID ROTAS correspondente; a chave do Manager
  fica limitada a `cases:read` e `cases:write`.

Evidência atual:

- Chromium/Playwright isolado: login → criar caso → listar → detalhe → resolver
  e criar viatura real → criar pedido Oficina → listar, com respostas 201/200 e
  zero erros de consola; a credencial Governance local usada no ensaio tinha
  apenas `cases:read/cases:write`; screenshot em
  `apps/manager/test-results/tasks-governance-detail.png`;
- Manager: 24 ficheiros, 108/108 testes, typecheck e build de 74 rotas verdes;
- Governance: 52/52 testes; Ruff verde;
- backend ROTAS: 714/714 testes executados, um skip; OpenAPI regenerado;
- staging manifest: 6/6 testes;
- auditor frontend/OpenAPI: 203 referências, 156 operações e 99 violações,
  todas agora de schema 2xx vazio; as sete operações ausentes foram eliminadas
  e 14 operações F-11/dependências receberam modelos explícitos de sucesso.

Limites restantes:

- staging suporta o piloto single-tenant com credenciais separadas; SaaS
  multi-tenant ainda exige provisionamento/rotação/revogação dinâmica e auditada
  do mapa tenant→chave;
- faltam negativos de browser para sessão adulterada, scopes, tenant A→B,
  replay/conflito e Governance indisponível;
- notas Governance, associação caso↔OS, anexos e transições orientadas por
  `available` não possuem fluxo UI completo;
- outbox/DLQ/reconciliação não foram certificados nesta jornada;
- permanecem 99 referências frontend a respostas OpenAPI sem schema;
- não há CI remota, staging implantado, piloto assinado ou release certification
  no mesmo SHA.

### 12.1 Incremento F-01 autenticação e sessão

- nove operações de login, MFA, recuperação de palavra-passe e sessões passaram
  a expor respostas de sucesso tipadas;
- o login documenta separadamente a emissão de tokens e o desafio MFA;
- respostas de recuperação preservam a omissão de token/URL quando não
  aplicável, sem introduzir campos `null` incompatíveis;
- token e URL de recuperação deixaram de ser expostos por resposta em staging;
  apenas ambientes `development` e `test` mantêm essa conveniência;
- 14 testes focados de autenticação/contrato, 712 testes backend e 108 testes
  Manager passaram; typecheck, drift OpenAPI e Ruff estão verdes;
- o ledger caiu de 132 para 122 violações, mas F-01 ainda precisa de browser
  negativo e staging no mesmo release candidate para certificação runtime.

### 12.2 Incremento F-02 cliente, contrato, ordem e viagem

- 20 operações de clientes, contratos, trip-orders e lifecycle de viagens
  passaram a expor respostas de sucesso tipadas;
- a atribuição documenta conjuntamente `trip_order` e `trip`; o despacho
  documenta `trip` e o evento persistido, sem reduzir respostas compostas a um
  objeto genérico;
- valores monetários preservam o formato numérico JSON observado pelo Manager;
- 21 testes de clientes/contratos/trip-orders, 15 testes de despacho/cache e
  714 testes backend passaram; Manager manteve 108/108 e typecheck verde;
- o ledger caiu de 122 para 99 violações. F-02 permanece parcial até browser,
  negativos cross-tenant/replay e staging no mesmo release candidate.

### 12.3 Runtime browser F-02: cliente e contrato

- Chromium real confirmou login, validação obrigatória do formulário de
  cliente, `POST /api/v1/clients` 201 e persistência PostgreSQL;
- a primeira execução revelou que `router.refresh()` continuava a servir a
  lista ISR antiga durante 30 segundos. Clientes, contratos, trip-orders e
  viagens operacionais passaram a usar leitura sem cache após mutações;
- o frontend enviava `assigned_vehicle_id`/`assigned_driver_id`, enquanto o
  contrato backend exige `vehicle_id`/`driver_id`; o payload e a resposta
  composta `trip_order` + `trip` foram alinhados;
- o seletor de cliente do contrato era renderizado atrás da modal (`z-index`
  50 contra 200), tornando as opções visíveis mas não clicáveis. O popover foi
  promovido para a camada 300;
- o novo E2E cliente→contrato falhou antes das correções e passou depois:
  autenticação, criação de cliente, atualização imediata da lista, seleção do
  cliente, criação do contrato e atualização imediata da tabela;
- a revisão de contrato encontrou ainda duas ações quebradas na Torre de
  Controlo: iniciar viagem omitira o `km_start` obrigatório e fechar viagem
  enviava `pod_received/pod_waiver`, campos que não existem no contrato de
  fecho operacional. Testes RED reproduziram o primeiro erro; ambos os helpers
  e a UI passaram a usar os schemas efetivos, com validação de quilometragem;
- Manager passou 112/112 testes, typecheck e build de 74 rotas; o E2E focado
  passou 2/2 incluindo setup autenticado. O auditor OpenAPI permanece em 99
  violações, sem regressão;
- bloqueador confirmado: depois de expirar o access token, pedidos Server
  Component concorrentes tentam rodar o mesmo refresh token. Uma rotação passa
  e as restantes recebem 401, fazendo a navegação voltar ao dashboard. A
  correção de autenticação requer aprovação de segurança específica;
- não existe interface Manager para criar/confirmar trip-order. A UI apenas
  lista ordens `planning` e tenta atribuí-las. Assim, o fluxo completo
  cliente→contrato→ordem→atribuição→autorização→viagem continua impossível de
  executar exclusivamente pelo frontend.

### 12.4 Fecho local F-02 e renovação de sessão — 2026-08-21

Esta secção substitui os dois bloqueadores locais registados no final de
12.3, sem transformar evidência local em certificação de release.

- foi implementada a interface Manager para criar uma ordem em rascunho,
  vinculada ao contrato e cliente selecionados, confirmá-la e atribuir
  viatura/motorista;
- a listagem da Torre de Controlo passou a abranger `draft`, `confirmed` e
  `planning`, preservando o requisito de confirmar antes de atribuir;
- o E2E Chromium executou a cadeia
  cliente→contrato→ordem→confirmação→atribuição→viagem e confirmou a viagem
  persistida em `/viagens`, sem erros de consola nem respostas API 4xx/5xx
  observadas nesse cenário;
- o backend agora bloqueia, na mesma transação, o refresh token e a sessão do
  dispositivo. O teste concorrente reproduziu 200/200 antes da correção e
  passou com exatamente uma rotação aceite e a reutilização rejeitada;
- o Manager usa single-flight por processo e o proxy renova tokens expirados
  antes dos Server Components, propagando os novos cookies à requisição
  interna e à resposta do navegador;
- um segundo cenário Chromium substituiu o access token por um valor expirado
  e abriu o dashboard com a sessão renovada, sem 401 de API observado;
- evidência local final: Manager 117/117, typecheck e build de 74 rotas;
  backend 715 executados e verdes + 1 skip, Pyright sem erros; E2E focado 3/3;
- permanecem vermelhos o auditor OpenAPI com 99 referências de sucesso sem
  schema e o Ruff global com 51 ocorrências preexistentes fora deste
  incremento. CI remota, staging com múltiplas instâncias/tenants, replay sob
  balanceador e piloto do mesmo RC continuam sem evidência.

Conclusão: F-02 está **funcional local** até criação da viagem. Não está
release-certified e o produto permanece **NO-GO comercial e de produção**.

### 12.5 Autorização de saída e início real da viagem — 2026-08-21

Uma revisão adversarial do elo criação→execução encontrou três bypasses que
impediam considerar a viagem funcional: o Manager oferecia início ainda em
`planned`, o endpoint `/start` aceitava estados anteriores ao despacho e a
aprovação visual marcava sete verificações como verdadeiras sem confirmação
explícita do operador.

- `/start` agora aceita apenas uma viagem `dispatched`; tentativa direta em
  `planned` retorna `409 dispatch_required`;
- o Manager passou a representar `planned → dispatch_pending → dispatched →
  in_progress`, pedir autorização antes da saída e enviar `km_start` no início;
- a aprovação exige sete confirmações explícitas. O backend continua soberano:
  um contrato que requer Load Permit é bloqueado sem documento real, mesmo que
  o operador confirme a verificação;
- os negativos backend comprovaram `404` no acesso tenant A→B, `403` sem
  `trips.dispatch` e `409 idempotency_key_reused` no replay com payload diferente;
- o retry após renovação de sessão preserva o `Idempotency-Key`; uma nova
  reavaliação de clearance usa uma nova chave, para não repetir eternamente o
  resultado bloqueado depois de a evidência documental mudar;
- o cache da Torre usava `ct:kpis:<tenant>`, fora do namespace invalidado pelas
  mutações. A chave passou a `tenant:<tenant>:control-tower:<representação>`,
  incluindo data e paginação;
- a fila `pending_dispatch` retinha viagens já despachadas. Agora exige também
  `Trip.status == dispatch_pending` e desaparece depois do despacho;
- o seed E2E direto passou a registar todos os modelos antes de libertar a
  viagem sintética, evitando falha de resolução de foreign keys;
- o Chromium executou cliente→contrato sem Load Permit→ordem→confirmação→
  atribuição→pedido de saída→aprovação explícita→despacho→`km_start`→`in_progress`,
  sem erros de consola nem respostas API 4xx/5xx; E2E focado 3/3;
- evidência local: Manager 123/123, typecheck, build de 74 rotas, BFF/design/
  no-demo/acessibilidade verdes; backend focado 42/42, Ruff do escopo verde e
  Pyright 0 erros; suíte backend integral 719 verdes + 1 skip + 1 falha de
  drift RLS descrita abaixo.

A suíte backend integral não pode ser declarada verde neste ambiente: a base
local está em revisão Alembic `rec15`, mas o checkout tem `rec13` como head e
`alembic current` falha ao localizar `rec15`. A tabela
`trip_document_requests`, inexistente neste código, produz o único mismatch RLS
remanescente. O auditor OpenAPI continua vermelho com 99 referências 2xx sem
schema; CI remota, staging, multi-instância e piloto continuam sem evidência.

Conclusão: F-02 está **funcional local até viagem iniciada**, mas não está
release-certified. O produto permanece **NO-GO comercial e de produção**.

### 12.6 Base limpa, contratos de resposta e Gestão de Acessos — 2026-08-21

A anomalia RLS de 12.5 foi isolada sem alterar nem apagar a base antiga. Uma
base PostgreSQL nova, `rotas_rec13_audit_20260821`, partiu vazia e recebeu
`alembic upgrade head` até `rec13`.

- `alembic current` devolveu `rec13 (head)` e `alembic check` não encontrou
  novas operações de upgrade;
- a base limpa contém 114 políticas de isolamento e o teste RLS passou 6/6;
- a suíte backend integral passou 721 testes, com 1 skip. Portanto, a falha
  única observada sobre `trip_document_requests` era drift da base antiga em
  `rec15`, não uma falha reproduzível do checkout atual;
- alertas, notificações e utilizadores receberam schemas OpenAPI de sucesso;
  o auditor melhorou de 99 para 88 referências 2xx sem schema, mas continua
  vermelho;
- a Gestão de Acessos dizia “convidar”, embora a API criasse imediatamente um
  utilizador e exigisse password. A interface agora assume corretamente
  “Criar Utilizador”, pede password temporária e invalida `/settings` após as
  mutações;
- o Chromium autenticado criou um utilizador e confirmou a sua presença na
  lista atualizada, sem erros de consola nem respostas API falhadas; E2E focado
  2/2;
- regressão final: Manager 124/124, typecheck e build de 74 rotas verdes;
  cliente TypeScript sem drift e `git diff --check` limpo.

Conclusão: a camada Gestão de Acessos possui agora uma jornada vertical local
real e o backend atual é reproduzível numa base vazia. Isto não fecha o
produto: permanecem 88 contratos de resposta incompletos, os demais fluxos
F-01 a F-14, CI remota, staging multi-tenant/multi-instância, segurança
operacional, soak e piloto do mesmo release candidate. Veredito global:
**NO-GO comercial e de produção**.

### 12.7 Contratos de Motoristas e Rotas Conhecidas — 2026-08-21

Dois incrementos contract-first fecharam as operações do Manager mais
concentradas em Motoristas e Rotas Conhecidas.

- Motoristas: listagem, criação, detalhe, edição, pairing code, scorecard e
  histórico passaram a expor respostas OpenAPI tipadas sem filtrar campos que
  o Manager já consome;
- Rotas Conhecidas: listagem, criação, edição e remoção passaram a usar modelos
  de request e response explícitos; os payloads genéricos `dict` deixaram de
  ser o contrato público;
- o auditor caiu de 88 para 72 referências 2xx sem schema, mantendo zero
  operações frontend ausentes;
- o OpenAPI foi novamente exportado, o cliente TypeScript regenerado e o
  controlo de drift passou;
- gates focados: 46 testes backend + 1 skip e Ruff do escopo verdes;
- gates integrais: backend 723/723 + 1 skip na base limpa `rec13`; Manager
  124/124, typecheck e build de 74 rotas verdes;
- a regressão revelou um teste HOS dependente da hora UTC. O worker passou a
  ser testado de forma determinística contra a classificação HOS recebida, e
  os oito testes próprios do cálculo continuam reais. A definição comercial
  de dia UTC versus turno contínuo/rolling 24h não foi alterada e requer
  validação explícita de domínio e conformidade antes da certificação.

Conclusão: os contratos usados pelos fluxos de Motoristas e Rotas Conhecidas
estão **fechados localmente**, mas o gate agregado permanece vermelho em 72.
O produto continua **NO-GO comercial e de produção**.
