# Transporte e Carga - Closure Checklist

Estado: fechado MVP
Data: 2026-06-04

## Responsabilidade

O modulo Transporte e Carga cobre o ciclo operacional desde a intencao de transporte ate a entrega e fecho operacional:

- ordem de transporte;
- planeamento e atribuicao de viatura/motorista;
- autorizacao de saida;
- execucao da viagem;
- eventos e incidentes;
- documentos de carga;
- Load Permit;
- manifesto/guia;
- prova de descarga;
- disputa documental;
- fecho operacional.

## Fontes de Verdade

| Area | Fonte |
| --- | --- |
| Intencao/planeamento | `trip_orders` |
| Viagem executavel | `trips` |
| Autorizacao de saida | `dispatch_clearances` |
| Linha temporal | `trip_execution_events` |
| Incidentes | `trip_incidents` |
| Paragens/custos pontuais | `trip_stops`, `trip_costs` |
| Documentos de carga | `load_permits`, `cargo_manifests`, `transport_documents` |
| Prova de descarga | `delivery_proofs` |
| Excepcoes controladas | `operational_waivers`, `operational_exceptions` |
| Auditoria | `audit_logs` |

## Estados Criticos

- `trip_orders`: `draft`, `confirmed`, `planning`, `assigned`, `dispatch_pending`, `dispatched`, `in_execution`, `delivered`, `closed`, `cancelled`.
- `trips`: `draft`, `planned`, `dispatch_pending`, `dispatched`, `in_progress`, `delayed`, `incident`, `arrived`, `delivered`, `delivery_disputed`, `closed`.
- `dispatch_clearances`: `pending`, `blocked`, `approved`.
- `delivery_proofs`: `pending`, `validated`, `disputed`, `rejected`.
- `trip_incidents`: `open`, `investigating`, `resolved`, `closed`.

## Definition of Done do Modulo

- [x] Tenant isolation aplicada no service layer.
- [x] Criacao de ordem, confirmacao, atribuicao e cancelamento.
- [x] Atribuicao valida disponibilidade de viatura e motorista.
- [x] Atribuicao cria viagem vinculada de forma transaccional.
- [x] Criacao trip-first suportada para MVP.
- [x] Mutacoes directas de viagem escrevem audit log.
- [x] Idempotencia HTTP cobre criacao, transicoes criticas, incidentes, stops e fecho.
- [x] Autorizacao de saida exige aprovacao interna.
- [x] Load Permit obrigatorio bloqueia autorizacao de saida quando ausente.
- [x] Incidentes criam evento de execucao e podem bloquear estado da viagem.
- [x] Avaria em viagem cria pedido de manutencao.
- [x] Prova de descarga actualiza estado operacional e billing readiness.
- [x] Disputa documental bloqueia validacao e cobranca.
- [x] Resolucao de disputa fecha exception/alerta ligado.
- [x] Fecho operacional exige POD validado ou waiver `no_pod`.
- [x] Fecho operacional bloqueia incidentes high/critical abertos.
- [x] Fecho operacional reconcilia custos e margem.
- [x] Control Tower consome filas do modulo.
- [x] Manager tem board dedicado para Transporte e Carga com ordens, autorizacao de saida, execucao, incidentes, checklists falhados, descargas pendentes e disputas.
- [x] Board dedicado executa accoes directas para validar descarga, resolver disputa documental e resolver checklist falhado.
- [x] Board dedicado executa accoes directas para aprovar/reavaliar saida, iniciar saida operacional, resolver incidente e fechar operacionalmente viagens prontas.
- [x] Avaliacao explicita de SLA de entrega marca viagens atrasadas, cria evento operacional e gera exception/alerta idempotente.
- [x] Control Tower e board dedicado expõem fila de atrasos SLA.
- [x] Politica documental por tipo de carga bloqueia autorizacao de saida quando faltam Load Permit, manifesto ou documento de transporte configurado no tenant.
- [x] Politica de paragens obrigatorias por tipo de carga bloqueia fecho operacional quando stops requeridos nao foram registados.
- [x] Concorrencia ampliada para atribuicao/saida impede duplicacao de viagem activa e evento de saida.
- [x] Auditoria granular dos documentos auxiliares de carga captura campos operacionais completos.
- [x] Testes cobrem happy path, conflitos, replay e regressao operacional.

## Lacunas Restantes

- Nenhuma lacuna funcional MVP aberta.

## Proxima Fatia Recomendada

Avancar para o proximo modulo de produto na sequencia de fechamento.
