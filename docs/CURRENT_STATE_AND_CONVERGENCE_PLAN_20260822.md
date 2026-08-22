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

### P0-DRV-01 — Driver cria e atribui a si próprio viagens

`POST /api/v1/driver/trips` permanece público para o Driver, a PWA mostra
“Nova viagem” e o teste atual exige `201`. O bootstrap também expõe frota ativa
do tenant sem limitar às atribuições do motorista.

Critério de fecho: Driver recebe apenas viagens atribuídas e tentativas de
criar/atribuir viagem ou listar frota geral devolvem `403` sem efeito persistido.

### P0-DRV-02 — Linha Android aprovada não convergiu

Os commits `ebb583b` e `50955e1` não são ancestrais do SHA auditado. Faltam na
branch atual Minhas Viagens, histórico, detalhe operacional, documentos,
pedidos de documento, guia de transporte, reconciliação de pedidos e bloqueio
de emissão após fecho.

Critério de fecho: portar seletivamente o contrato e as jornadas, preservando
as melhorias atuais e repetindo testes no SHA integrado.

### P0-SYNC-01 — Sync não prova ownership intra-tenant

O dispatcher aceita criação/edição de viagens, custos e documentos usando o
tenant autenticado, mas não prova em cada operação que viagem, viatura e
documento pertencem ao motorista e dispositivo autenticados. O `device_id`
auditado é recebido no payload.

Critério de fecho: allowlist por persona/operação, ownership por entidade e
`device_id` derivado/verificado contra o principal autenticado.

### P0-SYNC-02 — Idempotência pode atravessar motoristas/dispositivos

A chave é única apenas por `(tenant_id, idempotency_key)`. O replay não compara
`driver_id` nem `device_id` apesar de ambos serem persistidos.

Critério de fecho: owner mismatch falha fechado; concorrência e replay
cross-driver/cross-device possuem testes negativos.

### P1-API-01 — Contratos Driver/Sync vazios

Os sucessos de `/driver/bootstrap`, `/driver/vehicles`,
`/driver/active-trip`, `/driver/trips`, `/sync/batch` e `/sync/bootstrap`
continuam com schema OpenAPI `{}`. O auditor a zero cobre o Manager, não o
Driver.

### P1-DATA-01 — Serializer Driver expõe finanças internas

O Driver recebe o serializer integral da viagem, incluindo custos, receita,
margem e identificadores de faturação. Deve existir DTO próprio com o mínimo
operacional necessário.

### P1-AUTH-01 — Pairing concorrente não é serializado

O código de pairing é lido sem lock de linha; duas requisições concorrentes
podem validá-lo antes do commit. Falta também unicidade explícita do dispositivo
por tenant/motorista.

### P1-CI-01 — Gates Driver e supply chain ausentes

A CI compila o Driver mas não executa os seus testes nem Playwright. Actions
voltaram a referências mutáveis, Node não usa o patch fixado e o validador de
pins não está nesta branch.

### P1-ERP-01 — Fontes e fluxos ERP ainda parciais

- stock mínimo no Manager usa limiar fixo `5`;
- a rotina de lançamento de fatura de fornecedor não bloqueia estado diferente
  de `approved` e aparenta estar sem consumidor;
- Client, ThirdParty e ClientProfile ainda duplicam identidade e termos;
- SaaS comercial, fecho financeiro, payroll legal e Trusted BI não estão
  certificados ponta a ponta.

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

### C1 — Driver e Sync fail-closed

- testes RED com token Driver e dois motoristas do mesmo tenant;
- proibir criação/atribuição/emissão administrativa;
- allowlist e ownership em todas as mutações offline;
- isolar idempotência/cache por tenant, motorista, dispositivo e sessão;
- serializar consumo do pairing.

### C2 — Jornadas Driver

- Minhas Viagens atribuídas;
- detalhe, histórico e documentos;
- pedidos de documento sem emissão pelo motorista;
- viagem fechada somente leitura;
- cache offline e sync reconciliado.

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

Qualquer P0 acima aberto mantém G2/G3 vermelhos. CI sem jobs, Pyright vermelho,
staging ausente ou evidência de outro SHA mantêm G0/G4/G5 vermelhos. Nenhum
agente está autorizado a alterar esta decisão sem nova evidência reproduzida e
registada no mesmo release candidate.
