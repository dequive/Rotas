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
| Transporte e Carga | C2 parcial; não fechado | listas, requisitos, pedidos e terminal read-only verdes no backend; faltam download Driver, checklist Manager e UI Android |
| Sync/Offline | avançado local; não fechado | ownership e idempotência por motorista/dispositivo verdes localmente; faltam recovery/staging/Android no RC |
| Contratos API Driver | avançado local; não fechado | DTOs/OpenAPI explícitos para listas, histórico, documentos e pedidos; faltam download, UI e CI/RC |
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

### Modulos de Produto

| Modulo de produto | Inclui | Estado | Lacunas para fechamento |
| --- | --- | --- | --- |
| Centro de Comando | control_tower, alerts, operational_exceptions | avancado | dashboard executivo TMS coberto; faltam configuracao de filas por tenant, politicas adicionais de escalonamento e QA visual final em origem browser permitida |
| Frota e Pessoas | vehicles, drivers, availability | avançado local; não fechado | pairing/ownership e remoção de frota geral verdes localmente; faltam revisão, RC e Android |
| Transporte e Carga | trip_orders, trips, checklists, cargo, operations | C2 parcial; não fechado | listas/requisitos/pedidos e terminal read-only backend prontos; faltam download, checklist Manager, UI/E2E/Android |
| Custos e Margem | trips custos, workshop custos, billing margem | avancado | reconciliacao final e politicas adicionais de margem |
| Combustivel | fuel | operacional MVP | politicas adicionais de stock, desvios e segregacao |
| Oficina e Manutencao | workshop | operacional MVP | ampliar board visual e politicas enterprise |
| Cobranca | contracts, billing | avancado | politicas adicionais de reajuste, renovacao e reconciliacao final |
| Administracao Operacional | tenants, users, auth | operacional MVP | branding, planos publicos, pagamento/subscricao, recovery codes e politicas enterprise |
| Suporte Tecnico-Operacional | files, sync, audit | operacional | storage R2, ampliar tipos de sync e cobertura transversal residual |

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
| trips | C2 parcial | criação proibida, listas e detalhe documental tenant+driver-scoped; faltam download, UI e certificação |
| cargo | C2 parcial / não fechado | emissão de gestor, pedido Driver e bloqueio após fecho separados localmente; falta reconciliar checklist legada e provar UI/RC |
| billing | avancado | reconciliacao final e politicas adicionais |
| fuel | operacional MVP | politicas adicionais |
| workshop | operacional MVP | ampliar board visual e politicas enterprise |
| operational_exceptions | avancado | politicas adicionais e integracao final |
| control_tower | avancado | dashboard executivo TMS adicionado; faltam QA visual final e configuracao de filas por tenant |
| alerts | operacional MVP | escalonamento externo por canal |
| tenants | avancado | branding e politicas administrativas adicionais |
| users | operacional MVP | politicas enterprise |
| auth | operacional MVP | recovery codes e gates adicionais por email verificado |
| sync | avançado local; não fechado | ownership/idempotência verdes localmente; faltam E2E, staging e Android no RC |

## Ordem de Fechamento

1. C0-C4: convergência Driver/Sync, branches, contratos e certificação Issue #42.
2. Cliente <-> Terceiro por `widen-migrate-narrow`.
3. E0: fronteira SaaS e administração comercial.
4. E1: Procure-to-Pay e inventário unificado.
5. E2: Order-to-Cash, Oficina e fecho financeiro.
6. E3: Pessoas, payroll e ativos.
7. E4: Trusted BI.
8. E5: piloto e promoção comercial.
