# ROTAS — Estado Atual e Plano de Convergência

- Estado: baseline vinculativa
- Data da auditoria: 2026-08-22
- Branch: `codex/issue42-convergencia-manager-driver-backend`
- SHA auditado: `c912cb1c9e098b8cd4899c138232af7a02432c54`
- PR: `#44`
- Decisão: **NO-GO para merge, piloto, venda e produção**

## 1. Parecer executivo

O ROTAS possui uma fundação técnica avançada, mas está em convergência e
estabilização pré-RC. A branch auditada melhora contratos Manager/backend, RLS,
RBAC, idempotência, outbox e cobertura de testes; contudo, não integra a linha
Driver aprovada no Android e contém fronteiras de autorização intra-tenant
insuficientes.

O produto deve ser descrito como **beta interno avançado**, não como ERP/TMS
enterprise vendável. O PR #44 requer alterações e a Issue #42 permanece aberta.

## 2. Evidência reproduzida no SHA auditado

| Camada | Resultado |
| --- | --- |
| Git | worktree versionada limpa; 39 commits acima da base; 734 ficheiros alterados |
| Backend Ruff | verde em `app tests` |
| Backend compileall | verde |
| Backend pytest | `936 passed, 1 skipped` |
| Backend Pyright | vermelho: 4 erros |
| Manager typecheck | verde |
| Manager Vitest | `128/128` |
| Manager contratos | 208 referências, 158 operações, 0 violações Manager |
| Manager BFF/no-demo/acessibilidade estática | verde |
| Manager build | inconclusivo no checkout OneDrive por `EPERM` no `.next` |
| Driver typecheck/Vitest/build | verde; `30/30`; PWA compilada |
| Alembic | `rec13` head/current; check sem operações, com avisos de ciclos FK |
| GitHub CI | `startup_failure`; nenhum job efetivo do CI |
| GitHub governance | falhou sem passos executados |

Testes locais fortes não compensam falha de autorização nem constituem
certificação remota.

## 3. Bloqueios confirmados

### P0-DRV-01 — Driver criava e atribuía a si próprio viagens

No SHA `77385bb`, o backend passou a rejeitar com `403` tanto
`POST /api/v1/driver/trips` como `GET /api/v1/driver/vehicles`; o bootstrap já
não expõe frota geral e o teste prova que nenhuma viagem é persistida. A PWA
antiga ainda contém a jornada “Nova viagem” e será substituída em C2.

Critério de fecho: Driver recebe apenas viagens atribuídas e tentativas de
criar/atribuir viagem ou listar frota geral devolvem `403` sem efeito persistido.

Estado: **backend fechado localmente; jornada completa ainda aberta em C2**.

### P0-DRV-02 — Linha Android aprovada não convergiu

Os commits `ebb583b` e `50955e1` não são ancestrais do SHA auditado. Faltam na
branch atual Minhas Viagens, histórico, detalhe operacional, documentos,
pedidos de documento, guia de transporte, reconciliação de pedidos e bloqueio
de emissão após fecho.

Critério de fecho: portar seletivamente o contrato e as jornadas, preservando
as melhorias atuais e repetindo testes no SHA integrado.

### P0-SYNC-01 — Sync não prova ownership intra-tenant

Os SHAs `51509d5` e `58b730a` passaram a exigir que o `device_id` do batch
coincida com o JWT Driver e bloquearam no dispatcher criação de viagem,
licença, manifesto e documento de transporte. `d30f1b0` protegeu criações
ligadas à viagem e o lifecycle; `aa28bc2` protegeu identidade/viatura em
checklist e combustível; `e7de9e6` protegeu update de combustível. `5c7588e`
fechou ownership dos updates de checklist, paragem e prova de entrega, incluindo
teste negativo com outro motorista do mesmo tenant.

Critério de fecho: allowlist por persona/operação, ownership por entidade e
`device_id` derivado/verificado contra o principal autenticado.

### P0-SYNC-02 — Idempotência pode atravessar motoristas/dispositivos

A chave é única apenas por `(tenant_id, idempotency_key)`. O replay não compara
`driver_id` nem `device_id` apesar de ambos serem persistidos.

Critério de fecho: owner mismatch falha fechado; concorrência e replay
cross-driver/cross-device possuem testes negativos.

Estado em 2026-08-23: **fechado localmente** por `9698314` e `e1d69c4`. O
replay valida motorista e dispositivo antes de comparar hash ou devolver cache;
tentativas divergentes são auditadas sem expor `server_id`. A corrida entre dois
dispositivos consolida efeito, chave e evento numa única transação e aceita
exatamente um efeito físico. A partição Driver/Sync isolada passou `57/57`;
Ruff e Pyright focados ficaram verdes.

### P0-TEST-DB-01 — Pytest escreve na base operacional configurada

`backend/tests/conftest.py` usa `AsyncSessionLocal`/`DATABASE_URL` sem rollback
ou cleanup. A configuração mascarada observada foi `localhost:55432/rotas` e
os services fazem commits reais. A repetição da suíte acumula fixtures e não é
evidência isolada/repetível.

Critério de fecho: implementar ADR-010 com `TEST_DATABASE_URL` obrigatório,
base PostgreSQL efémera `rotas_test_*` por execução/worker e falha fechada
contra URLs operacionais. Não limpar os dados existentes sem autorização.

Estado em 2026-08-22: **fechado localmente em modo serial** por `0b7a36c` e
`3acabde`. O guard bloqueia a coleção insegura; o runner criou uma base de
`template0`, migrou até `rec13`, executou 8 testes e deixou zero bases
`rotas_test_*`. `xdist` permanece proibido até haver uma base por worker. CI e
regressão integral ainda não foram repetidos nesta infraestrutura.

### P1-API-01 — Contratos Driver/Sync vazios

Os sucessos de `/driver/bootstrap`, `/driver/vehicles`,
`/driver/active-trip`, `/driver/trips`, `/sync/batch` e `/sync/bootstrap`
continuam com schema OpenAPI `{}`. O auditor a zero cobre o Manager, não o
Driver.

Estado em 2026-08-23: **fechado localmente** por `987273c`. Bootstrap, templates,
viagem ativa e Sync usam DTOs públicos explícitos; `DriverTripRead` exclui tenant,
contrato, billing, custos, receita e margem. `/driver/vehicles` e
`POST /driver/trips`, sempre proibidos, deixaram de anunciar `200` e documentam
erro estruturado `403`. OpenAPI e cliente TypeScript foram regenerados pelo
gerador oficial. Após a correção tipológica HR de `ccb4dc4`, o artefacto integral
atual tem digest `abadc941169773797976f4db9ff2c6b48cf37eabed8e4ff40f9863739e6fc0c4`.
Partição OpenAPI/Driver/Sync isolada `68/68`, Ruff/Pyright focados, drift,
typecheck Manager e auditor `208/158/0` ficaram verdes.

### P1-DATA-01 — Serializer Driver expõe finanças internas

O Driver recebe o serializer integral da viagem, incluindo custos, receita,
margem e identificadores de faturação. Deve existir DTO próprio com o mínimo
operacional necessário.

### P1-AUTH-01 — Pairing concorrente não é serializado

O código de pairing é lido sem lock de linha; duas requisições concorrentes
podem validá-lo antes do commit. Falta também unicidade explícita do dispositivo
por tenant/motorista.

Estado em 2026-08-23: **fechado localmente** por `9ae52b5`. O consumo usa lock
de linha e a corrida real aceita uma resposta `200` e uma `401`, com um único
dispositivo e uma única sessão. A migration `rec14` reconcilia duplicados
históricos de forma determinística antes de criar a constraint única
`(tenant_id, driver_id, device_id)`; o downgrade remove a constraint. No SHA do
commit, as partições combinadas Driver/Sync/Auth passaram `74/74` numa base
descartável migrada do zero até `rec14`; Ruff e Pyright focados ficaram verdes.

### P1-CI-01 — Gates Driver e supply chain ausentes

A CI compila o Driver mas não executa os seus testes nem Playwright. Actions
voltaram a referências mutáveis, Node não usa o patch fixado e o validador de
pins não está nesta branch.

Estado verificado em 2026-08-23: a política remota está ativa com
`allowed_actions=selected` e `sha_pinning_required=true`, enquanto `ci.yml` e
`pr18-release-evidence.yml` usam `actions/checkout@v4`,
`actions/setup-python@v5`, `actions/setup-node@v4` e
`actions/upload-artifact@v4`. O run CI `32619996532` terminou
`startup_failure` em zero segundos, enquanto Dependabot executou com sucesso no
mesmo minuto. A correção é bloquear as quatro Actions por SHA imutável e alinhar
os testes que hoje esperam tags, mas a execução continua subordinada à conclusão
de C2; não se salta a sequência para obter um check verde.

Estado local em 2026-08-26: `9cb2abe` fixou as 12 utilizações atuais das quatro
Actions por SHA, limitou o allowlist a GitHub-owned, fixou Node `20.20.2` nos
jobs e acrescentou Vitest/build/Playwright Driver à CI. Os contratos ficaram
verdes localmente (validador 6/6, 12/12 referências e testes CI/PR18/governance
8/8). A auditoria limpa no runtime canónico encontrou 6 high em produção e 9
na árvore completa, zero critical, além de `@emnapi/runtime` extraneous; o
agregador PR18 também apresentou contagens contraditórias e deve falhar fechado.
Logo P1-CI-01 e C3 permanecem abertos até remediação, CI com jobs executados e
revisão. Ver `docs/evidence/C3_CI_SUPPLY_CHAIN_BASELINE_20260826.md`.

### P1-ERP-01 — Fontes e fluxos ERP ainda parciais

- stock mínimo no Manager usa limiar fixo `5`;
- a rotina de lançamento de fatura de fornecedor não bloqueia estado diferente
  de `approved` e aparenta estar sem consumidor;
- Client, ThirdParty e ClientProfile ainda duplicam identidade e termos;
- SaaS comercial, fecho financeiro, payroll legal e Trusted BI não estão
  certificados ponta a ponta.

### P1-ARCH-01 — Taxonomia e roadmap não governavam a superfície real

A revisão de 2026-08-23 confirmou ownership duplicado da cobrança, fusão entre
Administração SaaS e Administração do Tenant, ausência de domínio explícito para
as fundações Driver/Sync e duas ordens incompatíveis entre as secções 9 e 10 do
plano mestre. No código atual, a superfície de módulos continua limitada aos
bundles `tms` e `oficina`; isto não implementa o catálogo de entitlements
enterprise descrito pelo plano.

A `ADR-011` resolve a arquitetura documental: separa módulos de negócio,
governação e fundações técnicas; atribui cobrança a Clientes/Vendas/Cobrança;
coloca a Oficina Intelligence Layer sob BI; classifica `tms/oficina` como
bundles legados; e torna C0-C4 -> Cliente/Terceiro -> E0-E5 a única sequência
executável. O alinhamento do catálogo, navegação e entidades legais é trabalho
de E0 e não pode interromper C2.

## 4. Achados reclassificados

O `test-token` só é aceite em `development`/`test`; não foi confirmado como
bypass de produção. Contudo, suites que o utilizam não provam sessão Driver,
dispositivo e ownership reais. É lacuna de evidência, não vulnerabilidade de
produção demonstrada.

O `EPERM` do build Manager em OneDrive é ambiental até reprodução em workspace
local. Não deve ser escondido nem classificado como defeito do produto sem essa
reprodução.

## 5. Sequência vinculativa de convergência

### C0 — Freeze e fonte única

- manter PR #44 sem merge;
- não iniciar Issue #43 nem nova funcionalidade;
- classificar PRs/branches como integrar, portar, substituir ou descartar;
- preservar Billing salvo Issue aprovada/gate bloqueante.

Estado em 2026-08-22: **concluído localmente** pela matriz vinculativa
`docs/BRANCH_PR_CONVERGENCE_MATRIX_20260822.md`. O freeze continua ativo e não
equivale a merge, CI remoto ou fecho da Issue #42.

### C1 — Driver e Sync fail-closed

- testes RED com token Driver e dois motoristas do mesmo tenant;
- proibir criação/atribuição/emissão administrativa;
- allowlist e ownership em todas as mutações offline;
- isolar idempotência/cache por tenant, motorista, dispositivo e sessão;
- serializar consumo do pairing.
- C1-I0: isolar a base de testes antes de executar novos pytest mutáveis.

Estado em 2026-08-22: **em progresso**. O slice `77385bb` fechou localmente
criação/atribuição de viagem e listagem de frota pelo Driver. `51509d5` vinculou
o batch ao dispositivo do JWT; `58b730a` introduziu allowlist e bloqueou
operações de despacho via Sync. `d30f1b0`, `aa28bc2` e `e7de9e6` fecharam
ownership de criação por viagem/viatura e update de combustível. `0b7a36c` e
`3acabde` fecharam C1-I0 localmente com base PostgreSQL descartável e
fail-closed. Há RED/GREEN e Ruff anteriores, mas as partições Sync/Driver e o
baseline combinado de 938 passados/1 skip antecedem o isolamento e são apenas
históricos. `5c7588e` repetiu a partição Driver isolada em `16/16` e fechou os
updates operacionais residuais. `9698314` e `e1d69c4` fecharam localmente replay
e corrida idempotente por owner/device; a partição isolada Driver/Sync passou
`57/57`. `9ae52b5` serializou o pairing e instalou a unicidade física do
dispositivo; no mesmo SHA, as partições combinadas Driver/Sync/Auth passaram
`74/74`. `987273c` fechou os DTOs públicos e a semântica 403, com partição
OpenAPI/Driver/Sync `68/68`. `ccb4dc4` eliminou os seis diagnósticos Pyright sem
alterar a semântica HR e regenerou o contrato. `97e365d` ativou a prova do plano
de viaturas ilimitado e a regressão integral numa base descartável até `rec14`
passou `968/968`, sem skips; Ruff `app tests`, Pyright e drift OpenAPI ficaram
verdes. C1/C3 estão fechados apenas na fronteira backend local; C2, CI, revisão,
staging e Android no mesmo SHA permanecem bloqueantes.

### C2 — Jornadas Driver

- Minhas Viagens atribuídas;
- detalhe, histórico e documentos;
- pedidos de documento sem emissão pelo motorista;
- viagem fechada somente leitura;
- cache offline e sync reconciliado;
- diário imutável de checklist, combustível, despesas e despacho de viagem;
- navegação canónica Hoje/Viagens/Registos/Mais conforme a `ADR-012`.

Estado em 2026-08-23: **em progresso**. `5286fe1` fechou o primeiro slice da
fronteira de persona na PWA: removeu criação de viagem, seleção de frota,
formulários de Load Permit/manifesto e o painel de cobrança. O cliente já não
exporta as chamadas proibidas; 32/32 testes, TypeScript e build PWA/service
worker passaram. `e70e79b` acrescentou os contratos paginados
`GET /driver/trips` e `GET /driver/trips/history`: ambos filtram por tenant e
motorista autenticado, excluem rascunhos e dados financeiros, e o histórico
aceita apenas `closed/cancelled`. A partição Driver/OpenAPI passou `34/34`,
Ruff/Pyright globais, drift OpenAPI, cliente TypeScript, typecheck Manager e o
auditor `208/158/0` ficaram verdes; o OpenAPI tem SHA-256 `257276c7...7303`.
`710dc9f` publicou a leitura dos documentos e requisitos canónicos usados pelo
despacho, e o pedido idempotente de documento em falta. O motorista continua
sem poder emitir; pedidos geram exceção operacional atribuída ao Driver e são
resolvidos quando o gestor disponibiliza o documento. Viagens
`closed/cancelled` rejeitam novas emissões e pedidos. Replay HTTP entre
motoristas ou dispositivos agora falha antes de devolver cache. A partição
integrada passou `82/82`; Ruff/Pyright globais, OpenAPI SHA-256
`e58f28fb...b12`, cliente TypeScript, typecheck Manager e auditor `208/158/0`
ficaram verdes.

`4d439ed` acrescentou download ownership-scoped: apenas ficheiro ligado a um
documento não cancelado da viagem atribuída pode ser obtido. Storage local
serve bytes; R2 recebe redirect para URL GET temporário apenas depois da
autorização. Outro motorista, token Manager e ficheiro não associado falham
fechados. A partição integrada com Files passou `87/87`; OpenAPI SHA-256
`cd1cb174...3dba` e gates estáticos permaneceram verdes.

`426e865` publicou a PWA de Minhas Viagens, histórico paginado e detalhe com
requisitos reais, documentos emitidos, download e pedido em falta. A navegação
separa Hoje/Viagens/Histórico, traduz estados operacionais e mostra pedido já
aberto sem permitir duplicação visual. Viagem fechada é somente leitura. Driver
passou `35/35`, TypeScript, build PWA/service worker e Chromium E2E `1/1`.

`d3b24e1` eliminou a checklist documental paralela do Manager: o endpoint legado
agora delega na mesma política canónica usada por Driver e despacho, expõe DTO
OpenAPI tipado e não sinaliza incompleto quando os requisitos configurados estão
presentes. A partição combinada de documentos operacionais, Driver e despacho
passou `57/57` na base descartável; OpenAPI, cliente e gates estáticos ficaram
verdes. `443e217` criou cache de leitura Dexie v5 isolado por
`(tenant_id, driver_id, session_id)` e purge no logout. `22ae117` ligou listas e
documentos a esse cache, apresenta freshness explícita e remove pedidos quando
os dados recuperados estão offline. Driver passou `38/38`, TypeScript e build
PWA/service worker; Playwright mobile passou `4/4`, incluindo perda de rede e
recuperação real via IndexedDB. `1513913` ampliou a suíte para `6/6`: pedido ao
gestor, download autorizado e erro persistente após retries automáticos com
recuperação manual ficaram provados no artefacto compilado.

No HEAD de produto `e0078c6`, a base efémera migrou até `rec14` e a regressão
backend passou `980/980`; Ruff, Pyright e OpenAPI ficaram verdes. Manager passou
`128/128`, typecheck, contratos/BFF e build de 74 páginas; Driver passou
`38/38`, typecheck, build PWA e Playwright `6/6`. A base operacional permaneceu
intocada.

Em 2026-08-24, a jornada foi exercitada exploratoriamente num Redmi físico
contra os processos locais e confirmou autenticação, viagem atribuída,
documentação completa e fronteira negativa de emissão. A prova ocorreu sobre
working tree com alterações não consolidadas e, portanto, **não fecha o gate
Android nem promove C2**.

A revisão de domínio e UX identificou o próximo bloqueio C2: a PWA ainda não
possui o diário operacional imutável nem a arquitetura de informação definida
na `ADR-012`. Checklist concluída já bloqueia edição no backend, mas não possui
contrato Driver de histórico; abastecimentos ainda aceitam atualização
destrutiva de factos via Sync; custos não possuem leitura Driver pública nem
ator Driver completo; despacho/allowance não possui contrato Driver próprio.
Permanece obrigatória esta ordem:

1. contratos e máquina append-only, com testes RED de mutação destrutiva;
2. DTOs Driver paginados, ownership e cache por identidade;
3. primitives/tokens canónicos e navegação Hoje/Viagens/Registos/Mais;
4. histórico e detalhe de checklist, combustível, despesas e despacho;
5. regressão integral, Playwright e Android físico no mesmo SHA/artefacto.

O primeiro incremento da etapa 1 ficou **verde local em working tree** em
2026-08-24: `fuel_log` deixou de aceitar update no Driver/Sync, o mutator e o
schema de patch foram removidos e testes com token Driver real provam que nem o
próprio motorista reescreve litros, custo ou posto. A partição Driver/Sync
passou `66/66`; a base descartável `template0 -> rec14` passou `983/983`; Ruff
`app tests` e Pyright `0/0/0` ficaram verdes. Ainda faltam o modelo de
ajuste/estorno e os contratos Driver paginados; C2 continua aberto.

O segundo incremento aplicou o `widen` do vínculo à viagem. A migration `rec15`
adiciona `trip_id` nullable, FK composta `(tenant_id, trip_id)` e índice a
`checklists` e `fuel_logs`; schemas e
serializers propagam o campo e o Sync valida que o `tripId` pertence ao mesmo
tenant, motorista e viagem ativa. Testes RED mostraram que a identidade era
descartada; GREEN prova persistência e rejeição de viagem de outro motorista.
Históricos antigos continuam nulos: não foi usado emparelhamento heurístico por
veículo/hora. Em base descartável `template0 -> rec15`, a partição
Driver/Sync/OpenAPI/checklist/fuel passou `85/85` e a regressão integral
`987/987`; dois RED adicionais provaram e fecharam criação cross-tenant tanto
no service como na constraint física. Ruff,
Pyright, OpenAPI/cliente e Manager typecheck ficaram verdes. Falta a fase
`migrate` com política explícita e os DTOs de leitura antes de qualquer `narrow`.

O terceiro incremento publicou DTOs próprios e paginação `1..100` em quatro
coleções Driver: checklist, combustível, despesas pagas pelo motorista e
despachos emitidos em `DriverAdvance`. Todas aceitam `trip_id` opcional e
revalidam `(tenant_id, driver_id, trip_id)`; token Manager recebe `403`, viagem
de outro motorista recebe `404` e páginas acima do limite recebem `422`.
Serializers não expõem tenant, outro motorista, respostas brutas, preço interno,
reconciliação, referências internas, notas de gestor ou UUID de comprovativo sem
download ownership-scoped. OpenAPI/Driver passou `58/58`; regressão descartável
`template0 -> rec15` passou `1003/1003`; Ruff, Pyright `0/0/0`, OpenAPI
`00305475b9625a65ad53d0f8162e63ba0e738c4f35269e242be7254b39690f0c`,
cliente gerado e Manager typecheck ficaram verdes. Working tree não é RC.

O quarto incremento fechou localmente a máquina de despesas. `rec16` guarda
`driver_id`, `driver_visibility`, `recorded_by_type`, `entry_type`,
`corrects_id` e motivo; o backfill usa a atribuição da viagem e classifica ator
Driver apenas quando `source_type=driver_app` e `source_id=trip.driver_id`.
Custos pagos pelo motorista ficam visíveis; os restantes ficam ocultos. A base
rejeita `UPDATE/DELETE`, ajuste e estorno são novos movimentos assinados com
lock, idempotência, auditoria e reconciliação. A partição integrada passou
`81/81`; `template0 -> rec16` e regressão integral passaram `1009/1009`; Ruff,
Pyright `0/0/0`, OpenAPI/cliente `be1f22e87fdaae8925d0a03afaa6f013d124235a1e07bb8c4be60a1340e2049d`
e Manager `128/128`, contratos `208/158/0` e build 74 páginas ficaram verdes.

O quinto incremento publicou o consumidor PWA das quatro coleções. O diário usa
cache Dexie segregado por tenant, motorista e sessão, apresenta ajuste/estorno
sem códigos internos e possui estados loading, vazio, 403, erro, snapshot
degradado e somente leitura. A navegação passou a
Hoje/Viagens/Registos/Mais; histórico permanece dentro de Viagens. O artefacto
offline deixou de depender de Google Fonts. Driver passou `55/55`, typecheck,
build `1805/93/6` e Playwright mobile `7/7`, incluindo recovery offline do
diário. Isto é verde local em working tree, sem promoção.

O próximo incremento é exclusivamente a repetição da jornada no Android físico
contra um SHA/artefacto fixado. Nenhum `narrow` de checklist/combustível está
autorizado.

A primeira passagem deste artefacto pelo Redmi confirmou atualização do service
worker, navegação canónica e tradução do estado da carga. Também revelou
`network_error` exposto no painel e preflight `400` para o origin real
`http://localhost:4174`. O frontend passou a ocultar detalhes técnicos, corrigiu
linguagem/contagens e mantém refresh do painel; a allowlist development inclui
4174 sem alterar a regra production HTTPS. CORS isolado `5/5`, Ruff focado,
Driver `55/55`, build e Playwright `7/7` ficaram verdes. O dispositivo desligou
antes da repetição pós-correção, logo Android permanece pendente.

Em 2026-08-25, a repetição física pós-CORS confirmou quatro respostas backend
`401`, em vez de falha de rede, e ausência de `network_error`/`loaded_empty` na
UI. A sessão instalada era legada: access token expirado em 2026-08-21 e nenhum
refresh token, portanto o bloqueio é novo pairing, não CORS. Teste RED/GREEN
adicionou `Voltar a emparelhar`; revisão posterior bloqueou purge imediato e
exige a confirmação explícita `Limpar e emparelhar` antes da limpeza fail-closed.
Driver passou `56/56`, typecheck, build `1805/93/6` e Playwright `7/7`; o Redmi
mostrou a primeira ação no bundle intermédio.

Com autorização explícita do utilizador, o segundo passo removeu os três
registos QA e a identidade legada. Access/refresh/tenant/driver/session ficaram
ausentes e todos os stores operacionais/Workbox foram contados a zero. A revisão
de UI seguinte reproduziu `position: sticky` e shell limitado a 390 px. RED/GREEN
fixou a barra ao fundo do viewport, safe areas, `100dvh`, scroll invariável e
largura integral em 390/412 px. O pairing passou a aceitar exatamente os seis
dígitos numéricos emitidos pelo backend, informa validade de 15 minutos e não
expõe `invalid_pairing_code`. Driver `60/60`, build `1806/93/6` e Playwright
`7/7` ficaram verdes. Em 2026-08-25 o bundle foi carregado e a ativação autónoma
foi inspecionada no Redmi. A PWA instalada usa origem `4173`, distinta do Chrome
`4174`, e reteve cliente/precache antigo; a saída real eliminou a identidade e
provou 18 stores `RotasMotoristaDB` e Workbox a zero. O bundle atual só assumiu
após ativar o worker em espera, remover o precache antigo e executar navegação
real. RED/GREEN preserva agora o worker em espera antes do mount e publica
`Atualizar aplicação` mesmo sem sessão. Isto mantém C2 aberto: falta provar a
transição física entre dois bundles, fazer novo pairing e repetir a jornada
online/degradada no mesmo SHA/artefacto.

O slice de origem/atualização eliminou a separação corrente entre 4173/4174:
`http://localhost:4173` é agora a única origem instalável, de preview e E2E;
`4174` é rejeitada por CORS e `5174` é exclusivamente desenvolvimento. O bind
interno usa `0.0.0.0` para o reverse ADB IPv4, mas nenhum consumidor navega
nesse endereço.
Preview e build usam porta/configuração explícita e `configLoader native`; existe uma única configuração
Vite e um único manifesto gerado. Em instalação já controlada, o worker procura
update antes do render, ativa a versão em espera e recarrega após `controlling`;
em primeira instalação, o render não espera o registo. RED/GREEN e trace
fecharam a regressão de bootstrap/CORS. A primeira tentativa física revelou
que bind `localhost` escutava apenas em `::1` e o reverse ADB não conseguia
buscar `sw.js`; RED/GREEN fixou bind IPv4 sem alterar a origem consumidora.
O Redmi manteve somente os reverses 4173/8000, migrou o WebAPK autónomo de
`index-tVgRH7eW.js` para `index-GP13naLz.js` e provou uma atualização seguinte
a partir do lifecycle novo. A ativação limpa bundles hashed runtime que já não
pertencem ao precache; `static-assets` reteve apenas o CSS atual. Um único alvo
standalone 4173 ficou ativo, controlado e sem worker waiting/installing. Driver
`67/67`, typecheck, build `1806/94/6`, E2E `7/7` e CORS descartável `5/5` estão
verdes localmente. Pairing e jornada online/degradada no mesmo SHA/artefacto
permanecem pendentes; isto não promove C2.

Uma nova passagem física, ainda no working tree baseado em `b00962e`, emitiu
pairing administrativo real para o único motorista da base piloto e recebeu
`200` no WebAPK, sem expor código, tokens ou device id. O Redmi apresentou
Joao Manuel, histórico atribuído `Maputo -> Beira` entregue e detalhe fechado
somente leitura com documentação completa, incluindo Load Permit, manifesto e
guia de transporte. Rede degradada, emulada apenas no alvo, mostrou
`navigator.onLine=false`, aviso operacional e preservou o detalhe/documentos;
a restauração confirmou `navigator.onLine=true`. A continuação retirou ambos os
reverses e comprovou as portas 4173/8000 recusadas no Redmi; após `force-stop`,
o WebAPK arrancou pelo Service Worker, preservou a sessão e navegou por lista e
detalhe do Dexie, com avisos explícitos de dados guardados/somente leitura.
Restaurados os dois reverses, viagens e documentos responderam `200`, os avisos
stale desapareceram e a sessão continuou válida. Depois da expiração natural
do access token, abrir Viagens produziu duas leituras `401`, refresh `200` e
repetições `200`; access e refresh mudaram sem exposição dos valores, a sessão
permaneceu emparelhada e a viagem continuou visível. O percurso funcional C2
está fisicamente provado no working tree. Persiste a repetição num
SHA/artefacto fixo. C2 continua aberto.

CI, revisão, staging e RC ainda não existem.

Em 2026-08-26 o produto foi congelado em `ae1ede2`/`a978229` e os gates locais
passaram backend `1010/1010`, Ruff/Pyright, Driver `67/67`/build/E2E `7/7`,
Manager `128/128`/build e OpenAPI. Serviços reiniciados a partir desse conteúdo
repetiram no Redmi cold start com API bloqueada e
`GET 401 -> POST refresh 200 -> GET 200`, preservando sessão, viagem e bundle
`index-GP13naLz.js`. C2 fica fechado local+físico no produto; C3, CI, staging e
RC permanecem pendentes. Ver
`docs/evidence/C2_DRIVER_ANDROID_FIXED_SHA_20260826.md`.

### C3 — Contratos e gates

- DTOs Driver/Sync e OpenAPI não vazio;
- Pyright zero;
- testes Driver e Playwright em CI;
- Node patch fixado e Actions por SHA;
- base vazia, snapshot e dois tenants/dois motoristas.

Estado em 2026-08-26: contratos, Pyright/OpenAPI, Node, pins e comandos Driver
da CI estão verdes localmente em `9cb2abe`. Supply chain está vermelha por 6
high de produção, 9 high totais, árvore extraneous e agregador PR18
contraditório. CI remota não executada. C3 continua **em progresso/NO-GO**.

### C4 — Certificação da Issue #42

- Manager, backend e Driver no mesmo SHA;
- CI com jobs efetivamente executados;
- Android físico e rede degradada;
- staging multi-instância;
- atualização coordenada de plano, matriz e ledger.

Depois de C0-C4 verdes, retomar Issue #43 e E0-E5 do plano mestre.

## 6. Critério de decisão

Qualquer P0 acima aberto mantém G2/G3 vermelhos. CI sem jobs, qualquer gate
estático vermelho no RC, staging ausente ou evidência de outro SHA mantêm
G0/G4/G5 vermelhos. Nenhum
agente está autorizado a alterar esta decisão sem nova evidência reproduzida e
registada no mesmo release candidate.
