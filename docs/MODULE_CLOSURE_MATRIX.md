# ROTAS Module Closure Matrix

Estado: activo
Data: 2026-08-23

## Override de auditoria — Issue #42

Esta secção substitui qualquer classificação mais otimista existente abaixo
até nova auditoria no SHA integrado. Ver
`docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md`.

| Área | Estado vinculativo | Razão bloqueante |
| --- | --- | --- |
| Frota e Pessoas | avançado local; não fechado | pairing e ownership Driver verdes localmente; faltam RC, revisão e Android |
| Transporte e Carga | C2 integrado local; não fechado | listas, requisitos, pedidos, download, checklist Manager canónica, terminal read-only, recovery e E2E verdes no mesmo HEAD; falta Android/RC |
| Sync/Offline | avançado local; não fechado | ownership, idempotência e recovery de leituras por identidade verdes localmente; faltam staging/Android no RC |
| Contratos API Driver | avançado local; não fechado | DTOs/OpenAPI e consumidor PWA alinhados para listas, histórico, documentos, pedidos, download e cache; faltam CI/RC |
| Segurança multi-tenant | avançado local; não certificado | ownership intra-tenant provado localmente; falta RLS restrita e pentest no RC |
| ERP financeiro/inventário | parcial | fontes duplicadas, limiar de stock fixo e fecho ponta a ponta não certificado |
| SaaS comercial | parcial | planos públicos, pagamento/subscrição, branding e operação comercial pendentes |
| Business Intelligence | implementado parcialmente; não Trusted BI | faltam lineage/reconciliação/SLO/piloto no mesmo RC |

Nenhum módulo pode usar `fechado MVP` como sinónimo de enterprise ou de
release-certified.

## Definition of Closed

Um modulo so e considerado fechado quando:

- tem fonte de verdade explicita e estados validos;
- mutacoes criticas sao idempotentes ou naturalmente repetiveis sem duplicacao;
- tenant isolation e permissoes sao aplicadas no service layer;
- alteracoes criticas deixam audit log;
- falhas operacionais relevantes geram exception ou estado visivel;
- mudancas de schema possuem migration Alembic;
- testes cobrem happy path, conflito, replay e regressao de integracao;
- boards consomem o estado quando o modulo afecta decisao operacional.

## Estado por Modulo

### Módulos de negócio do tenant

Esta tabela segue a `ADR-011`. Existência de rota/página não torna a capacidade
licenciável nem fechada; `tms/oficina` continuam bundles legados até E0.

| Módulo de negócio | Inclui | Estado | Lacunas para fechamento |
| --- | --- | --- | --- |
| Centro de Comando | control_tower, alerts, operational_exceptions | avançado local; não fechado | configuração de filas por tenant, escalonamento, QA visual e RC |
| Frota e Pessoas | vehicles, drivers, availability | avançado local; não fechado | pairing/ownership verdes localmente; faltam revisão, RC e Android |
| Transporte e Carga | trip_orders, trips, checklists, cargo, operations | C2 integrado local; não fechado | falta Android físico e certificação RC |
| Custos e Margem | trip costs, custos de oficina, reconciliação e margem | parcial | separar estimado/realizado, certificar fontes e reconciliar receita sem ownership de billing |
| Combustível | fuel | parcial | fechar API/movimentos, contagens, desvios, segregação, reconciliação e jornada E2E |
| Oficina e Manutenção | workshop | avançado local; não fechado | provar lifecycle integral, stock/custos/billing reconciliados, board, exceções e gates enterprise no mesmo RC |
| Clientes, Vendas e Cobrança | clients, contracts, billing, AR | avançado local; congelado | billing permanece congelado; faltam Cliente/Terceiro, O2C/AR, reconciliação e certificação E2 |
| Compras e Fornecedores | suppliers, procurement, AP | parcial | requisição até pagamento, aprovações, three-way match, devoluções e reconciliação E1 |
| Inventário e Ativos | inventory, warehouses, asset lifecycle | parcial | lote/série/validade, contagem, valorização e ciclo de vida de ativos ainda não fechados |
| Finanças e Contabilidade | accounting, treasury, close | básico/parcial | entidade legal, filial, centro de custo, período, fecho, reconciliação e demonstrações certificadas |
| Recursos Humanos | HR, payroll, people assets | parcial | lifecycle laboral, segregação salarial, payroll legal, contabilização, pagamentos e ativos E3 |
| Business Intelligence | semantic layer, dashboards, alerts, workshop intelligence | parcial; não Trusted BI | catálogo KPI, lineage, freshness, reconciliação, drill-down, alertas e piloto E4/E5 |

### Capacidades de governação

| Capacidade | Estado | Lacunas para fechamento |
| --- | --- | --- |
| Administração do Tenant | parcial | entidades legais, filiais, centros de custo, sequências e governação intra-tenant E0 |
| Administração SaaS | parcial | catálogo, subscrições, entitlements, limites/consumo, suporte JIT e offboarding E0 |

### Fundação técnico-operacional

Não é módulo vendável. `auth`, `files`, `sync`, `audit`, idempotência, outbox e
integrações são controlos transversais. Estão **avançados localmente, não
certificados**: faltam CI, staging multi-instância,
observabilidade, Android físico, pentest e evidência no mesmo RC.

### Modulos Tecnicos Backend

| Modulo | Estado | Lacunas para fechamento |
| --- | --- | --- |
| audit | avancado | cobertura transversal residual |
| contracts | operacional MVP | politicas adicionais de reajuste/renovacao |
| vehicles | fechado MVP | evolucoes enterprise futuras |
| drivers | avançado local; não fechado | pairing, ownership e contratos base verdes; falta concluir C2 e certificar RC |
| files | operacional MVP | storage adapter R2 |
| checklists | avancado | politicas adicionais e visual hardening |
| trip_orders | fechado MVP | evolucoes enterprise futuras |
| trips | C2 integrado local | criação proibida, listas, detalhe, download, UI, cache tenant+driver+session-scoped e E2E verdes; falta Android/RC |
| cargo | C2 avançado local / não fechado | emissão de gestor, pedido Driver, checklist canónica e bloqueio após fecho reconciliados localmente; falta prova integrada/RC |
| billing | avancado | reconciliacao final e politicas adicionais |
| fuel | operacional MVP | politicas adicionais |
| workshop | operacional MVP | ampliar board visual e politicas enterprise |
| operational_exceptions | avancado | politicas adicionais e integracao final |
| control_tower | avancado | dashboard executivo TMS adicionado; faltam QA visual final e configuracao de filas por tenant |
| alerts | operacional MVP | escalonamento externo por canal |
| tenants | avancado | branding e politicas administrativas adicionais |
| users | operacional MVP | politicas enterprise |
| auth | operacional MVP | recovery codes e gates adicionais por email verificado |
| sync | avançado local; não fechado | ownership/idempotência e recovery de leituras verdes localmente; faltam staging e Android no RC |

## Ordem de Fechamento

1. C0-C4: convergência Driver/Sync, branches, contratos e certificação Issue #42.
2. Cliente <-> Terceiro por `widen-migrate-narrow`.
3. E0: fronteira SaaS e administração comercial.
4. E1: Procure-to-Pay e inventário unificado.
5. E2: Order-to-Cash, Oficina e fecho financeiro.
6. E3: Pessoas, payroll e ativos.
7. E4: Trusted BI.
8. E5: piloto e promoção comercial.
