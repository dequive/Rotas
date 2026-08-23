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
- cache offline e sync reconciliado.

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

Permanecem reconciliação da checklist legada do Manager, cache/recovery offline
das novas leituras, E2E ampliado, Android físico e repetição integral backend no
SHA integrado C2.

### C3 — Contratos e gates

- DTOs Driver/Sync e OpenAPI não vazio;
- Pyright zero;
- testes Driver e Playwright em CI;
- Node patch fixado e Actions por SHA;
- base vazia, snapshot e dois tenants/dois motoristas.

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
