# ROTAS — Instruções Canónicas para Agentes

- Estado: vinculativo
- Atualizado em: 2026-08-23
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
- Motorista pode solicitar documento em falta e consultar documentos emitidos.
- Viagem fechada é somente leitura e não aceita novos documentos/pedidos.
- Histórico exclui rascunhos e inclui viagens atribuídas concluídas/canceladas.
- Toda mutação offline valida `(tenant_id, driver_id, device_id)`, ownership da
  entidade, operação permitida e estado do lifecycle.
- Idempotência e cache não podem ser partilhadas entre motoristas/dispositivos.
- API Driver/Sync usa schemas públicos próprios; nunca o serializer integral de
  gestor nem campos internos de custo, receita ou margem.

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

Os slices C2 até `426e865` removeram ações administrativas da PWA e publicaram
Minhas Viagens, histórico, detalhe, requisitos canónicos, documentos, download,
pedido em falta e terminal read-only. O próximo incremento obrigatório continua
em C2: reconciliar a checklist legada do Manager, implementar cache/recovery
offline das novas leituras e ampliar E2E. Depois deve repetir-se backend e
frontend no mesmo SHA integrado e validar Android físico. Só então se retomam
build reproduzível, Actions/supply chain e CI. Estado: `NO-GO`.
