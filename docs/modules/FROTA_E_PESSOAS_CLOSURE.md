# Frota e Pessoas - Closure Checklist

Estado: fechado MVP
Data: 2026-06-04

## Responsabilidade

O modulo Frota e Pessoas cobre os activos humanos e materiais usados na operacao:

- cadastro de viaturas;
- cadastro de motoristas;
- documentos e compliance;
- disponibilidade operacional;
- bloqueios por viagem activa, oficina e documentos;
- waivers operacionais auditados;
- historicos detalhados e separados por viatura e motorista.

## Fontes de Verdade

| Area | Fonte |
| --- | --- |
| Viaturas | `vehicles` |
| Motoristas | `drivers` |
| Documentos | `vehicles.documents`, `drivers.documents` |
| Validade de motorista | `drivers.license_valid_until`, `drivers.inatter_valid_until` |
| Viagens activas | `trips` |
| Oficina bloqueante | `work_orders` |
| Checklists | `checklists` |
| Combustivel | `fuel_logs`, `vehicle_refuels` |
| Excepcoes controladas | `operational_waivers` |
| Auditoria | `audit_logs` |

## Estados Criticos

- `vehicles`: `active`, `maintenance`, `retired`, outros estados administrativos definidos por tenant.
- `drivers`: `active`, `inactive`, `suspended`.
- `trips`: estados activos bloqueiam atribuicao: `planned`, `dispatch_pending`, `dispatched`, `in_progress`, `delayed`, `incident`.
- `work_orders`: estados bloqueantes: `approved`, `in_progress`, `quality_check`.
- `operational_waivers`: `active`, `revoked`.

## Definition of Done do Modulo

- [x] Tenant isolation aplicada no service layer.
- [x] CRUD de viaturas com limite por plano, duplicacao por matricula e auditoria.
- [x] CRUD de motoristas com limite por plano, duplicacao por telefone e auditoria.
- [x] QR/deep link de viatura emitido com auditoria.
- [x] Documentos de viatura renovam validade, associam ficheiro e auditam.
- [x] Documentos de motorista renovam validade, associam ficheiro e auditam.
- [x] Disponibilidade centralizada bloqueia viatura por estado, compliance, oficina e viagem activa.
- [x] Disponibilidade centralizada bloqueia motorista por estado, compliance e viagem activa.
- [x] Waivers activos permitem excepcao controlada para documentos em falta/expirados.
- [x] Torre de Controlo expoe filas preventivas de documentos a expirar.
- [x] Historico de viatura e motorista sao separados, detalhados e cruzam apenas referencias relacionadas.
- [x] API dedicada de disponibilidade explica bloqueios, avisos e waivers activos.
- [x] Manager apresenta historicos separados com fallback demo e API real.
- [x] Manager tem board dedicado de compliance documental com renovacao directa de documentos de viatura e motorista.
- [x] Testes cobrem CRUD, conflitos, compliance, waivers, renovacao documental, historicos e disponibilidade detalhada.

## Lacunas Restantes

- Nenhuma lacuna funcional MVP aberta.
- Evolucoes enterprise futuras: categorias de carta por tipo de viatura/carga, escalas de motorista, fadiga e indisponibilidade programada.

## Proxima Fatia Recomendada

Avancar para o proximo modulo de produto na sequencia de fechamento.
