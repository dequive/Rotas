# ROTAS Module Closure Matrix

Estado: activo
Data: 2026-08-22

## Override de auditoria — Issue #42

Esta secção substitui qualquer classificação mais otimista existente abaixo
até nova auditoria no SHA integrado. Ver
`docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md`.

| Área | Estado vinculativo | Razão bloqueante |
| --- | --- | --- |
| Frota e Pessoas | avançado local; não fechado | pairing concorrente e Driver com acesso à frota geral |
| Transporte e Carga | regredido / P0 | Driver cria viagens e documentos; linha Android não convergiu |
| Sync/Offline | regredido / P0 | falta ownership intra-tenant e isolamento de idempotência por motorista/dispositivo |
| Contratos API Driver | parcial / P1 | seis sucessos Driver/Sync mantêm schema OpenAPI vazio |
| Segurança multi-tenant | forte entre tenants; incompleta intra-tenant | RLS não substitui ownership entre motoristas do mesmo tenant |
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
| Frota e Pessoas | vehicles, drivers, availability | avançado local; não fechado | pairing concorrente e exposição de frota geral ao Driver; falta prova intra-tenant por motorista/dispositivo |
| Transporte e Carga | trip_orders, trips, checklists, cargo, operations | regredido / P0 | Driver cria viagens/documentos e a jornada atribuída/documental Android não convergiu |
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
| drivers | parcial / P1 | pairing concorrente, contratos Driver e jornada atribuída por convergir |
| files | operacional MVP | storage adapter R2 |
| checklists | avancado | politicas adicionais e visual hardening |
| trip_orders | fechado MVP | evolucoes enterprise futuras |
| trips | parcial / P0 | proibir criação/edição pelo Driver sem assignment/ownership |
| cargo | parcial / P0 | separar emissão de gestor, pedido do Driver e bloqueio após fecho |
| billing | avancado | reconciliacao final e politicas adicionais |
| fuel | operacional MVP | politicas adicionais |
| workshop | operacional MVP | ampliar board visual e politicas enterprise |
| operational_exceptions | avancado | politicas adicionais e integracao final |
| control_tower | avancado | dashboard executivo TMS adicionado; faltam QA visual final e configuracao de filas por tenant |
| alerts | operacional MVP | escalonamento externo por canal |
| tenants | avancado | branding e politicas administrativas adicionais |
| users | operacional MVP | politicas enterprise |
| auth | operacional MVP | recovery codes e gates adicionais por email verificado |
| sync | regredido / P0 | ownership intra-tenant e idempotência por motorista/dispositivo incompletos |

## Ordem de Fechamento

1. C0-C4: convergência Driver/Sync, branches, contratos e certificação Issue #42.
2. Cliente <-> Terceiro por `widen-migrate-narrow`.
3. E0: fronteira SaaS e administração comercial.
4. E1: Procure-to-Pay e inventário unificado.
5. E2: Order-to-Cash, Oficina e fecho financeiro.
6. E3: Pessoas, payroll e ativos.
7. E4: Trusted BI.
8. E5: piloto e promoção comercial.
