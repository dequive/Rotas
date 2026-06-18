# ROTAS Module Closure Matrix

Estado: activo
Data: 2026-06-17

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
| Frota e Pessoas | vehicles, drivers, availability | fechado MVP | disponibilidade detalhada, compliance documental, waivers, historicos separados, filas preventivas e renovacao no Manager cobertos |
| Transporte e Carga | trip_orders, trips, checklists, cargo, operations | fechado MVP | board dedicado, SLA, politicas documentais, paragens obrigatorias, concorrencia critica e auditoria granular cobertos |
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
| drivers | fechado MVP | evolucoes enterprise futuras |
| files | operacional MVP | storage adapter R2 |
| checklists | avancado | politicas adicionais e visual hardening |
| trip_orders | fechado MVP | evolucoes enterprise futuras |
| trips | fechado MVP | evolucoes enterprise futuras |
| cargo | fechado MVP | evolucoes enterprise futuras |
| billing | avancado | reconciliacao final e politicas adicionais |
| fuel | operacional MVP | politicas adicionais |
| workshop | operacional MVP | ampliar board visual e politicas enterprise |
| operational_exceptions | avancado | politicas adicionais e integracao final |
| control_tower | avancado | dashboard executivo TMS adicionado; faltam QA visual final e configuracao de filas por tenant |
| alerts | operacional MVP | escalonamento externo por canal |
| tenants | avancado | branding e politicas administrativas adicionais |
| users | operacional MVP | politicas enterprise |
| auth | operacional MVP | recovery codes e gates adicionais por email verificado |
| sync | operacional | ampliar tipos suportados |

## Ordem de Fechamento

1. Workshop: pecas, ferramentas, preventiva e custos.
2. Custos reais e margem por viagem.
3. Idempotencia HTTP reutilizavel e adopcao por mutacoes criticas.
4. Users, tenants, auth JWT e RBAC real.
5. Alerts e Control Tower unificados.
6. Compliance documental, waivers, Storage R2, observabilidade, testes de carga e hardening de piloto.
