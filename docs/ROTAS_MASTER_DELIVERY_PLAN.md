# ROTAS Master Delivery Plan

Versao: 0.1
Data: 2026-05-31
Estado: documento vivo de planeamento e execucao

## 1. Objectivo

O ROTAS deve ser materializado como um sistema de gestao de operacoes na area de transportes, nao apenas como um registo de viagens.

A plataforma deve integrar, de forma coesa:

- operacoes de transporte;
- frota e disponibilidade;
- documentos de carga;
- prova de entrega;
- combustivel;
- oficina e manutencao;
- pecas e ferramentas;
- custos reais;
- cobranca;
- auditoria;
- excepcoes operacionais;
- torre de controlo.

O principio de desenho e simples:

```text
ordem -> planeamento -> autorizacao de saida -> execucao -> entrega -> fecho operacional -> cobranca
      -> combustivel -> manutencao -> custos reais -> margem
```

Nota de linguagem local: para os motoristas, `despacho` significa o subsidio de viagem de longo curso, calculado pela distancia. A etapa operacional de liberar uma viagem para sair deve aparecer no produto como `autorizacao de saida`.

Nenhum dominio deve existir como submenu isolado. Tudo que afecta disponibilidade, custo, margem, risco ou cobranca deve alimentar a torre de controlo.

## 2. Visao do Produto

O ROTAS deve responder diariamente a estas perguntas:

- Que operacoes temos hoje?
- Que viagens estao em risco?
- Que viaturas estao disponiveis, paradas, em rota ou em oficina?
- Que motorista esta alocado a cada operacao?
- Que documentos faltam para carregar, descarregar ou cobrar?
- Quanto combustivel temos, quanto saiu e para que viagem?
- Que manutencoes estao abertas, vencidas ou a bloquear viaturas?
- Que custos reais ja afectaram a margem da viagem?
- Que entregas ja podem ser cobradas?
- Quem autorizou cada decisao critica?

## 3. Modulos de Produto por Responsabilidade

Esta e a taxonomia de produto usada para fechar a aplicacao. Os pacotes tecnicos do backend podem continuar mais granulares, mas o utilizador e a gestao do produto devem pensar nestes modulos.

| Modulo | Responsabilidade principal |
| --- | --- |
| Centro de Comando | Torre de Controlo, alertas, excepcoes operacionais e priorizacao diaria. |
| Frota e Pessoas | Viaturas, motoristas, disponibilidade, compliance documental e historicos separados. |
| Transporte e Carga | Ordem, viagem, autorizacao de saida, execucao, checklists, incidentes, documentos de carga, Load Permit, prova de descarga e disputas. |
| Custos e Margem | Custos reais da viagem, despacho do motorista, reconciliacao, margem e risco financeiro operacional. |
| Combustivel | Compra, recepcao, stock por movimentos, abastecimentos, contagens, ajustes e desvios. |
| Oficina e Manutencao | Pedidos, ordens de servico, tarefas, pecas, ferramentas e preventiva. |
| Cobranca | Contratos, viagens billable, documentos de cobranca e exportacoes. |
| Administracao Operacional | Tenants, utilizadores, politicas, configuracoes e responsabilidades. |
| Suporte Tecnico-Operacional | Ficheiros, sync offline, auditoria, autenticacao e integracoes tecnicas. |

Os sete primeiros sao os modulos principais apresentados ao cliente. Administracao Operacional e Suporte Tecnico-Operacional sao a base de governanca e operacao do sistema.

## 4. Dominios Integrados

### 4.1 Transporte e Carga

Responsabilidade:

- receber/intencionar ordens de transporte;
- planear viagem;
- atribuir viatura e motorista;
- controlar autorizacao de saida;
- acompanhar execucao;
- registar incidentes;
- rastrear documentos emitidos pelo cliente;
- controlar Load Permit;
- controlar manifesto de carga quando aplicavel;
- controlar guia/documento de transporte;
- receber prova de entrega;
- gerir disputas documentais;
- fechar operacionalmente a viagem.

Entidades principais:

- `trip_orders`;
- `trips`;
- `dispatch_clearances`;
- `trip_execution_events`;
- `trip_incidents`;
- `cargo_documents`;
- `delivery_proofs`;
- `operational_waivers`.

Regras principais:

- Load Permit e emitido pelo cliente, nao pelo ROTAS.
- ROTAS rastreia numero, ficheiro, validade operacional e relacao com viagem.
- Manifesto de carga pode ser emitido pelo transportador para produtos manufaturados.
- Para cliente empresa, prova preferencial e guia carimbada/assinada ou documento de descarga.
- Para cliente individual, pode haver prova alternativa com foto, GPS, assinatura/codigo ou waiver.

### 4.2 Frota e Pessoas

Responsabilidade:

- manter cadastro de viaturas;
- controlar documentos e compliance;
- expor disponibilidade calculada;
- bloquear viatura por manutencao, documentos, viagem activa ou waiver;
- manter historico operacional.

Entidades principais:

- `vehicles`;
- documentos da viatura;
- estado operacional;
- vinculos com trips, checklists, fuel e work orders.

### 4.3 Combustivel

Responsabilidade:

- controlar compra de combustivel;
- controlar recepcao fisica;
- controlar tanque;
- controlar movimentos;
- abastecer viaturas;
- reconciliar stock fisico e teorico;
- calcular custo real por viagem;
- detectar desvios.

Entidades principais:

- `fuel_tanks`;
- `fuel_purchases`;
- `fuel_receipts`;
- `fuel_movements`;
- `vehicle_refuels`;
- `fuel_stock_counts`.

Regra fundamental:

```text
Stock de combustivel nao e actualizado directamente.
Toda entrada ou saida deve passar por fuel_movements.
```

### 4.4 Oficina e Manutencao

Responsabilidade:

- receber pedidos de manutencao;
- diagnosticar;
- criar ordens de servico;
- gerir tarefas;
- atribuir mecanicos;
- consumir pecas por movimento;
- controlar ferramentas por checkout;
- bloquear/libertar viaturas;
- calcular custo real de manutencao.

Entidades principais:

- `maintenance_requests`;
- `work_orders`;
- `work_order_tasks`;
- `maintenance_parts_used`;
- `spare_parts_inventory`;
- `spare_part_movements`;
- `workshop_tools`;
- `tool_checkouts`;
- `maintenance_plans`;
- `maintenance_schedule`.

Regra fundamental:

```text
Work order activa torna a viatura indisponivel para nova viagem,
salvo waiver operacional aprovado e auditado.
```

### 4.5 Custos, Margem e Cobranca

Responsabilidade:

- calcular custo estimado;
- receber custos reais;
- aplicar tabela de despacho do transportador quando existir;
- reconciliar margem;
- preparar cobranca;
- impedir cobranca indevida;
- exportar documentos profissionais.

Entidades principais:

- `contracts`;
- `billing_items`;
- `billing_documents`;
- `trip_cost_estimates`;
- `trip_cost_actuals`.

Regra fundamental:

```text
Cobranca segue a data de descarga validada, nao a data de partida.
```

Regra de despacho do motorista:

```text
Se o transportador tiver tabela de despacho, o subsidio de longo curso e calculado pela faixa de distancia dessa tabela.
A tabela de despacho e preenchida manualmente pela Administracao Operacional do transportador.
Se a distancia nao atingir o minimo de longo curso ou nao casar com nenhuma faixa, o sistema nao deve gerar custo de despacho.
O custo gerado entra em trip_costs como driver_despacho e afecta a margem real da viagem.
```

### 4.6 Centro de Comando

Responsabilidade:

- consolidar estado operacional;
- expor excepcoes;
- priorizar riscos;
- mostrar KPIs de transporte, frota, combustivel, oficina e financeiro.

Entidades principais:

- `operational_exceptions`;
- `audit_logs`;
- views ou services agregadores;
- boards por dominio.

## 5. Fluxos Principais

### 5.1 Fluxo completo de transporte

```text
trip_order criada
  -> trip_order confirmada
  -> viatura e motorista atribuidos
  -> trip criada
  -> autorizacao de saida pendente
  -> documentos verificados
  -> autorizacao de saida aprovada
  -> viagem em execucao
  -> eventos e incidentes registados
  -> descarga/prova de entrega submetida
  -> prova validada
  -> custos reconciliados
  -> fecho operacional
  -> candidata a cobranca
  -> documento de cobranca emitido
```

### 5.2 Fluxo trip-first do MVP

Este fluxo continua valido para clientes informais ou em fase de transicao:

```text
trip criada directamente
  -> contract_id opcional
  -> documentos de carga anexados quando existirem
  -> descarga validada
  -> se contrato existir, gera billing item
  -> se contrato faltar, entra em fila uncontracted
```

### 5.3 Fluxo contract/order-first

Este fluxo sera o principal para clientes mais maduros:

```text
contrato
  -> ordem de transporte
  -> Load Permit recebido do cliente
  -> atribuicao de viatura/motorista
  -> autorizacao de saida
  -> execucao
  -> descarga
  -> cobranca mensal
```

### 5.4 Fluxo de combustivel

```text
fuel_purchase
  -> aprovacao
  -> fuel_receipt
  -> verificacao
  -> fuel_movement purchase_receipt
  -> stock do tanque actualizado
  -> vehicle_refuel
  -> fuel_movement vehicle_refuel
  -> custo associado a trip
  -> exception se houver desvio
```

### 5.5 Fluxo de oficina

```text
maintenance_request
  -> triagem
  -> work_order
  -> aprovacao
  -> tarefas
  -> issue de pecas
  -> checkout de ferramentas
  -> execucao
  -> quality_check
  -> fecho
  -> viatura libertada
  -> custo real associado a viatura/trip quando aplicavel
```

### 5.6 Fluxo de avaria em viagem

```text
trip_incident breakdown
  -> maintenance_request automatica
  -> work_order
  -> vehicle status maintenance/blocked
  -> custos reais de manutencao
  -> trip_cost_actuals
  -> margem real recalculada
```

## 6. Regras Transversais de Consistencia

### 6.1 Disponibilidade

Disponibilidade nao deve ser apenas um campo editavel. Deve ser calculada a partir de:

- viagem activa;
- dispatch pendente;
- work order activa;
- manutencao vencida;
- documento expirado;
- bloqueio manual;
- waiver activo.

### 6.2 Stock

Stock de combustivel, pecas e ferramentas deve seguir fontes de verdade diferentes:

- combustivel: movimentos em `fuel_movements`;
- pecas: movimentos em `spare_part_movements`;
- ferramentas: estado e checkouts em `tool_checkouts`.

### 6.3 Cobranca

- Viagem nao deve ser cobrada sem contrato associado.
- Viagem nao deve ser cobrada sem prova de descarga validada, salvo waiver `no_pod`.
- Periodo de cobranca e derivado de `delivered_at`.
- Draft de documento de cobranca nao marca viagem como cobrada.
- Apenas emissao/finalizacao marca item como cobrado.

### 6.4 Auditoria

Toda mutacao critica deve registar:

- actor;
- tenant;
- entidade;
- estado anterior;
- estado novo;
- motivo quando aplicavel;
- request/correlation id quando existir;
- timestamp.

### 6.5 Excepcoes

O sistema deve gerir por excepcoes, nao por relatorios passivos. Quando uma regra critica falhar, deve nascer uma `operational_exception`.

Exemplos:

- motorista sem disponibilidade;
- viatura com documento expirado;
- falta de Load Permit obrigatorio;
- atraso de carga ou descarga;
- POD em falta;
- combustivel acima do esperado;
- stock abaixo do minimo;
- work order atrasada;
- ferramenta por devolver.

## 7. Boards Operacionais

### 7.1 Transport Control Tower

Indicadores:

- ordens abertas;
- ordens em risco;
- viagens em execucao;
- viagens atrasadas;
- incidentes abertos;
- entregas pendentes de validacao;
- candidatas a cobranca;
- pendencias contratuais.

Colunas:

- abertas;
- planeamento;
- atribuidas;
- autorizacao de saida;
- em rota;
- com incidente;
- entregues;
- a fechar.

### 7.2 Fuel Control Board

Indicadores:

- stock actual por tanque;
- dias estimados de autonomia;
- compras pendentes;
- recepcoes pendentes;
- litros abastecidos hoje;
- consumo por viatura;
- consumo por motorista;
- abastecimentos sem viagem;
- desvios de stock.

Colunas:

- compras;
- recepcao;
- em stock;
- abastecimentos;
- disputas;
- ajustes.

### 7.3 Workshop Control Board

Indicadores:

- viaturas em oficina;
- ordens de servico abertas;
- manutencoes vencidas;
- manutencoes proximas;
- pecas abaixo do minimo;
- ferramentas em atraso;
- custo de manutencao do mes;
- viaturas aguardando quality check.

Colunas:

- pedidos;
- diagnostico;
- aprovadas;
- em execucao;
- aguardam pecas;
- aguardam ferramentas;
- controlo de qualidade;
- concluidas;
- fechadas.

### 7.4 Billing Control Board

Indicadores:

- entregas validadas nao cobradas;
- viagens sem contrato;
- documentos de cobranca em draft;
- documentos emitidos no periodo;
- valor por cliente;
- valor pendente;
- viagens com POD no mes seguinte.

## 8. Perfis e Permissoes

Perfis minimos:

- Tenant Admin;
- Operations Director;
- Fleet Manager;
- Dispatcher;
- Driver;
- Fuel Manager;
- Fuel Attendant;
- Workshop Manager;
- Maintenance Supervisor;
- Mechanic;
- Parts Storekeeper;
- Tool Custodian;
- Finance Officer;
- Auditor.

Segregacoes obrigatorias:

- Quem abastece nao aprova ajuste de stock.
- Quem usa peca nao deve controlar sozinho o inventario.
- Quem executa manutencao nao deve sempre libertar viatura sem validacao.
- Finance Officer reconcilia e cobra, mas nao altera execucao operacional.
- Auditor le, mas nao altera.

## 9. Roadmap Integrado

### Wave 0 - Base ja implementada

Estado actual:

- backend modular;
- contratos;
- trips/cargo;
- Load Permit;
- manifesto;
- prova de descarga;
- cobranca por data de descarga;
- PDF/XLSX de cobranca;
- viaturas e motoristas;
- checklists;
- fuel logs simples;
- sync offline;
- PWA motorista para checklist/combustivel;
- dashboard gestor de cobranca.

### Wave 1 - Transport Operations Foundation

Objectivo:

Criar a espinha dorsal operacional.

Entregaveis:

- `trip_orders`;
- alteracao em `trips` para `trip_order_id`;
- indices parciais contra conflito de viatura/motorista;
- `TripOrderService`;
- confirmacao;
- atribuicao transaccional;
- criacao de trip a partir da ordem;
- testes de concorrencia.

Aceite quando:

- uma ordem pode ser criada, confirmada e atribuida;
- atribuicao cria trip vinculada;
- a mesma viatura nao pode ser atribuida a duas operacoes activas;
- o mesmo motorista nao pode ser atribuido a duas operacoes activas;
- toda atribuicao critica gera auditoria ou ponto de auditoria preparado.

### Wave 2 - Autorizacao de Saida, Execution, POD and Incidents

Objectivo:

Controlar a saida e execucao da viagem.

Entregaveis:

- `dispatch_clearances`;
- `trip_execution_events`;
- `trip_incidents`;
- harmonizacao de `delivery_proofs` com POD operacional;
- endpoint de saida operacional;
- endpoint de eventos;
- endpoint de incidentes;
- regras de fecho operacional.

Aceite quando:

- viagem nao passa a dispatched sem autorizacao de saida aprovada;
- incidente pode bloquear fecho;
- POD validado permite billing readiness;
- viagem entregue ainda pode ficar pendente de fecho operacional.

### Wave 3 - Fuel Operations MVP

Objectivo:

Substituir o fuel log simples por controlo operacional de combustivel.

Entregaveis:

- `fuel_tanks`;
- `fuel_purchases`;
- `fuel_receipts`;
- `fuel_movements`;
- `vehicle_refuels`;
- `fuel_stock_counts`;
- `FuelMovementService`;
- Fuel Control Board basico;
- excepcoes de combustivel.

Aceite quando:

- compra nao aumenta stock sem recepcao verificada;
- movimento actualiza stock atomicamente;
- abastecimento sem stock suficiente falha;
- abastecimento pode ser ligado a trip;
- variancia relevante gera exception.

### Wave 4 - Workshop Operations MVP

Objectivo:

Controlar manutencao e disponibilidade de frota.

Entregaveis:

- `maintenance_requests`;
- `work_orders`;
- `work_order_tasks`;
- estados de bloqueio/libertacao;
- ligacao com vehicle availability;
- Workshop Control Board basico.

Aceite quando:

- work order activa torna viatura indisponivel;
- work order fechada pode libertar viatura com permissao;
- avaria em viagem pode criar maintenance request;
- custo de manutencao pode alimentar trip cost actuals.

### Wave 5 - Parts, Tools and Preventive Maintenance

Objectivo:

Controlar recursos da oficina.

Entregaveis:

- `spare_parts_inventory`;
- `spare_part_movements`;
- `maintenance_parts_used`;
- `workshop_tools`;
- `tool_checkouts`;
- `tool_maintenance_records`;
- `maintenance_plans`;
- `maintenance_schedule`.

Aceite quando:

- peca nao sai sem stock suficiente;
- stock de peca muda apenas por movimento;
- ferramenta checked out nao pode ser levantada de novo;
- ferramenta vencida/danificada pode bloquear checkout;
- manutencao vencida gera exception.

### Wave 6 - Operational Exceptions, Waivers and Audit

Objectivo:

Endurecer governanca operacional.

Entregaveis:

- `operational_exceptions`;
- `operational_waivers`;
- `audit_logs` funcional;
- servico de auditoria;
- politicas de waiver;
- endpoints de acknowledge/resolve.

Aceite quando:

- mutacoes criticas geram audit log;
- exceptions aparecem nos boards;
- waiver pode permitir excepcao sem apagar risco;
- auditor consegue reconstruir decisoes.

### Wave 7 - Unified Control Tower

Objectivo:

Unificar operacao, frota, combustivel, oficina, custos e cobranca.

Entregaveis:

- endpoint `GET /api/v1/control-tower`;
- cards de KPIs;
- filas de risco;
- boards integrados;
- filtros por data, cliente, viatura, motorista e estado.

Aceite quando:

- gestor consegue ver o dia operacional numa tela;
- riscos aparecem antes de relatorios detalhados;
- cada alerta liga para a entidade origem.

### Wave 8 - Production Hardening

Objectivo:

Preparar piloto real e evolucao enterprise.

Entregaveis:

- auth/JWT completo;
- RBAC real;
- Cloudflare R2;
- WhatsApp Cloud API;
- logs estruturados;
- backup;
- health checks;
- testes de carga;
- estrategia expand/contract de migracoes.

## 10. Dependencias de Implementacao

Ordem recomendada:

```text
Audit base
  -> Trip Orders
  -> Availability
  -> Dispatch
  -> Execution Events
  -> Exceptions
  -> Fuel Movements
  -> Workshop Blocking
  -> Cost Actuals
  -> Control Tower
```

Risco se inverter:

- construir fuel sem movements cria divida contabilistica;
- construir workshop sem availability cria incoerencia operacional;
- construir frontend antes de services estaveis cria retrabalho;
- construir WhatsApp antes de exceptions internas cria notificacoes sem regra forte.

## 11. Testes Obrigatorios por Dominio

### Transport

- motorista nao pode ter duas viagens activas;
- viatura nao pode ter duas viagens activas;
- ordem so gera trip via atribuicao confirmada;
- autorizacao de saida bloqueia sem aprovacao;
- viagem nao fecha sem POD ou waiver.

### Fuel

- combustivel nao sai sem stock suficiente;
- dois abastecimentos simultaneos do mesmo tanque mantem stock correcto;
- recepcao verificada gera movement;
- ajuste sem permissao falha;
- odometro regressivo gera exception.

### Workshop

- work order activa bloqueia viatura;
- work order fechada liberta apenas com permissao;
- peca nao sai sem stock;
- ferramenta checked out nao pode ser levantada de novo;
- manutencao vencida gera exception.

### Billing

- billing period vem de `delivered_at`;
- draft nao marca billed;
- issue marca billed;
- viagem sem contrato fica `uncontracted`;
- waiver `no_pod` e auditavel.

### Audit

- toda mutacao critica tem evento;
- evento contem actor, tenant, entidade, before/after e timestamp;
- operacao rejeitada nao altera estado.

## 12. Criterios de MVP Aceite

O MVP operacional e aceite quando:

1. Gestor consegue abrir Control Tower diario.
2. Ordem pode ser criada, confirmada, atribuida e convertida em trip.
3. Sistema bloqueia viatura/motorista duplicados em operacao activa.
4. Autorizacao de saida exige aprovacao.
5. Execucao aceita eventos e incidentes.
6. Entrega exige POD validado ou waiver.
7. Billing respeita data de descarga.
8. Combustivel e controlado por movimentos.
9. Abastecimento pode alimentar custo real da trip.
10. Oficina bloqueia viatura por work order activa.
11. Pecas e ferramentas sao controladas por movimento/checkout.
12. Excepcoes aparecem nos boards.
13. Mutacoes criticas deixam auditoria.

## 13. Fora do MVP

Nao implementar agora:

- GPS em tempo real;
- IoT em tanques;
- bombas electronicas integradas;
- CAN bus;
- optimizacao automatica de rotas;
- manutencao preditiva;
- machine learning de consumo;
- QR/RFID obrigatorio para ferramentas;
- app mobile completa de mecanico;
- aprovacao multi-nivel complexa;
- facturacao fiscal avancada;
- multi-stop complexo N:M.

## 14. Principio de Execucao

Cada nova funcionalidade deve responder antes de ser implementada:

- Que dominio owns esta regra?
- Que entidade e fonte de verdade?
- Que estado altera?
- Que disponibilidade afecta?
- Que custo afecta?
- Que exception pode gerar?
- Que audit log deve deixar?
- Que teste prova a regra?
- Que tela ou board consome o resultado?

Se uma funcionalidade nao responder a estas perguntas, ainda nao esta pronta para entrar no roadmap.
