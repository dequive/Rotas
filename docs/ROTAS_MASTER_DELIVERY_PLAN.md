# ROTAS Master Delivery Plan

Versao: 0.6
Data: 2026-07-26
Estado: documento vivo de planeamento e execucao

## 1. Objectivo

O ROTAS deve ser materializado como um ERP e TMS SaaS multi-tenant para empresas
de transporte, logistica e oficinas, nao apenas como um registo de viagens.

Cada tenant representa um cliente empresarial independente do ROTAS e gere os
seus proprios clientes, fornecedores, colaboradores, operacoes, activos,
stocks, documentos e contabilidade. O operador SaaS governa a plataforma, os
planos e as subscricoes, mas nao se torna owner dos dados operacionais do
tenant.

A plataforma deve integrar, de forma coesa:

- operacoes de transporte;
- frota e disponibilidade;
- documentos de carga;
- prova de entrega;
- combustivel;
- oficina e manutencao;
- pecas e ferramentas;
- custos reais;
- compras, vendas, facturacao, cobranca e tesouraria;
- contabilidade e centros de custo;
- recursos humanos e processamento salarial;
- inventario, armazens e activos;
- Business Intelligence, KPIs e alertas;
- auditoria;
- excepcoes operacionais;
- torre de controlo.

O principio de desenho e simples:

```text
ordem -> planeamento -> autorizacao de saida -> execucao -> entrega -> fecho operacional -> cobranca
      -> combustivel -> manutencao -> custos reais -> margem
requisicao -> compra -> recepcao -> stock/activo -> factura fornecedor -> pagamento -> contabilidade
proposta/contrato -> servico -> factura cliente -> recebimento -> contabilidade
eventos de negocio -> read models tenant-scoped -> KPIs -> alertas -> decisao
```

Nota de linguagem local: para os motoristas, `despacho` significa o subsidio de viagem de longo curso, calculado pela distancia. A etapa operacional de liberar uma viagem para sair deve aparecer no produto como `autorizacao de saida`.

Nenhum dominio deve existir como submenu isolado. Tudo que afecta disponibilidade, custo, margem, risco ou cobranca deve alimentar a torre de controlo.

## 2. Visao do Produto

Definicao vinculativa do produto:

> ROTAS e um ERP e TMS SaaS multi-tenant no qual cada tenant administra de
> forma autonoma os seus proprios clientes e a sua operacao, com isolamento
> rigoroso de dados e governanca central da plataforma.

A hierarquia de ownership e:

```text
Operador ROTAS SaaS
  -> tenant
     -> entidade legal
        -> filial/centro operacional
           -> centro de custo, armazem, oficina e equipa
     -> clientes do tenant
     -> fornecedores do tenant
```

Um tenant pode ter uma ou mais entidades legais. Filiais nunca substituem o
limite de tenant. Partilha entre entidades legais do mesmo tenant exige regra
explicita; partilha entre tenants e proibida por defeito.

Existem dois ciclos comerciais e financeiros separados:

1. `ROTAS -> tenant`: plano, subscricao, entitlements, limites e cobranca SaaS.
2. `tenant -> cliente do tenant`: contratos, servicos, vendas, facturas,
   cobrancas e recebimentos operacionais.

Modelos, APIs, permissoes, relatorios e lancamentos nunca devem misturar estes
dois ciclos.

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
| Clientes, Vendas e Cobranca | CRM operacional, propostas, contratos, pedidos, viagens/servicos billable, facturas, cobrancas e recebimentos. |
| Compras e Fornecedores | Requisicoes, cotacoes, aprovacoes, ordens de compra, recepcoes, facturas e pagamentos. |
| Inventario e Activos | Artigos, armazens, movimentos, lotes/seriais, contagens, valorizacao, activos, transferencias e abates. |
| Financas e Contabilidade | Plano de contas, diarios, AP/AR, tesouraria, reconciliacao, centros de custo, periodos e demonstracoes. |
| Recursos Humanos | Colaboradores, documentos, assiduidade, ausencias, payroll, adiantamentos e desligamento. |
| Business Intelligence | Camada semantica de KPIs, dashboards, tendencias, drill-down, metas e alertas. |
| Administracao do Tenant | Entidades legais, filiais, utilizadores, politicas, sequencias, configuracoes e responsabilidades. |
| Administracao SaaS | Provisionamento de tenants, planos, subscricoes, entitlements, limites, suporte autorizado e saude da plataforma. |
| Suporte Tecnico-Operacional | Ficheiros, sync offline, auditoria, autenticacao e integracoes tecnicas. |

Os modulos de negocio sao apresentados ao tenant conforme o plano contratado e
os entitlements definidos pelo operador SaaS. Administracao do Tenant,
Administracao SaaS e Suporte Tecnico-Operacional formam a base de governanca,
isolamento e operacao do sistema.

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

### 4.7 Plataforma SaaS e Administracao do Tenant

Responsabilidade:

- provisionar, suspender e encerrar tenants sem apagar silenciosamente dados;
- gerir planos, subscricoes, entitlements, limites e consumo SaaS;
- configurar entidades legais, filiais, centros operacionais e centros de custo;
- isolar identidade, dados, ficheiros, cache, jobs, eventos e analytics;
- autorizar e auditar acessos excepcionais de suporte;
- permitir configuracao por tenant sem forks de codigo.

Entidades principais:

- `tenants`, `tenant_subscriptions` e `tenant_entitlements`;
- `legal_entities`, `branches` e `cost_centers`;
- `tenant_users`, roles e politicas;
- `support_access_grants` e audit trail de plataforma.

### 4.8 Clientes, Vendas e Contas a Receber

Responsabilidade:

- manter clientes proprios de cada tenant;
- gerir propostas, contratos, tabelas comerciais e pedidos;
- converter servicos executados em facturas e contas a receber;
- controlar notas de credito, recebimentos, saldos e cobranca;
- ligar receita, custo e margem a cliente, contrato, viagem e centro de custo.

O identificador de cliente nunca e global: a identidade efectiva e
`tenant_id + customer_id`. A mesma organizacao pode existir em tenants
diferentes sem partilha implicita de dados.

### 4.9 Compras e Contas a Pagar

Responsabilidade:

- requisitar e aprovar compras;
- comparar cotacoes e emitir ordem de compra;
- receber fisicamente bens ou confirmar servicos;
- conferir ordem, recepcao e factura do fornecedor;
- programar, aprovar e reconciliar pagamentos;
- alimentar stock, activos, custos e contabilidade sem lancamentos duplicados.

Fluxo canonico:

```text
requisicao -> cotacao/aprovacao -> purchase order -> recepcao
           -> factura fornecedor -> three-way match -> pagamento -> diario
```

### 4.10 Inventario e Activos

Responsabilidade:

- gerir catalogo, unidades, categorias, armazens, localizacoes e politicas;
- controlar reservas, entradas, saidas, transferencias, devolucoes e ajustes;
- suportar lote, numero de serie, validade e contagem fisica quando aplicavel;
- valorizar stock por politica definida e manter trilho ate ao documento origem;
- gerir ciclo de vida do activo: aquisicao, atribuicao, manutencao,
  depreciacao, transferencia e abate.

Combustivel, pecas e ferramentas preservam regras operacionais especializadas,
mas publicam movimentos para uma visao consolidada de inventario. Nao podem
existir saldos paralelos sem reconciliacao e owner explicito.

### 4.11 Financas, Contabilidade e Tesouraria

Responsabilidade:

- plano de contas e dimensoes por tenant e entidade legal;
- diarios balanceados e lancamentos automaticos originados nos dominios;
- contas a pagar, contas a receber, caixa e bancos;
- reconciliacao bancaria, periodos, fechos e reabertura autorizada;
- balancete, resultados, balanco e cash flow;
- orcamento versus realizado por centro de custo.

O diario contabilistico e append-only para documentos finalizados. Correccoes
sao feitas por reversao ou documento correctivo auditavel; nunca por alteracao
silenciosa do historico.

### 4.12 Recursos Humanos

Responsabilidade:

- admissao, contrato, documentos, funcao, equipa e centro de custo;
- assiduidade, turnos, ausencias, ferias e disciplina;
- variaveis, processamento salarial, descontos, adiantamentos e pagamento;
- contabilizacao de payroll e reconciliacao com tesouraria;
- desligamento, revogacao de acessos e preservacao legal do historico.

Motorista pode estar ligado a um colaborador, mas os dois agregados nao sao
sinonimos: elegibilidade operacional pertence ao TMS; relacao laboral pertence
ao RH.

### 4.13 Business Intelligence e Alertas

Responsabilidade:

- consumir eventos e fontes de verdade certificadas;
- manter read models e agregados tenant-scoped;
- publicar KPIs com formula, owner, granularidade, freshness e versao;
- permitir drill-down do indicador ate ao documento e movimento origem;
- gerar alertas accionaveis com severidade, responsavel, SLA e escalacao;
- separar BI do tenant de telemetria e BI comercial da plataforma SaaS.

Arquitectura inicial recomendada:

```text
mutacao transaccional
  -> transactional outbox
  -> evento com tenant_id
  -> projection/read model
  -> camada semantica
  -> dashboard, alerta e export
```

O BI operacional pode ser near-real-time. Relatorios financeiros oficiais usam
periodos e snapshots reconciliados; velocidade nunca substitui consistencia.

### 4.14 Oficina Intelligence Layer

A inteligencia da oficina e uma camada de leitura derivada sobre o nucleo
transaccional imutavel. A sua funcao e transformar factos reconciliados em
alertas, explicacoes, recomendacoes, previsoes e simulacoes sem reescrever OS,
orcamentos, movimentos, facturas, pagamentos ou entregas.

```text
nucleo transaccional da oficina
  -> audit + transactional outbox
  -> eventos versionados com tenant_id
  -> projections/read models reconstruiveis
  -> camada semantica e modelos versionados
  -> alertas, rentabilidade, recomendacoes e simulacoes
  -> decisao humana
  -> comando autorizado pela API transaccional, quando aceite
```

A camada analitica nunca escreve directamente nas tabelas operacionais. Uma
recomendacao aceite pode originar um comando explicito, como criar rascunho de
pedido de compra ou agendar contacto WhatsApp, mas esse comando volta a passar
pelas permissoes, validacoes, idempotencia, gates e auditoria do nucleo.

O catalogo inicial de eventos inclui, com schema versionado e `tenant_id`:

```text
WORKSHOP_RECEPTION_ACCEPTED
WORK_ORDER_STATE_CHANGED
DIAGNOSIS_COMPLETED
QUOTE_SENT
QUOTE_APPROVED
QUOTE_REJECTED
SUPPLEMENTAL_QUOTE_CREATED
PART_RESERVED
PART_CONSUMED
TASK_STARTED
TASK_COMPLETED
QUALITY_CONTROL_COMPLETED
INVOICE_ISSUED
PAYMENT_RECORDED
VEHICLE_DELIVERED
PREVENTIVE_MAINTENANCE_DUE
WARRANTY_OR_REWORK_OPENED
```

Evento e contrato de integracao, nao copia arbitraria da tabela. Deve conter
identificador do agregado, versao, occurred_at, actor/contexto autorizado,
correlation/causation/idempotency keys e apenas os dados necessarios. Alteracao
de schema segue compatibilidade e consumer contract tests.

As APIs e interfaces classificam todo resultado derivado:

- `fact`: valor reconciliado com fonte transaccional;
- `forecast`: estimativa futura com horizonte e incerteza;
- `recommendation`: accao sugerida ainda nao aceite;
- `simulation`: cenario hipotetico isolado;
- `decision`: aceite/rejeicao humana ou automatica autorizada;
- `command_result`: resultado factual devolvido pelo nucleo transaccional.

#### 4.14.1 Alertas proactivos

O motor de decisao combina evento, regra/modelo, contexto e accao sugerida.
Alertas minimos:

- peca abaixo do stock minimo com alta rotatividade: calcular risco de ruptura,
  quantidade sugerida e fornecedor elegivel;
- mecanico com carga materialmente acima da equipa: sugerir redistribuicao sem
  transferir trabalho automaticamente;
- OS parada alem do SLA configurado por estado: indicar aging, risco e owner da
  proxima accao;
- viatura com preventiva vencida recebida por outro motivo: sugerir item
  adicional no orcamento, sempre sujeito a aprovacao do cliente;
- cliente com revisao vencida ou inactivo: sugerir contacto conforme
  consentimento e politica de comunicacao.

Cada alerta possui entidade origem, tenant, severidade, owner, SLA, estado,
regra/modelo e versao, dados usados, explicacao, accao sugerida, timestamps e
resultado. Alertas duplicados devem ser correlacionados, nao multiplicados por
replay do mesmo evento.

#### 4.14.2 Rentabilidade operacional

A margem prevista e apresentada durante o orcamento, antes da concessao de
desconto, separando receita, custo de pecas, mao de obra, comissao, desconto,
impostos e custos indirectos alocados. A margem realizada usa apenas consumos,
tempos, documentos e pagamentos reconciliados.

Indicadores minimos:

- margem prevista e realizada por OS, item, servico, cliente e viatura;
- desvio entre orcamento e realizacao, com explicacao;
- ranking de servicos mais e menos rentaveis por periodo;
- impacto do desconto na OS e na margem do periodo;
- custo de retrabalho, garantia e retorno pela mesma queixa/causa.

Previsto e realizado nunca usam o mesmo rotulo. Formula, politica de rateio,
moeda, periodo, freshness e versao devem estar visiveis e reproduziveis.

#### 4.14.3 Saude do negocio

O dashboard executivo da oficina cobre quatro perspectivas:

- Operacao: OS abertas/atrasadas, aging e tempo por estado, ocupacao,
  produtividade, capacidade e gargalos;
- Comercial: conversao orcamento-aprovacao, tempo de resposta, descontos e
  motivos normalizados de rejeicao;
- Financeiro: ticket medio, margem, aging de facturas, recebimentos e previsao
  de caixa por cenarios;
- Cliente: frequencia, ticket por periodo, recorrencia, clientes inactivos,
  preventiva vencida e retorno/reclamacao.

Previsao de caixa separa valores contratados/facturados de receita apenas
potencial associada a preventivas agendadas. Toda previsao exibe horizonte,
premissas, cenario, intervalo de incerteza, data de treino/calculo e erro
historico quando disponivel.

#### 4.14.4 Recomendacoes e assistente

A evolucao e controlada por niveis:

1. regras deterministicas, explicaveis e aprovadas pelo negocio;
2. modelos estatisticos/ML para previsao, anomalia e propensao;
3. assistente em linguagem natural para explicar indicadores e comparar
   cenarios, sem acesso ou accao fora das permissoes do utilizador.

Exemplos incluem rever fornecedor com preco acima da tendencia, avaliar tecnico
acima do tempo padrao, contactar cliente com preventiva vencida e explicar a
queda de margem. Recomendacao nao e ordem, conclusao disciplinar nem facto
contabilistico. Acao automatica exige politica explicita, opt-in, limites,
kill switch e trilho auditavel.

#### 4.14.5 Simulacao e Oficina Digital Twin

Simulacoes podem testar desconto, preco de mao de obra, capacidade, contratacao,
mix de servicos, compra de stock e impacto no fluxo de caixa. Cada execucao e
um cenario isolado e imutavel com autor, tenant, inputs, periodo-base, modelo,
versao, premissas, resultado, incerteza e timestamp.

Resultado simulado nunca actualiza tabela de precos, orcamento, folha salarial,
stock, forecast oficial ou diario. Aplicar um cenario exige workflow separado,
aprovacao e comandos transaccionais normais.

#### 4.14.6 Benchmarking inteligente e privacidade

Benchmark interno compara filiais, equipas, periodos e tipos de servico do mesmo
tenant com dimensoes equivalentes. Benchmark entre tenants e permitido apenas
com base legal/consentimento, dados agregados e anonimizados, coorte minima,
controlo de inferencia e politica aprovada pelo operador SaaS.

Nenhum tenant pode identificar outro tenant, cliente, colaborador, preco,
fornecedor ou volume atraves de ranking, filtro, export ou assistente. Quando a
coorte nao satisfaz o limiar de privacidade, o benchmark nao e publicado.

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

Este e o fluxo canonico ponta a ponta para viaturas proprias do tenant e para
clientes externos do tenant. Recepcao, diagnostico, orcamento, execucao,
qualidade, facturacao e entrega formam uma unica jornada auditavel; nenhum
destes modulos pode manter um lifecycle paralelo ou fechar a sua etapa sem
produzir a pre-condicao exigida pela etapa seguinte.

```text
chegada/agendamento
  -> identificacao do cliente e viatura
  -> historico, alertas e checklist de entrada
  -> RECEBIDO
  -> atribuicao do mecanico
  -> EM_DIAGNOSTICO
  -> DIAGNOSTICO_CONCLUIDO
  -> orcamento original
  -> AGUARDANDO_APROVACAO
  -> APROVADO | REJEITADO
  -> reserva logica de pecas
  -> EM_EXECUCAO
     -> achado adicional
     -> orcamento suplementar independente
     -> aprovacao independente
     -> execucao apenas do suplemento aprovado
  -> EXECUCAO_CONCLUIDA
  -> checklist e controlo de qualidade
  -> QC_CONCLUIDO
  -> consolidacao dos orcamentos aprovados
  -> emissao de factura imutavel
  -> FATURADO
  -> pagamento pendente | parcial | pago
  -> checklist de saida e aceite do cliente
  -> manutencao preventiva seguinte
  -> ENTREGUE
  -> custo real associado a viatura/trip/cliente quando aplicavel
```

#### 5.5.1 Fase 1 - Chegada e recepcao

- A chegada pode resultar de agendamento, alerta preventivo, avaria ou walk-in.
- O recepcionista pesquisa cliente e viatura por telefone, matricula ou outro
  identificador tenant-scoped; se nao existirem, cadastra-os sem criar
  duplicados silenciosos.
- Para viatura existente, a recepcao apresenta OS anteriores, pecas trocadas,
  garantias, recorrencias e manutencoes preventivas pendentes.
- O checklist de entrada regista quilometragem, combustivel, danos com fotos,
  itens pessoais e itens de serie, com assinatura digital ou aceite por canal
  autorizado, incluindo WhatsApp.
- A queixa inicial preserva texto livre e categorias normalizadas. Nao pode ser
  sobrescrita pelo diagnostico tecnico.
- A transicao para `RECEBIDO` grava timestamp do servidor, recepcionista,
  identidade do cliente/representante, canal de aceite, versao do checklist e
  hash/referencia das evidencias. O registo aceite torna-se imutavel; correccao
  posterior e adenda auditavel.

#### 5.5.2 Fase 2 - Diagnostico

- A OS e atribuida manualmente ou por regra explicita de disponibilidade,
  competencia, turno e carga de trabalho.
- O mecanico inicia `EM_DIAGNOSTICO`, regista achados tecnicos separados da
  queixa inicial e conclui em `DIAGNOSTICO_CONCLUIDO`.
- Quando a confirmacao exige desmontagem, o diagnostico e marcado preliminar e
  explicita escopo, incerteza, taxa aplicavel e possibilidade de suplemento.
- Tempo, responsavel, evidencias e alteracoes do diagnostico permanecem
  reconstruiveis.

#### 5.5.3 Fase 3 - Orcamento e gate de aprovacao

- O orcamento agrega pecas com preco e disponibilidade verificados e mao de
  obra por tabela de tempo ou estimativa justificada.
- Cada versao enviada e congelada como snapshot e possui validade, moeda,
  impostos, descontos, termos e canal de envio.
- A decisao do cliente guarda resultado, timestamp do servidor, canal,
  identidade do aprovador e evidencia. Aprovacao por telefone exige registo
  reforcado segundo politica do tenant.
- `AGUARDANDO_APROVACAO -> APROVADO` autoriza apenas os itens e quantidades
  daquela versao. `REJEITADO` encerra a jornada operacional, preservando a taxa
  de diagnostico quando previamente informada e aplicavel.
- Nenhuma reserva de stock, inicio de tarefa, checkout operacional ou consumo
  pode ocorrer antes de uma aprovacao valida.

#### 5.5.4 Fase 4 - Execucao e suplementos

- A aprovacao cria reserva logica das pecas; insuficiencia gera backorder ou
  bloqueio visivel, nunca consumo ficticio.
- O inicio de cada tarefa grava mecanico e tempo real. Apenas tarefa pertencente
  a item aprovado pode entrar em execucao.
- Achado adicional cria diagnostico complementar e orcamento suplementar
  separado, ligado a OS e ao orcamento original, com numeracao, itens, total,
  versao e gate de aprovacao proprios.
- Rejeitar um suplemento nao invalida o original nem autoriza executar o item
  rejeitado. O trabalho original pode continuar quando tecnicamente seguro.
- Conclusao de item confirma resultado, mao de obra e baixa fisica das pecas
  efectivamente usadas; reserva nao consumida e libertada ou reconciliada.
- `EXECUCAO_CONCLUIDA` exige todas as tarefas autorizadas terminadas, pecas e
  ferramentas reconciliadas e nenhum suplemento aprovado pendente.

#### 5.5.5 Fase 5 - Controlo de qualidade

- O checklist de saida testa o funcionamento e cada reparacao aprovada e compara
  a viatura com o checklist de entrada.
- Falha de QC devolve a OS para correccao sem apagar a tentativa, o responsavel,
  os achados ou os tempos anteriores.
- `QC_CONCLUIDO` grava inspector, timestamp, checklist, notas e evidencias. Por
  segregacao de funcoes, o tenant pode exigir inspector diferente do mecanico.
- Nenhuma OS segue para facturacao sem `QC_CONCLUIDO`.

#### 5.5.6 Fase 6 - Facturacao e pagamento

- A facturacao consolida somente o orcamento original e os suplementos
  aprovados, reconciliados com tarefas e consumos efectivos.
- Antes da emissao pode existir rascunho; depois de emitida, a factura e
  imutavel. Correccao exige nota de credito/debito ou documento correctivo
  auditavel, nunca edicao silenciosa.
- O pagamento suporta M-Pesa, e-Mola, numerario, transferencia e outros meios
  configurados, com estados `pendente`, `parcial` e `pago`, referencias e
  reconciliacao.
- `FATURADO` representa documento emitido, nao pagamento confirmado.

#### 5.5.7 Fase 7 - Entrega

- A entrega exige pagamento conforme a politica do tenant, checklist de saida
  aceite pelo cliente e `QC_CONCLUIDO`.
- Entrega com pendencia exige politica activa e autorizacao. Override de QC e
  excepcional, exclusivo de papel autorizado, com motivo, risco aceite,
  timestamp, actor e notificacao/auditoria; nunca altera retroactivamente o
  resultado do QC.
- Na entrega, o sistema agenda a proxima manutencao por quilometragem e/ou tempo
  usando a leitura e a data reais de saida.
- `ENTREGUE` fecha a OS e torna o agregado operacional imutavel. Eventos
  posteriores, como garantia, devolucao, nota de credito ou nova avaria, criam
  agregados ligados; nao reabrem nem reescrevem a OS entregue.

#### 5.5.8 Maquina de estados vinculativa

```text
RECEBIDO
  -> EM_DIAGNOSTICO
  -> DIAGNOSTICO_CONCLUIDO
  -> AGUARDANDO_APROVACAO
  -> APROVADO
  -> EM_EXECUCAO
  -> EXECUCAO_CONCLUIDA
  -> QC_CONCLUIDO
  -> FATURADO
  -> ENTREGUE
```

`REJEITADO` e um terminal comercial depois de `AGUARDANDO_APROVACAO`. Estados de
pagamento sao um lifecycle financeiro relacionado, nao substitutos do estado da
OS. Diagnostico preliminar, backorder, suplemento pendente, falha de QC e
entrega autorizada com pendencia sao subestados/condicoes persistidas; nao
permitem saltar gates.

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

### 6.6 Isolamento SaaS Multi-Tenant

- Toda entidade de negocio, movimento, ficheiro, job, evento e read model deve
  ter ownership de tenant inequivoco.
- Toda referencia a cliente, fornecedor, colaborador, artigo ou documento deve
  ser validada dentro do mesmo `tenant_id`.
- PostgreSQL RLS e GRANT da role de runtime sao controlos obrigatorios, nao
  substitutos de filtros e testes na aplicacao.
- Constraints e foreign keys compostas devem impedir referencias cross-tenant
  mesmo perante erro de servico.
- Cache keys, object storage paths, idempotency keys, filas, logs e metricas
  devem incluir o contexto de tenant quando contiverem dados do negocio.
- Platform Admin nao recebe acesso implicito aos dados do tenant. Suporte exige
  grant temporario, motivo, escopo, expiracao e auditoria.
- Export, backup, restore, offboarding e apagamento devem respeitar o tenant e
  a politica de retencao aplicavel.

### 6.7 Integridade ERP

- Stock muda apenas por movimento atomico ligado ao documento origem.
- Todo diario finalizado tem debitos iguais a creditos.
- Compra nao cria stock antes da recepcao aceite.
- Factura de fornecedor nao e paga sem aprovacao e controlo de duplicados.
- Venda/servico nao e reconhecido duas vezes por retry ou integracao.
- Documento finalizado nao e reescrito; usa-se reversao ou documento correctivo.
- Periodo fechado rejeita lancamento retroactivo sem reabertura autorizada.
- Numeracao documental e unica por tenant, entidade legal, tipo, serie e
  periodo conforme a politica configurada.
- Toda mutacao critica de dinheiro, stock, payroll ou activo grava audit e
  outbox na mesma unidade de trabalho.

### 6.8 Consistencia do BI

- Cada KPI tem nome, formula, fonte, dimensoes, owner, versao e freshness SLO.
- Nenhum dashboard calcula uma segunda versao informal de uma metrica canonica.
- KPI permite drill-down ate aos registos que explicam o valor.
- Correccoes e backfills sao idempotentes e deixam evidencia.
- Alertas possuem ciclo `open -> acknowledged -> resolved/escalated` e entidade
  origem; notificacao sem estado persistido nao conta como alerta controlado.
- Freshness alvo: eventos criticos ate 5 segundos, dashboards operacionais ate
  30 segundos e agregados financeiros de gestao ate 5 minutos. Relatorios de
  fecho dependem de reconciliacao, nao de eventual consistency.

### 6.9 Integridade do lifecycle da oficina

- Toda transicao da OS e validada no backend sob lock/controlo de concorrencia;
  esconder uma accao na interface nao constitui gate.
- Cada transicao grava actor, role, tenant, estado anterior/novo, timestamp do
  servidor, motivo, canal, correlation/idempotency key e evidencias aplicaveis.
- Recepcao assinada, aprovacao de orcamento, QC, factura emitida, override e
  entrega sao registos append-only ou snapshots imutaveis.
- Orcamento original e suplemento sao agregados distintos. Um suplemento nunca
  altera itens, totais, aprovacao ou evidencia do original.
- Reserva e consumo de stock sao movimentos distintos e reconciliaveis.
- Nenhuma tarefa pode iniciar sem item aprovado; nenhuma factura pode ser
  emitida sem QC; nenhuma entrega pode ocorrer sem politica financeira
  satisfeita ou override autorizado.
- Override reduz um bloqueio especifico, tem validade e escopo, e nunca apaga o
  risco, a regra violada ou a decisao original.
- Retry, chamadas concorrentes e reenvio de WhatsApp nao duplicam OS,
  aprovacoes, reservas, consumos, facturas, pagamentos ou entregas.

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
- OS por estado, aging e SLA ultrapassado;
- manutencoes vencidas;
- manutencoes proximas;
- pecas abaixo do minimo;
- risco de ruptura por consumo e lead time;
- ferramentas em atraso;
- carga, ocupacao e produtividade por equipa;
- tempo medio e percentis por fase e tipo de servico;
- conversao de orcamentos e motivos de rejeicao;
- margem prevista/realizada e impacto de descontos;
- custo e taxa de retrabalho/garantia;
- viaturas aguardando quality check;
- clientes inactivos e preventivas vencidas;
- previsao de caixa da oficina com intervalo de incerteza.

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

O board separa factos, previsoes e recomendacoes visualmente. Cada indicador
permite drill-down ate aos registos autorizados que explicam o valor; cada
recomendacao mostra regra/modelo, versao, evidencia e accao sugerida.

### 7.4 Billing Control Board

Indicadores:

- entregas validadas nao cobradas;
- viagens sem contrato;
- documentos de cobranca em draft;
- documentos emitidos no periodo;
- valor por cliente;
- valor pendente;
- viagens com POD no mes seguinte.

### 7.5 ERP Executive Board

Indicadores tenant-scoped:

- receita, custo, margem bruta e resultado operacional;
- contas a receber e a pagar por aging;
- posicao de caixa e bancos;
- compras comprometidas e ainda nao recebidas;
- valor e rotacao de stock;
- custo de frota e oficina por viatura;
- custo de pessoal e payroll pendente;
- desvios de orcamento e centros de custo em risco.

Todos os cards devem declarar periodo, moeda, entidade legal, freshness e link
de drill-down. Consolidacao entre entidades legais e permitida apenas dentro do
mesmo tenant e com regra de eliminacao explicita.

### 7.6 Platform SaaS Board

Indicadores sem expor dados operacionais detalhados dos tenants:

- tenants activos, suspensos e em onboarding;
- planos, entitlements e limites consumidos;
- MRR/ARR, churn e cobranca SaaS;
- disponibilidade, erros, filas e SLO por tenant;
- adopcao agregada de modulos;
- acessos de suporte activos e proximos da expiracao.

Telemetria de plataforma deve ser agregada ou minimizada. Acesso ao detalhe do
negocio do tenant nao e uma funcionalidade implicita deste board.

## 8. Perfis e Permissoes

Perfis minimos:

- Platform Admin;
- Platform Billing;
- Platform Support com acesso just-in-time;
- Tenant Admin;
- Legal Entity Admin;
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
- Procurement Officer;
- Sales/Billing Officer;
- Finance Officer;
- Accountant;
- Treasury Officer;
- HR Officer;
- Payroll Officer;
- Inventory/Asset Controller;
- BI Analyst;
- Auditor.

Segregacoes obrigatorias:

- Quem abastece nao aprova ajuste de stock.
- Quem usa peca nao deve controlar sozinho o inventario.
- Quem executa manutencao nao deve sempre libertar viatura sem validacao.
- Quem solicita uma compra nao deve aprovar, receber e pagar sozinho.
- Quem recebe mercadoria nao deve aprovar sozinho a factura do fornecedor.
- Quem prepara pagamento nao deve ser o unico aprovador.
- Quem processa payroll nao deve aprovar e executar sozinho o pagamento.
- Finance Officer reconcilia e cobra, mas nao altera execucao operacional.
- Platform Admin gere o SaaS, mas nao assume papel operacional no tenant.
- Suporte acede apenas mediante grant temporario, limitado e auditado.
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

Executar a jornada de oficina desde a chegada ate ao QC, com gates
transaccionais e trilho auditavel.

Entregaveis:

- recepcao agendada/walk-in e pesquisa tenant-scoped de cliente/viatura;
- historico, alertas e checklists de entrada/saida com fotos e aceite;
- `maintenance_requests`;
- `work_orders`;
- `work_order_tasks`;
- diagnostico preliminar/final e atribuicao de mecanico;
- maquina de estados canonica da seccao 5.5;
- orcamento original, versoes e suplementos com aprovacoes independentes;
- reserva logica, consumo fisico e reconciliacao de pecas;
- tempos de mao de obra e conclusao por item aprovado;
- QC com retorno para correccao e segregacao configuravel;
- estados de bloqueio/libertacao;
- ligacao com vehicle availability;
- Workshop Control Board por etapa, bloqueio e aging;
- timeline imutavel das transicoes e decisoes.

Aceite quando:

- work order activa torna viatura indisponivel e identifica a fase corrente;
- servico e consumo falham sem aprovacao valida do item correspondente;
- suplemento rejeitado nao autoriza execucao nem altera o orcamento original;
- `EXECUCAO_CONCLUIDA` falha com tarefa, peca, ferramenta ou suplemento aprovado
  pendente;
- QC falhado preserva evidencia e devolve a OS para correccao;
- OS sem `QC_CONCLUIDO` nao pode ser facturada;
- avaria em viagem pode criar maintenance request;
- custo de manutencao pode alimentar trip cost actuals;
- jornada real e concorrencia/retry passam com dois tenants e 404 cross-tenant.

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
- `maintenance_schedule`;
- facturacao consolidada de original e suplementos aprovados;
- pagamentos pendente/parcial/pago;
- entrega com aceite e politica financeira;
- nota de credito/debito para corrigir documento emitido;
- agendamento preventivo baseado na data/km reais de entrega.

Aceite quando:

- peca nao sai sem stock suficiente;
- stock de peca muda apenas por movimento;
- ferramenta checked out nao pode ser levantada de novo;
- ferramenta vencida/danificada pode bloquear checkout;
- manutencao vencida gera exception;
- factura emitida e imutavel e exclui todo item nao aprovado;
- entrega sem QC falha, salvo override de gestor explicitamente auditado;
- entrega sem condicao financeira falha conforme politica do tenant;
- `ENTREGUE` e terminal e a proxima manutencao usa data/km reais de saida.

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

Execucao detalhada: ver `15. Programa de Promocao a Producao Premium`. A Wave 8
nao e aceite pela presenca destes componentes no codigo; exige a evidencia e os
gates definidos nessa seccao.

### Wave 9 - SaaS Tenant Foundation and Master Data

Objectivo:

Tornar o modelo `plataforma -> tenant -> entidades legais/filiais -> clientes`
uma fronteira executavel e comprovada.

Entregaveis:

- lifecycle de tenant, subscricao, plano, entitlement e limites;
- entidades legais, filiais, centros de custo e sequencias documentais;
- master data tenant-scoped de clientes, fornecedores, artigos e colaboradores;
- constraints e foreign keys que rejeitam referencias cross-tenant;
- suporte just-in-time com expiracao e auditoria;
- export e offboarding de tenant;
- testes com dois tenants e identificadores de negocio sobrepostos.

Aceite quando:

- Tenant A nunca le, altera, exporta ou infere dados do Tenant B;
- Platform Admin nao entra implicitamente no contexto operacional do tenant;
- cliente do tenant e sempre resolvido dentro de `tenant_id`;
- entitlement e controlado pela plataforma, nao auto-activado pelo tenant;
- provisioning, suspensao, reactivacao e offboarding deixam evidencia.

### Wave 10 - Procure-to-Pay and Unified Inventory

Objectivo:

Fechar compras, fornecedores, recepcao, stock, activos e contas a pagar.

Entregaveis:

- requisicoes, cotacoes, aprovacoes e purchase orders;
- recepcao parcial/total, devolucao e three-way match;
- factura de fornecedor, vencimentos e pagamentos;
- inventario unificado com armazens, reservas, transferencias e contagens;
- lotes/seriais e valorizacao conforme politica do tenant;
- integracao de combustivel, pecas, ferramentas e activos;
- segregacao de funcoes e lancamentos contabilisticos automaticos.

Aceite quando:

- compra aprovada nao aumenta stock antes da recepcao;
- recepcao, stock, factura, pagamento e diario reconciliam ponta a ponta;
- retry nao duplica recepcao, movimento, factura ou pagamento;
- contagem fisica explica e audita cada ajuste;
- nenhum saldo paralelo fica sem reconciliacao e owner.

### Wave 11 - Order-to-Cash, Accounting and Treasury

Objectivo:

Fechar vendas, facturacao, cobranca, recebimentos e contabilidade por tenant.

Entregaveis:

- propostas/pedidos e contratos comerciais;
- contas a receber, recebimentos, notas de credito e aging;
- plano de contas, diarios, periodos e centros de custo;
- caixa, bancos, reconciliacao e cash flow;
- P&L, balancete e balanco por entidade legal e consolidado do tenant;
- fecho e reabertura controlada de periodo;
- separacao tecnica e contabilistica entre billing SaaS e billing do tenant.

Aceite quando:

- uma operacao real percorre contrato ate recebimento e diario sem duplicacao;
- todo diario finalizado permanece balanceado;
- periodo fechado bloqueia lancamento retroactivo nao autorizado;
- saldos AP/AR, bancos e razao reconciliam;
- documentos SaaS nunca aparecem nas contas dos clientes do tenant.

### Wave 12 - Enterprise HRM, Payroll and Asset Lifecycle

Objectivo:

Entregar o sistema corporativo de pessoas do tenant: strategy, core HR, talent,
workforce, rewards, payroll, experience, service delivery, relations, safety e
activos com impacto financeiro e operacional. O contrato vinculativo esta em
`docs/PRD_HRM_ROTAS.md` e a implementacao fisica em
`docs/HRM_IMPLEMENTATION_BLUEPRINT.md`; a Wave 12 nao autoriza prolongar o
scaffold legado como se este estivesse certificado.

Entregaveis:

- organization tenant-scoped: entidade legal, filial, unidade, departamento,
  equipa, cargo, posicao, headcount e centro de custo;
- workforce planning, position budget, cenarios e plan-versus-actual;
- requisition, candidate experience, assessment, offer e onboarding journeys;
- pessoa, worker profile, vinculo, utilizador, motorista e tecnico como agregados
  relacionados, mas nao fundidos;
- empregados, gestores, executives, interns, trainees, contractors e agency
  workers no modelo de total workforce;
- contratos e pacotes de compensacao effective-dated, sem salario mutavel no
  cadastro da pessoa;
- compensation review, benefits, total rewards e eligibility;
- lifecycle de colaborador, assiduidade offline, escalas, ausencias, ferias,
  skills, certificacoes e disponibilidade explicada;
- learning, goals, feedback, performance, calibration, career, mobility,
  talent review e succession;
- candidate, employee, manager e HR workspaces;
- HR service catalog, knowledge, cases, engagement, employee relations, labour
  relations, OHS, wellbeing e medical outcomes segregados;
- envelope de eventos versionado, outbox/inbox, idempotencia, replay, backfill e
  reconciliacao com TMS e Oficina;
- rule engine legal versionado, inputs congelados, memoria de calculo e payroll
  run `OPEN -> INPUTS_LOCKED -> CALCULATED -> VALIDATED -> APPROVED -> POSTED ->
  PAYMENT_PENDING -> PAID -> CLOSED`;
- segregacao entre preparar, aprovar, contabilizar, pagar e reconciliar;
- recibos, ajustes, outputs AT/INSS, contabilizacao e reconciliacao
  payroll-to-ledger-to-bank;
- self-service do colaborador e acesso do gestor limitado por equipa/campo;
- lifecycle de activos, atribuicoes, transferencias, depreciacao e abates;
- revogacao de acesso, devolucao de activos e checklist de desligamento;
- migration/backfill expand-contract do scaffold HR legado.

Aceite quando:

- o Gestor de RH planeia, atrai, admite, desenvolve, recompensa, apoia, mobiliza
  e desliga qualquer perfil da empresa, nao apenas recursos de TMS/Oficina;
- pessoa, vinculo, posicao, compensacao e perfil operacional possuem fontes e
  vigencias distintas;
- requisition exige position/headcount budget ou override auditado;
- candidate/employee/manager/HR percorrem jornadas próprias e acessíveis;
- performance e succession têm contexto, appeal e não geram decisão adversa
  automática;
- casos ER, denúncias e dados médicos provam vault e need-to-know;
- TMS/Oficina nao atribuem pessoa inelegivel e recebem os motivos sem ler tabelas
  internas de HR;
- ponto/correccao, ferias e eventos operacionais reconciliam sem perder o facto
  original;
- payroll e reproduzivel pelo snapshot, ruleset, memoria e hash aprovados;
- diario so nasce depois de aprovacao e reconcilia com pagamento, banco e
  outputs legais;
- o mesmo evento/retry nao gera rubrica, desconto, adiantamento, diario,
  pagamento ou submissao duplicados;
- preparador nao aprova nem paga sozinho a mesma folha;
- dois tenants com identificadores sobrepostos provam RLS, field authorization,
  storage, cache, export, evento e worker isolados;
- activo possui custodia, localizacao, valor e historico reconstruiveis;
- desligamento remove acesso e disponibilidade sem apagar historico laboral ou
  operacional;
- RH/Legal/Financas assinam a matriz legal do tenant piloto.

### Wave 13 - Embedded Business Intelligence

Objectivo:

Transformar dados ERP/TMS certificados em decisao near-real-time.

Entregaveis:

- catalogo e camada semantica versionada de KPIs;
- outbox e pipeline de projections tenant-scoped;
- Executive, Transport, Fuel, Workshop, Finance, Sales, Procurement, Stock e HR
  boards;
- metas, tendencias, comparacoes e drill-down;
- alertas com severidade, owner, SLA, acknowledge, resolucao e escalacao;
- Oficina Intelligence Layer com aging, rentabilidade, conversao, retrabalho,
  customer intelligence e previsao de caixa;
- motor de recomendacoes deterministicas antes de ML/assistente;
- simulador de desconto, preco de mao de obra, capacidade e fluxo de caixa;
- model registry, feature/data lineage, explainability, monitorizacao de drift,
  avaliacao e rollback para modelos analiticos;
- benchmarking interno e politica privacy-preserving para qualquer benchmark
  entre tenants;
- BI separado da plataforma SaaS com minimizacao de dados;
- reconciliacao automatica entre read models e fontes transaccionais.

Aceite quando:

- KPI explica formula, periodo, moeda, dimensoes, freshness e fonte;
- dashboard nunca revela dados de outro tenant;
- evento critico aparece ate 5 segundos e board operacional ate 30 segundos nas
  condicoes de referencia;
- relatorio financeiro reproduz o periodo fechado;
- alerta liga ao registo origem e possui lifecycle auditavel;
- rebuild de projection e idempotente e reconcilia com a fonte;
- margem prevista e realizada reconciliam com snapshots, consumos e documentos;
- recomendacao e simulacao nunca alteram directamente o nucleo transaccional;
- cada accao aceite volta a passar pela API, RBAC, gates e audit;
- previsao publicada exibe premissas, incerteza e erro historico;
- benchmark cross-tenant abaixo da coorte minima falha fechado.

## 10. Dependencias de Implementacao

Ordem recomendada:

```text
Audit base
  -> Tenant isolation and entitlements
  -> Trip Orders
  -> Availability
  -> Dispatch
  -> Execution Events
  -> Exceptions
  -> Fuel Movements
  -> Workshop Blocking
  -> Cost Actuals
  -> Control Tower
  -> ERP master data
  -> Procure-to-Pay and unified inventory
  -> Order-to-Cash, accounting and treasury
  -> HR, payroll and assets
  -> KPI semantic layer and projections
  -> Embedded BI and alerts
```

Risco se inverter:

- construir fuel sem movements cria divida contabilistica;
- construir workshop sem availability cria incoerencia operacional;
- construir frontend antes de services estaveis cria retrabalho;
- construir WhatsApp antes de exceptions internas cria notificacoes sem regra forte.
- construir ERP sem master data tenant-scoped cria referencias cross-tenant;
- construir contabilidade antes dos movimentos origem cria diarios manuais sem
  rastreabilidade;
- construir BI antes de reconciliar fontes de verdade institucionaliza KPIs
  contraditorios;
- usar billing SaaS no mesmo agregado do billing do tenant mistura receitas e
  responsabilidades legais diferentes.

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

- recepcao aceite preserva checklist, fotos, actor, timestamp e canal;
- queixa inicial permanece separada do diagnostico tecnico;
- transicoes fora da maquina de estados canonica falham sem mutacao;
- tarefa, tempo ou consumo de peca sem item aprovado falham;
- aprovacao e rejeicao concorrentes produzem uma unica decisao terminal;
- suplemento possui snapshot e gate independentes do orcamento original;
- suplemento nao aprovado nunca entra em execucao nem facturacao;
- reserva logica nao equivale a baixa fisica e ambas reconciliam;
- execucao nao conclui com tarefa/ferramenta/peca pendente;
- QC falhado preserva tentativa e bloqueia facturacao;
- factura emitida nao pode ser editada e correccao gera documento correctivo;
- pagamento parcial nao e apresentado como pago;
- entrega sem QC ou sem condicao financeira aplicavel falha;
- override de entrega exige papel, motivo, escopo e audit imutavel;
- `ENTREGUE` e terminal e cria o proximo agendamento preventivo;
- retries nao duplicam aprovacao, stock, factura, pagamento ou entrega;
- todas as regras passam com role PostgreSQL restrita e tentativa cross-tenant.

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

### SaaS Multi-Tenant

- duas entidades com o mesmo UUID logico em tenants diferentes nao colidem;
- API, BFF, worker, cache, ficheiro, export e projection rejeitam cross-tenant;
- foreign key cross-tenant falha na base mesmo se o servico errar;
- Platform Admin sem grant nao le dados operacionais;
- suporte expirado perde acesso e deixa trilho auditavel;
- backup/restore e export preservam ownership do tenant.

### ERP and Finance

- purchase order, recepcao, factura e pagamento reconciliam;
- venda, factura, recebimento e diario reconciliam;
- movimentos concorrentes nao produzem stock negativo indevido;
- diario desbalanceado falha atomicamente;
- periodo fechado rejeita lancamento retroactivo;
- retry nao duplica documento, movimento, pagamento ou lancamento;
- billing SaaS e billing do tenant permanecem isolados.

### HR and Assets

- pessoa, vinculo, posicao, compensacao e perfil motorista/mecanico nao sao
  fundidos;
- vigencias, sobreposicoes e historico laboral passam invariantes temporais;
- ponto offline, correccao, ferias, disponibilidade e eventos TMS/Oficina
  reconciliam de forma idempotente;
- payroll aprovado e reproduzivel e reconcilia com pagamento, banco, diario e
  outputs legais;
- segregacao impede preparador de aprovar, postar, pagar e reconciliar sozinho;
- ajuste nao edita folha ou periodo fechado;
- acesso de gestor nao revela salario, banco ou documento sensivel;
- desligamento revoga acesso sem apagar historico;
- transferencia, depreciacao e abate preservam cadeia do activo.

### Business Intelligence

- KPI canonico reconcilia com a fonte transaccional;
- projection pode ser reconstruida de forma idempotente;
- freshness SLO e medido e alerta quando violado;
- drill-down explica o valor agregado;
- filtros, cache, export e alertas nunca atravessam tenant;
- margem prevista/realizada usa formulas e snapshots versionados;
- regra/modelo produz a mesma recomendacao para o mesmo input versionado;
- recomendacao rejeitada ou ignorada nao produz mutacao transaccional;
- recomendacao aceite cria comando auditado e idempotente pela API do dominio;
- simulacao permanece isolada ate aprovacao e aplicacao explicita;
- forecast e avaliado por backtest e exibe erro e intervalo de incerteza;
- drift, degradacao e falha do modelo accionam fallback deterministico ou
  suspensao fail-closed;
- assistente respeita RBAC, tenant, fontes citadas e nao inventa accoes;
- benchmark entre tenants respeita consentimento, coorte minima e
  anti-inferencia.

## 12. Criterios de MVP Aceite

### 12.1 Primeiro Piloto TMS

O primeiro piloto operacional TMS e aceite quando:

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

Este aceite nao equivale a declarar o ERP/BI completo nem promove producao sem
os gates da seccao 15.

### 12.2 Base ERP/TMS SaaS Obrigatoria

A base pretendida do produto e aceite apenas quando:

1. Isolamento e demonstrado com pelo menos dois tenants reais de teste.
2. Cada tenant gere entidades legais, filiais, utilizadores e clientes proprios.
3. Compras percorrem requisicao ate pagamento e diario.
4. Vendas/servicos percorrem contrato ate recebimento e diario.
5. Stock, combustivel, pecas, ferramentas e activos possuem fontes reconciliadas.
6. Contabilidade fecha periodo com AP, AR, bancos, payroll e razao reconciliados.
7. Oficina liga aprovacao, mao de obra, pecas, facturacao e disponibilidade.
8. RH fecha payroll e desligamento com segregacao e auditoria.
9. BI reproduz os numeros transaccionais e permite drill-down.
10. Alertas possuem owner, SLA, estado e entidade origem.
11. Subscricao SaaS e financeiramente separada das vendas do tenant.
12. Journeys passam com servicos, roles e dados reais, nao apenas mocks.

## 13. Fora do Primeiro Piloto TMS

Nao implementar antes de fechar as dependencias e gates do primeiro piloto;
estes itens podem continuar no produto-alvo:

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
- integracoes fiscais avancadas especificas por jurisdicao;
- multi-stop complexo N:M.

## 14. Principio de Execucao

Cada nova funcionalidade deve responder antes de ser implementada:

- Quem e o tenant owner e qual entidade legal/filial se aplica?
- Pode algum identificador ou relacao atravessar tenant?
- Que dominio owns esta regra?
- Que entidade e fonte de verdade?
- Que estado altera?
- Que disponibilidade afecta?
- Que custo afecta?
- Que exception pode gerar?
- Que audit log deve deixar?
- Que teste prova a regra?
- Que tela ou board consome o resultado?
- Que evento/read model/KPI consome a alteracao?
- Como e reconciliada e reconstruida?

Se uma funcionalidade nao responder a estas perguntas, ainda nao esta pronta para entrar no roadmap.

## 15. Programa de Promocao a Producao Premium

### 15.1 Mandato e estado inicial

Este programa e a execucao detalhada da Wave 8. Nao e uma roadmap paralela e
nao autoriza uma reescrita. O `STABILIZATION_LOG.md` permanece o diario tactico
de implementacao; este documento e a fonte canonica de prioridade, dependencia,
evidencia e decisao GO/NO-GO.

Baseline de 2026-07-22:

- arquitectura conceptual: favoravel;
- fase: beta avancada em estabilizacao pre-piloto;
- decisao de release: NO-GO;
- backend: 371 rotas importadas e 520 testes colectados;
- Alembic: uma head (`bay01`), mas a base local auditada esta em
  `95929ae669b9`;
- frontend: Manager e Driver passam typecheck e build de producao;
- qualidade: Ruff integral ainda vermelho, incluindo erros semanticos;
- integracao Governance: outbox presente, mas produtores e contrato HTTP ainda
  nao fechados ponta a ponta;
- seguranca frontend: coexistem BFF, chamadas directas e tokens em
  `localStorage`;
- supply chain: vulnerabilidades high ainda presentes em dependencias de
  producao.

Actualizacao de engenharia em 2026-07-27:

- PR-00 passou a ter contrato versionado e fail-closed para as oito funções,
  feature freeze, `CODEOWNERS`, política mínima de duas aprovações e formação
  do RC; a CI passou a cobrir `stabilization/**`. Contrato, 4 testes, Ruff,
  JSON e YAML passaram localmente. A auditoria remota de 2026-08-01 encontrou
  apenas
  `dequive` como colaborador, `master`/`main` sem proteção, zero rulesets e
  branch remota de estabilização inexistente. Com um único owner distinto não
  há duas revisões independentes; PR-00 e G0 permanecem amarelos;
- a remediação GitHub PR-00 publicou a branch de estabilização e um commit
  limpo `1012ecf` no PR 1. `master`, `main` e estabilização passaram a exigir
  dois approvals, CODEOWNERS, checks, conversas resolvidas e histórico linear,
  inclusive para admins. Actions foi limitado a actions GitHub-owned fixadas
  por SHA e token read-only; Dependabot, vulnerability alerts, secret scanning,
  push protection e reporte privado foram activados. A conta GitHub continua
  locked por billing, impedindo runners; existe apenas um colaborador e a
  estabilização passou a ser a default branch protegida após autorização
  explícita. O scan multi-ecossistema passou a expor 60 alerts abertos, 26
  high, 30 medium e 4 low, para tratamento no PR-18. Por isso PR-00/G0
  continuam amarelos e o PR não pode ser mergeado;
- PR-01 foi reconstruído sem copiar funcionalidades do worktree principal e
  publicado no commit `8c47623`, draft PR 5 empilhado sobre o PR 1. Ruff,
  compile/import, OpenAPI com 370 rotas/296 paths/363 operações e 14 testes
  puros passaram; a partição DB teve 29 pass e 10 falhas preexistentes
  explicitadas. Backend/Frontend remotos não iniciaram devido ao mesmo billing
  lock e E2E foi skipped; faltam revisão, merge da pilha e reprodução no RC,
  portanto G0 permanece amarelo;
- isolamento PostgreSQL: `rec13` e uma unica policy canonica por tabela
  tenant-scoped; `rotas_app` e `NOBYPASSRLS`, e a aplicacao rejeita papel
  superuser/BYPASSRLS em producao; `rotas_admin` permanece `NOSUPERUSER` com
  `BYPASSRLS` e recebeu os GRANTs de tabela/sequencia exigidos por workers
  cross-tenant;
- regressao focada RLS/roles/relacoes/ficheiros/operacoes: `21 passed`, com
  login directo de `rotas_admin` validado;
- PR-02 foi publicada no commit `26caedc`, draft PR 9 empilhado sobre a PR-01:
  o CI bloqueia agora todo `app` e `tests` com Pyright; a baseline real de 744
  erros caiu para zero. Ruff, compileall, OpenAPI com 370 rotas/296 paths/363
  operações e a suite completa (`528 passed, 1 skipped`) passaram localmente.
  Backend/Frontend remotos não iniciaram devido ao billing lock e E2E foi
  skipped; G0 continua amarelo;
- PR-04 foi isolada no commit `58e4d27`, draft PR 10 sobre a PR-02. Uma base
  PostgreSQL 16 vazia migrou até à única head `rec13`; `alembic check` não
  detectou drift, 123 tabelas foram criadas e 113 têm ENABLE/FORCE RLS, sem
  tabela tenant-scoped não-particionada desprotegida. Ruff, Pyright, compileall
  e `530 passed, 1 skipped` ficaram verdes. Os jobs GitHub não iniciaram pelo
  mesmo billing lock; PR-05 continua responsável pelo upgrade de snapshot;
- PR-05 foi publicada no commit `51d3216`, draft PR 11 sobre a PR-04. O gate
  de restore/upgrade agora é fail-closed para anonimização e integridade e o
  smoke sintético até `rec13` passou com fingerprint preservado, zero waits
  observados e `532 passed, 1 skipped`. O Pyright do novo teste tem zero erros;
  o único erro global está herdado em billing e foi mantido fora do escopo.
  Falta o ensaio com snapshot representativo autorizado, tráfego concorrente e
  rollback independente; G1 permanece amarelo. Os jobs GitHub não iniciaram
  devido ao mesmo billing lock e billing não foi alterado;
- PR-06 foi publicada no commit `896a157`, draft PR 12 sobre a PR-05. A API
  tenant-facing passou a exigir `rotas_app` NOSUPERUSER/NOBYPASSRLS e a
  identidade/control-plane usa `rotas_admin`; produção recusa uma ligação
  privilegiada antes de aceitar tráfego. O auditor direto encontrou 114
  tabelas tenant-scoped, zero gaps de RLS/policy/grants e zero blockers. A
  prova com dois tenants cobriu relações, mutações, ficheiros, outbox e Oficina;
  a suíte terminou `546 passed, 1 skipped`. PR-06 está `done_local`, mas G1
  permanece amarelo até PR-05, revisão, CI e reprodução no RC. Os jobs GitHub
  não iniciaram pelo mesmo billing lock; billing não foi alterado;
- PR-08 concluiu localmente a fronteira Browser -> BFF -> API: gate AST
  bloqueante analisou 94 modulos client-side com zero token/storage, URL
  publica de backend, cabecalho Authorization ou fetch directo; login guarda
  access/refresh tokens apenas em cookies HttpOnly, 4 testes do gate e 75
  testes Manager passaram, com typecheck e build de 72 paginas verdes;
  reproducao no RC, E2E de seguranca e pentest continuam obrigatorios;
- PR-09 concluiu localmente o contrato OpenAPI 3.1 versionado: 300 paths, 367
  operacoes e 217 schemas geram tipos TypeScript deterministas e um cliente
  runtime que usa apenas o BFF. Drift FastAPI -> JSON e JSON -> TypeScript
  bloqueia o CI; contrato backend 2/2, Manager 76/76, typecheck e build de 72
  paginas passaram. A migracao dos helpers sera incremental no PR-10 e a
  cadeia dev Redocly permanece contabilizada no gate de vulnerabilidades;
- PR-10 concluiu localmente o contrato comum: `@rotas/http-contract` concentra
  timeout, erro tipado, retry com backoff/`Retry-After` e idempotencia; os
  clientes Manager/Driver, o sync Driver e todos os route handlers BFF foram
  migrados. O gate AST cobre 98 modulos client-side e 36 handlers com zero
  violacoes; os seus 6 testes, Manager 85/85, Driver 14/14, typechecks e builds
  passaram. CI no SHA do RC e rede degradada em staging continuam pendentes;
- PR-15 fechou localmente o lifecycle offline do Driver: Dexie v3 persiste
  backoff/tentativas/dead-letter, recupera itens interrompidos, roda tokens em
  401, limita o snapshot ao mesmo tenant/motorista e oferece painel de recovery
  com requeue e descarte transaccional. O bootstrap autenticado passou a
  `NetworkOnly`; Driver 23/23, typecheck e build PWA final de 1.807 módulos
  passaram. Chromium 1/1 comprovou cold start offline, ausência do bootstrap no
  cache Workbox, reconciliação com a mesma chave e ausência de duplicação após
  novo sinal online. RC, staging/dispositivo e rede degradada continuam
  pendentes; o purge na troca de identidade foi endereçado no PR-16;
- PR-16 fechou localmente o isolamento de identidade do Driver: Dexie v4,
  snapshots, filas, fotografias e contadores usam tenant/motorista/sessão; o
  logout revoga credenciais e limpa transaccionalmente dados, caches
  autenticados e fila Workbox antes de permitir novo pairing. Driver 26/26,
  typecheck e build PWA de 1.808 módulos passaram; Chromium 2/2 comprovou
  logout/purge/troca de identidade e preservou o cold start offline. Staging,
  Android físico, crash/storage pressure e RC continuam pendentes;
- PR-17 fechou localmente os fallbacks demonstrativos do Manager: datasets
  fictícios de cobrança, torre de controlo, históricos, combustível e despacho
  foram removidos, assim como as flags permissivas do CI/Playwright. API vazia
  produz estado vazio real e API indisponível nunca produz factos inventados.
  Um gate bloqueante passou source scan e 3/3 testes; Manager passou 86/86,
  typecheck, build de 72 páginas e scan do bundle. CI no SHA do RC e jornadas
  contra backend/staging real continuam obrigatórios;
- PR-18 foi reavaliado em 2026-07-29 e permanece `blocked_upstream`: Next foi
  atualizado para 16.2.12, PostCSS directo para 8.5.24 e brace-expansion foi
  corrigido; o grafo válido reduziu produção de 4 para 3 high. O Next ainda
  instala PostCSS 8.4.31 e Sharp 0.34.5. Um override ensaiado em instalação
  limpa produziu audit zero, mas `npm ls` exit 1 com ambos os pacotes
  `invalid`; foi rejeitado para evitar falsa mitigação. Manager passou 89
  testes/build de 72 rotas e Driver 26/build PWA, localmente em Node 24. G4
  continua vermelho até existir árvore suportada, zero high/critical ou
  waivers formais e reprodução no Node 20/RC;
- PR-14 fechou localmente a operação do transactional outbox: API e CLI
  tenant-scoped usam permissões `outbox.read`/`outbox.replay`, reconciliação
  local classifica a saúde, o drainer publica métricas Prometheus e cria alerta
  high determinístico ao entrar em DLQ. Replay exige motivo, usa `FOR UPDATE`,
  preserva a identidade idempotente e grava audit na mesma transação; duas
  chamadas concorrentes produziram uma transição e um audit. A partição passou
  22 testes, Ruff, Pyright, OpenAPI e typecheck Manager. G3 continua amarelo até
  replay/alerta/reconciliação serem exercitados contra Governance e staging
  reais no SHA do RC;
- PR-19 avançou de `pending` para `in_progress`: existe agora uma baseline
  provider-neutral de staging com Compose, Caddy/TLS, secrets externos,
  migrations one-shot, redes separadas e quatro imagens aplicacionais
  endurecidas, não-root e exigidas por digest. A política estática, renderização
  do Compose, 27 testes backend, 19 Governance, Ruff, Pyright e smokes locais
  passaram. O preflight vincula SHA integral, `/version`, papéis e secrets,
  RepoDigest, utilizador não-root e labels OCI; o build de promoção exige SBOM
  e provenance BuildKit. Os IDs observados são apenas locais: faltam
  provider/registry, digests publicados, verificação de attestations/assinatura,
  DNS/ACME, secret manager, migrations e jornadas remotas, CI do RC e fecho do
  PR-18; por isso G4 permanece vermelho;
- PR-20 avançou de `pending` para `in_progress`: Prometheus, Alertmanager e
  Grafana estão fixados por digest numa rede interna, com 4 SLIs, 5 alertas,
  dashboard de 7 painéis, catálogo e runbooks. Promtool validou 10 regras e
  firing/resolução temporal, amtool validou o routing e Grafana iniciou com o
  dashboard provisionado. Identificadores tenant/user/document/event são
  proibidos como labels. Faltam deploy, canal real de alerta, traces/logs
  centralizados, error budget de 30 dias, carga PR-22 e on-call; G4 continua
  vermelho;
- PR-20 ganhou um agregador fail-closed para os cinco controlos G4. O bundle
  exige 12 JSON físicos no SHA: métricas/dashboard, logs/PII, traces/PII, cinco
  drills de alertas e janela SLO. Valida retenção, correlação, três serviços,
  firing->delivery->ack->resolved, cobertura de 30 dias e objectivos canónicos.
  Os 5 testes, Ruff e Pyright passaram; o template mantém os cinco controlos
  falsos e nenhum stack/canal/RC remoto foi certificado;
- PR-21 avançou de `pending` para `in_progress`: tooling fail-closed produz
  dump PostgreSQL custom, manifesto SHA-256 e arquivo restic cifrado, restaura
  apenas em alvo novo `rotas_dr_*` e valida revision, tabelas, FORCE RLS e
  equilíbrio contabilístico. Um drill local não-produção arquivou 29,8 MB,
  passou `restic check --read-data` e restaurou `rec13` em 58,338 s, com 123
  tabelas, 113 FORCE RLS, zero diários desequilibrados e cleanup confirmado.
  A política propõe RPO 15 min/RTO 4 h e retenção versionada. Faltam PITR/WAL,
  storage object-locked/cross-region, dados/volume reais, Governance e
  observabilidade, operador independente, falha de região e aprovação formal;
  G4 permanece vermelho;
- PR-21 ganhou um agregador fail-closed para os quatro controlos G4. Exige 11
  JSON físicos no SHA, restore de ROTAS/Governance/observabilidade, FORCE RLS,
  diários e cinco jornadas; PITR/WAL com perda <=15 min; réplica cross-region
  object-locked; e RTO <=240 min reconciliado com timestamps. Os 5 testes,
  Ruff e Pyright passaram. O template mantém quatro controlos falsos porque
  nenhum DR staging/RC, operador independente ou falha de região foi executado;
- PR-22 avançou de `pending` para `in_progress`: budgets versionados e gate
  HTTP secret-safe cobrem leitura, batch offline, corrida idempotente, rede
  degradada e soak, com validação bloqueante no CI. A baseline local entregou
  5.614 respostas HTTP esperadas, processou 500 operações sync sem falhas,
  preservou um único efeito sob 20 chamadas concorrentes e manteve zero stock
  negativo/diários desequilibrados. Contudo, leitura/soak ficaram em p95
  346-350 ms contra 200 ms, sync em 780,602 ms contra 500 ms e a corrida em
  2.080,793 ms; apenas a rede degradada client-side passou. Faltam profiling e
  optimização, `rotas_app`, dataset/runner externos, proxy TCP, dois tenants,
  observabilidade staging e soak de duas horas; G4 permanece vermelho;
- o incremento de optimização PR-22 consolidou a validação request-time de
  tenant/utilizador ou tenant/motorista/dispositivo numa consulta, sem cache,
  e tornou batches sync multi-operação uma única transação com fallback de
  corrida idempotente. Em perfil local production-like com quatro workers,
  JWT real e `rotas_app` restrita, sync melhorou para p95 521,481 ms e depois
  423,281 ms, mas a repetição teve 5% timeouts; a corrida preservou um efeito
  e caiu para 750,048 ms. Leitura aquecida chegou a 215,499 ms, ainda acima de
  200 ms, com duas timeouts. Uma alteração de pool sem ganho foi revertida.
  PR-22 e G4 continuam vermelhos até eliminar caudas/timeouts e passar no RC;
- a instrumentação diagnóstica PR-22, desligada por default e rejeitada em
  produção, decompôs tempos sem expor SQL ou identificadores. Leitura serial
  passou com p95 53,138 ms, enquanto concorrência 12 elevou p95 a 303,856 ms;
  auth p95 foi 130,886 ms e tenant lookup/RLS 101,504 ms. No sync, prefetch
  reduziu cinco SELECTs idempotentes a um e a mediana da fase de 47,737 para
  27,075 ms, mas outliers de sessão mantiveram p95 vermelho. Um snapshot de
  tenant que piorou auth para 323,902 ms foi revertido. A próxima prova exige
  runner externo, quatro workers RC e telemetria de pool/`pg_stat_statements`;
- PR-22 passou a expor ocupação, capacidade, checkouts e invalidações dos
  pools `application`, `administrative` ou `shared`, sem labels de tenant,
  utilizador, query ou conexão. O dashboard PR-20 tem agora oito painéis e o
  runbook obriga a correlacionar pool, SQL, auth, tenant lookup e RLS antes de
  tuning. A topologia local foi depois restaurada em PostgreSQL 55432/Redis
  6381 e exercitada com quatro workers, JWT real, `rotas_app` restrita e 42.048
  tenants sintéticos. Três leituras de 600 pedidos/concorrência 12 produziram
  p95 250,521 ms, 142,951 ms e 322,902 ms; a última teve 9 `ReadTimeout`
  (1,5%). Um drill amostrado observou no máximo 2/15 conexões application e
  1/15 administrative no processo atingido, sem saturação evidente. O gate
  passou a persistir tipos de erro e amostragem process-visible. A
  variabilidade, a ausência de `pg_stat_statements`, a capacidade de pool
  diferente de produção e a falta de agregação multiprocess mantêm PR-22
  vermelho; runner externo, quatro workers RC, dois tenants e soak continuam
  pendentes;
- a agregação Prometheus multiprocess do PR-22 foi implementada e exercitada
  numa imagem Linux local bloqueada: quatro workers expuseram capacidade
  agregada 20/20 para os pools application/administrative e o restart PID
  26 -> 85 eliminou a série `livesum` morta sem alterar a capacidade. O lock
  Python 3.11/Linux possui 24 dependências directas, 69 pacotes e 1902 hashes;
  Docker instala com `--require-hashes` e `pip check` passou dentro da imagem.
  O Image ID local é
  `sha256:0fc81e0cfc25b1fdc64a2ed31edc75751d691df42cc7b21ac7474273a1455296`,
  mas não substitui RepoDigest/SBOM/attestation de registry;
- a curva local dessa imagem passou em concorrência 1 com p95 135,792 ms, mas
  falhou em concorrência 4/8/12 com p95 395,153/942,881/686,902 ms. A execução
  c12 amostrada teve p95 504,025 ms, 600/600 HTTP 200 e apenas 4/20 conexões
  application e 3/20 administrative, afastando saturação de pool como causa
  primária. Runner externo, CPU/event loop, `pg_stat_statements`, dois tenants,
  soak de duas horas e reprodução no RC continuam pendentes; PR-22 e G4
  permanecem vermelhos;
- para explicar o joelho de concorrência sem tuning especulativo, PR-22 passou
  a medir atraso do event loop por `livemax` e CPU agregada dos workers por
  `livesum`, sem labels. O gate inclui p95/máximo dessas séries no relatório e
  o dashboard PR-20 passou a 10 painéis. Um primeiro drill rejeitou `max`
  porque deixou cinco ficheiros após restart; a correcção `livemax`, na imagem
  local
  `sha256:85ea2b57a2bd67d2a302fb5f7a278aab7415f9457ef46e35a65d88f9fdc41e71`,
  manteve quatro séries antes/depois do restart worker 25 -> 57. Vinte testes,
  Ruff, Pyright e validadores passaram. O contrato staging agora exige
  explicitamente runner externo, dois tenants, `pg_stat_statements` e estas
  métricas; a prova real continua pendente e não altera G4;
- o gate RC do PR-22 passou a distinguir fragmento de carga de contexto de
  release: seleccionar `staging_certification` produz apenas
  `release_evidence_fragment`. A validação final exige SHA integral,
  RepoDigest, HTTPS, runner externo, papel `rotas_app`, dois tenants distintos,
  quatro cenários por tenant, telemetria em todos os oito fragmentos,
  checks internos verdadeiros, SHA do RC, `pg_stat_statements` sem texto SQL e
  soak observado >= 7.200 s com zero Sev-1/Sev-2. O gerador rejeita endpoints
  locais/HTTP e volumes abaixo do perfil. Testes, Ruff, Pyright e o validador
  passaram localmente;
  nenhum bundle RC foi alegado e G4 permanece vermelho;
- G4 passou a possuir um decisor canónico fail-closed para PR-18 a PR-25. O
  manifesto solicita `GO`, mas a ferramenta exige todos os controlos
  canónicos, pelo menos um artefacto físico com SHA-256 válido por workstream e
  os 17 sign-offs dos papéis responsáveis. Controlo vermelho, hash divergente,
  workstream ausente ou aprovação incompleta produz `NO-GO` e exit code 1.
  Três testes e Ruff passaram; o template deliberadamente incompleto mantém a
  decisão actual `NO-GO` e PR-26 bloqueado;
- PR-18 passou a ter auditoria/SBOM machine-readable. A resolução raiz
  `esbuild@0.28.0` separou Vite 8 do `esbuild@0.21.5` usado por Vite 5,
  eliminou o único problema de `npm ls --all` e desbloqueou um CycloneDX 1.5
  com 787 componentes e hash canónico. Manager 89, Driver 26, typechecks e
  builds passaram. Contudo, produção continua com 3 high, o grafo completo
  com 17 high/1 moderate, o runtime local é Node 24 e o SBOM não está
  attested. PR-18 permanece `blocked_upstream` e G4 continua vermelho;
- o gate PR-18 foi reconciliado com a política do próprio plano para excepções
  formais: a V2 enumera findings exactos, rejeita divergência entre contagens e
  detalhes do audit e só cobre `high` com manifesto no SHA do RC, owner, ticket,
  controlos compensatórios, validade máxima de 30 dias e aprovações SEC/TL
  distintas. `critical` não é waivable. Nenhum waiver real foi criado; a
  execução Node 20 continua NO-GO com 3 findings de produção e 13 completos;
- a nova consulta ao registry confirmou o plateau upstream: Next 16.2.12 ainda
  é o latest estável e mantém PostCSS 8.4.31/Sharp 0.34.5. As correcções do npm
  são downgrades para Next 9, OpenAPI TypeScript 6 ou Workbox/PWA antigos. O
  ensaio isolado de OpenAPI TypeScript 6.7.6 perdeu `--check` e alterou o
  contrato gerado de 23.250 para 16.862 linhas; foi rejeitado. Nenhuma
  dependência foi alterada e PR-18 continua `blocked_upstream`;
- a exposição runtime PR-18 foi reduzida sem mascarar o audit: o Manager não
  usa `next/image`, passou a desactivar o optimizador e o build fail-closed
  remove Sharp/libvips do standalone, mantendo também PostCSS ausente. O
  runtime local iniciou sem esses pacotes, `/login` devolveu 200 e
  `/_next/image` 404; 89 testes, 14 gates, typecheck e build de 72 páginas
  passaram. A primeira construção Docker Linux caiu por `RPC EOF`; a segunda
  concluiu `npm ci` com 859 pacotes, mas expôs um download tardio do SWC que
  falhou por DNS. O contrato passou então a fixar
  `@next/swc-linux-x64-gnu@16.2.12` como optional dependency directa/lockada,
  executar `npm ci --include=optional`, verificar fisicamente o binário e
  compilar com `--network=none`. O dry-run npm e quatro testes do contrato
  passaram. A reconstrução Linux corrigida instalou 860 pacotes, compilou 72
  páginas offline e produziu a imagem local
  `sha256:3ad89e88e1293629f77d3eaa7d3163c9b583f57cd18b5f93f5965a0606c4933f`.
  A inspeção não encontrou Sharp, PostCSS ou `@img/sharp-*`; o manifesto foi
  lido dentro da imagem e o smoke confirmou `/login` 200 e `/_next/image`
  404. Como os labels ainda são `dev`/`unknown` e não há registry, RepoDigest
  de RC, assinatura ou attestation, a mitigação continua por provar no RC
  antes de qualquer waiver;
- PR-19 ganhou um gate de supply chain fail-closed para as quatro imagens:
  cada RepoDigest deve ter assinatura ligada à identidade CI/issuer exactos,
  transparência, SBOM SPDX, provenance SLSA v1 `max`, scanner zero
  high/critical e admissão do mesmo digest. Cada uma das cinco provas por
  imagem precisa de ficheiro físico, hash SHA-256 e SHA do release. O contrato
  passou 5 testes, Ruff e Pyright; o template continua NO-GO porque não existem
  registry/RC, Cosign, attestations, scanner ou admission reais. PR-19
  permanece `in_progress` e G4 vermelho;
- o gate runtime PR-19 passou a agregar os quatro controlos do G4. Exige nove
  outputs físicos: supply chain, quatro probes TLS/HSTS, secret manager, duas
  migrations one-shot e runtime. Valida 18 secrets por ficheiro, validade TLS
  residual, ordem migrations->aplicações, `/version`, `/health/deep`, heartbeat
  e `rotas_app` sem superuser/BYPASSRLS. Os 4 testes, Ruff e Pyright passaram,
  mas o template retorna NO-GO e nenhum staging/RC remoto foi executado;
- PR-23 avançou de `pending` para `in_progress`: o modelo versionado fixa a
  hierarquia operador ROTAS -> tenant independente -> clientes próprios do
  tenant e cobre 12 trust boundaries, 10 activos, 16 ameaças STRIDE, quatro
  classes de dados e oito fluxos de privacidade. O gate fail-closed e oito
  testes impedem alterar a hierarquia, omitir riscos/fluxos, falsificar scores,
  pré-fechar ameaças, alegar pentest ou introduzir padrões de segredo. Rules of
  Engagement e critérios de reteste foram definidos, mas PR-18/PR-19, JIT
  support, política/parecer jurídico e pentest independente no SHA do RC
  continuam pendentes; todos os riscos são release-blocking e G4 permanece
  vermelho;
- PR-23 ganhou um agregador fail-closed para pentest independente, findings e
  privacidade. Exige nove JSON físicos no SHA, quatro RepoDigests, nove papéis,
  doze superfícies, 16 ameaças exercitadas, reteste integral e zero
  high/critical; o parecer MZ cobre dez controlos e oito fluxos. Os 5 testes,
  Ruff e Pyright passaram. O template mantém três controlos falsos e a baseline
  de ameaças continua aberta porque pentest/parecer RC não foram executados;
- PR-24 avançou de `pending` para `in_progress`: um gate bloqueante percorre
  167 TSX, axe A/AA cobre Torre, Oficina, OS, Viaturas e Motoristas, e a suite
  local contra FastAPI/PostgreSQL terminou 17/17 sem skips. Foram corrigidos
  contraste, landmark/skip link, regiões scrollable, target size, tabs com
  roving focus, pareamento Driver e o drawer Hub 360; a execução com dados
  sintéticos também revelou e fechou o crash de billing paginado e o scorecard
  de dados insuficientes. Manager passou 89 testes e build de 72 rotas; Driver
  passou 26 testes e build PWA. Auditoria manual com tecnologias assistivas,
  mobile real, zoom/reflow/forced-colors, todas as rotas/papéis, dois tenants e
  reprodução no RC continuam pendentes; PR-24 e G4 não estão verdes;
- PR-25 avançou de `pending` para `in_progress`: a política e o runbook de
  resposta a incidentes ligam PR-20, PR-21, segurança, performance e promoção
  num contrato com quatro severidades, seis papéis, sete estados e cinco
  cenários. Roster e paging são externos, comunicação pública exclui
  identificadores e a comunicação dirigida é isolada por tenant. O validador,
  quatro testes e o tabletop local passaram, mas o relatório fixa
  `local_control_plane_only` e `gate_effect: none`. Paging/escalonamento
  humanos, staging no RC, injeção de falhas, recuperação/RPO/RTO medidos,
  operador independente e sign-off SRE/PO/QA continuam obrigatórios; PR-25 e
  G4 não estão verdes;
- produtores criticos ja persistem no transactional outbox e nao existem
  chamadas `asyncio.create_task` no backend para integracoes;
- contrato Governance, HTTP 409 idempotente, retry e isolamento de lote por
  savepoint estao testados localmente;
- reserva HTTP, mutacao, audit/outbox e resposta idempotente partilham agora
  uma unica transacao; rollback e concorrencia foram provados, e commits de
  sessoes auxiliares permanecem independentes;
- notas de debito e credito usam idempotencia HTTP e confirmam documento
  fiscal com audit na mesma transacao; pagamento a fornecedor usa lock,
  controlo de saldo, diario, audit e idempotencia na mesma unidade de trabalho;
- exports de faturacao e compliance persistem `ExportJob` e dispatch no
  transactional outbox; indisponibilidade de Redis passa a retry e a entrega
  ARQ usa identificador deterministico;
- a particao financeira integrada passou `83 passed`; a instancia historica
  `55432` foi reconciliada de `92c11f6fdf9d` ate `rec11` sem `stamp`, com
  fingerprints estruturais, `alembic check`, 12 testes financeiros/outbox e
  18 testes RLS/roles verdes;
- uma base descartavel criada de `template0` migrou do zero ate `rec11` e foi
  removida apos o gate; `rec11` tambem restaurou os 10 indices compostos
  database-managed ausentes em `5440`, com testes 3/3 e `alembic check`
  verdes em `5440` e `55432`;
- apos `rec12`, novo zero-to-head descartavel terminou em `rec12` sem drift e
  a base de gate foi removida;
- `rec13` corrigiu identidade UUID e timestamps de auditoria do inventario;
  passou em `5440`, `55432` e num novo zero-to-head descartavel sem drift;
- PR-05 tem ensaio sintetico com dados `95929ae669b9 -> rec11`, com integridade
  contabilistica preservada e 23 testes verdes, e revalidacao tecnica vazia
  `95929ae669b9 -> rec13`: dump/restore/upgrade medidos, `alembic check` verde,
  43 amostras de lock sem waits e regressao focada 26/26. Foram observados
  `AccessExclusiveLock` e outros locks fortes; snapshot real anonimizado,
  volume/carga de staging e rollback independente continuam obrigatorios;
- o runbook PR-05 agora exige confirmacao de anonimizacao, destino descartavel,
  secrets apenas no ambiente, `lock_timeout`, `statement_timeout`, monitor de
  locks e cleanup verificado; o head padrao e agora `rec13` e o smoke
  endurecido terminou nessa revisao sem drift;
- em 2026-08-08, o PR-05 foi isolado no commit `51d3216`, draft PR 11 sobre a
  PR-04. O gate passou a exigir classe e evidência aprovada de anonimização,
  rejeitar PII, fixar `DATABASE_URL` e `ALEMBIC_DATABASE_URL` no destino e
  comparar o fingerprint antes/depois. O novo smoke sintético
  `95929ae669b9 -> rec13` preservou o fingerprint, observou 34 amostras sem
  waits e a suíte backend terminou `532 passed, 1 skipped`. Isto não certifica
  PR-05: snapshot real autorizado, volume/carga representativos e rollback por
  operador independente permanecem obrigatórios. Backend/Frontend remotos não
  iniciaram devido ao billing lock; billing não foi alterado;
- em 2026-08-08, PR-06 foi isolado no commit `896a157`, draft PR 12 sobre
  PR-05. O arranque produção passou a validar a role real de `DATABASE_URL`, o
  CI recebeu auditor RLS fail-closed e login direto `rotas_app`, e a base local
  apresentou 114 tabelas tenant-scoped sem gaps de ENABLE/FORCE RLS, policy ou
  grants. Os testes focados passaram 29/29 e o backend completo 546/546, com um
  skip esperado. Esta prova é local; CI remota, revisão e RC ainda faltam;
- G3 permanece incompleto ate a operação local de DLQ/replay/alertas ser
  reproduzida contra Governance real e staging, e existir certificacao offline
  do Driver no SHA do release candidate.

O principio de promocao e:

```text
codigo presente != capacidade provada != release promovivel
```

### 15.2 Premissas de planeamento

- O produto promovido e SaaS multi-tenant: tenant, cliente do tenant e operador
  SaaS sao contextos distintos em identidade, dados, permissoes e billing.
- Janela de referencia: 10 a 12 semanas.
- Equipa minima: Tech Lead/Arquitectura, Backend, Manager, Driver, QA/Security e
  Platform/SRE. Uma pessoa pode acumular funcoes, mas nenhuma funcao pode ficar
  sem owner explicito.
- Trabalho organizado em sprints de duas semanas, com um Sprint 0 curto.
- Nenhuma data comercial sobrepoe um gate tecnico.
- Durante P0 e P1, novas features ficam congeladas, excepto correcoes exigidas
  por um gate.
- Cada entrega deve apontar para commit, teste, log de CI ou artefacto
  operacional reproduzivel.
- Evidencia obtida apenas com mocks nao fecha um gate de runtime, dados,
  seguranca ou integracao.

### 15.3 Funcoes responsaveis

| Codigo | Funcao | Responsabilidade de promocao |
| --- | --- | --- |
| TL | Tech Lead / Arquitectura | Contratos, fronteiras, ADRs, integracao e decisao tecnica. |
| BE | Backend | Dominios, transaccoes, migrations, RLS, outbox e API. |
| FE-M | Frontend Manager | BFF, sessao, UX administrativa e contratos TS. |
| FE-D | Frontend Driver | PWA, offline, sync, cache e experiencia de campo. |
| QA | QA / Test Engineering | Estrategia de testes, regressao, E2E, carga e evidencias. |
| SEC | Security | Threat model, supply chain, auth, pentest e privacidade. |
| SRE | Platform / SRE | CI/CD, ambientes, observabilidade, backup, DR e operacao. |
| PO | Produto / Operacoes | Fluxos reais, piloto, suporte, SLA e aceite de negocio. |

Os nomes das pessoas devem ser associados a estas funcoes no Sprint 0.

### 15.4 Sequencia vinculativa

```text
P0 Integridade
  -> P1 Dados e fronteiras de seguranca
  -> P2 Confiabilidade e integracoes
  -> P3 Operacao, desempenho e seguranca premium
  -> P4 Piloto, soak e promocao
```

P2 pode iniciar preparacao durante P1, mas nenhum gate posterior pode ser
declarado verde se o gate anterior estiver vermelho.

### 15.5 Plano de execucao

| ID | Entrega | Owner | Depende de | Evidencia de conclusao | Gate |
| --- | --- | --- | --- | --- | --- |
| PR-00 | Nomear owners, congelar features e criar release ledger | TL + PO | - | Owners, branch policy e ledger aprovados | G0 |
| PR-01 | Eliminar erros semanticos Ruff e fechar lint integral | BE | PR-00 | Ruff verde no mesmo commit candidato | G0 |
| PR-02 | Instalar Pyright e tipagem Python no CI | BE + QA | PR-01 | Pyright verde e blocking no CI | G0 |
| PR-03 | Estabilizar Vitest Manager e particionar suites lentas | FE-M + QA | PR-00 | Zero unhandled errors, timeouts definidos | G0 |
| PR-04 | Provar migrations em base vazia | BE + SRE | PR-01 | `upgrade head`, smoke e schema audit verdes | G1 |
| PR-05 | Provar upgrade de snapshot `95929ae669b9 -> rec13` | BE + SRE | PR-04 | Relatorio, duracao, locks e forward-fix ensaiado | G1 |
| PR-06 | Validar RLS/GRANT e integridade tenant-scoped com role restrita real | BE + SEC + QA | PR-04 | Suite cross-tenant por tabela, relacao, job, ficheiro e operacao | G1 |
| PR-07 | Remover auto-activacao de modulos pagos | BE + PO | PR-04 | Entitlement controlado por plataforma/billing | G2 |
| PR-08 | Completar `Browser -> BFF -> API` | FE-M + BE | PR-00 | Zero access token em `localStorage`; chamadas directas inventariadas = 0 | G2 |
| PR-09 | Gerar cliente Manager a partir de OpenAPI versionado | BE + FE-M | PR-08 | Drift check e tipos gerados no CI | G2 |
| PR-10 | Centralizar timeout, erros, retry e idempotencia HTTP | FE-M + FE-D | PR-09 | Contract tests e comportamento uniforme | G2 |
| PR-11 | Adoptar Unit of Work por caso de uso critico | TL + BE | PR-01 | Mutacao, audit, movimentos e outbox atomicos | G3 |
| PR-12 | Ligar produtores ao transactional outbox | BE | PR-11 | Zero `create_task` em integracoes criticas | G3 |
| PR-13 | Corrigir contrato ROTAS -> Governance | BE + TL | PR-12 | Endpoint, auth e schema validados em teste real | G3 |
| PR-14 | Operacionalizar retry, DLQ e reconciliacao | BE + SRE | PR-13 | Painel/CLI, metricas, alertas e replay idempotente | G3 |
| PR-15 | Fechar lifecycle offline do Driver | FE-D + BE | PR-10 | Cold start, refresh, backoff, conflito e dead-letter | G3 |
| PR-16 | Isolar cache por tenant, driver e sessao | FE-D + SEC | PR-15 | Testes de logout/troca de identidade sem leakage | G3 |
| PR-17 | Remover demo fallback do modo producao | FE-M + PO + QA | PR-09 | Zero dados demo em journeys de release | G3 |
| PR-18 | Corrigir vulnerabilidades e criar policy de dependencias | SEC + TL | PR-00 | Zero critical/high; excepcoes com prazo e owner | G4 |
| PR-19 | Preparar staging equivalente a producao | SRE | PR-04 | IaC, secrets, TLS, imagens imutaveis e migrations | G4 |
| PR-20 | Instrumentar SLI/SLO e alertas | SRE + BE + FE | PR-19 | Dashboards, traces e alertas testados | G4 |
| PR-21 | Executar backup/restore e DR | SRE + QA | PR-19 | Restore cronometrado; RPO/RTO aprovados | G4 |
| PR-22 | Carga, concorrencia, soak e rede degradada | QA + SRE | PR-15 + PR-20 | Relatorio contra budgets de performance | G4 |
| PR-23 | Threat model, privacidade e pentest | SEC + TL | PR-18 + PR-19 | Findings high/critical fechados | G4 |
| PR-24 | Uniformizar UX, erros e acessibilidade | FE-M + FE-D + PO | PR-17 | WCAG 2.2 AA e jornadas principais aprovadas | G4 |
| PR-25 | Runbooks, on-call, suporte e incident response | SRE + PO | PR-20 + PR-21 | Game day executado e escalacao validada | G4 |
| PR-26 | Piloto real controlado | PO + QA + SRE | G4 verde | Tenant/driver reais, dados autorizados e suporte activo | G5 |
| PR-27 | Soak de release e decisao GO/NO-GO | Todos | PR-26 | Janela estavel, ledger completo e sign-off | GO |

### 15.6 Fases e resultados esperados

#### P0 - Integridade de engenharia (Sprint 0 a Sprint 1)

Objectivo: voltar a confiar no commit candidato.

Inclui PR-00 a PR-03 e PR-18 iniciado. Resultado obrigatorio:

- CI sem etapas vermelhas ou ignoradas;
- Ruff e typecheck blocking;
- testes deterministas;
- builds reproduziveis;
- inventario de vulnerabilidades e owners;
- release ledger criado.

Saida: G0 verde. Nenhuma promocao para staging enquanto G0 estiver vermelho.

#### P1 - Dados, contratos e seguranca (Sprints 2 e 3)

Objectivo: provar isolamento, migrabilidade e uma unica fronteira de acesso.

Inclui PR-04 a PR-10. Resultado obrigatorio:

- migrations provadas em dois caminhos;
- RLS/GRANT e referencias tenant-scoped exercidos com role real;
- entitlements fora do controlo do tenant;
- BFF como fronteira unica do Manager;
- OpenAPI como contrato executavel;
- zero segredo/token de sessao acessivel ao browser fora do desenho aprovado.

Saida: G1 e G2 verdes.

#### P2 - Confiabilidade do produto (Sprints 4 e 5)

Objectivo: impedir perda silenciosa, duplicacao e inconsistencias.

Inclui PR-11 a PR-17. Resultado obrigatorio:

- unidade de trabalho nos fluxos financeiros, stock, oficina e excepcao;
- Governance entregue por outbox real;
- DLQ e reconciliacao operaveis;
- offline lifecycle completo;
- cache isolado por identidade;
- modo producao sem dados demo.

Saida: G3 verde.

#### P3 - Operacao premium (Sprints 6 a 8)

Objectivo: tornar o sistema operavel sob falha e carga reais.

Inclui PR-18 a PR-25. Resultado obrigatorio:

- staging production-like;
- observabilidade ponta a ponta;
- vulnerabilidades high/critical fechadas;
- backup/restore e DR comprovados;
- performance dentro dos budgets;
- pentest aprovado;
- UX e acessibilidade verificadas;
- runbooks e on-call exercitados.

Saida: G4 verde.

#### P4 - Piloto e promocao (Sprints 9 e 10)

Objectivo: provar valor e estabilidade com uso real controlado.

Inclui PR-26 e PR-27. O piloto nao pode usar mocks como prova e deve incluir:

- pelo menos um tenant autorizado em operacao e um segundo tenant controlado
  para provar isolamento;
- gestor e motorista reais;
- operacao completa de ordem a cobranca;
- rede instavel/offline no Driver;
- excecao operacional e reprocessamento Governance;
- backup da janela e restore ensaiado;
- suporte e observabilidade activos.

Saida: G5 verde e reuniao formal GO/NO-GO.

### 15.7 Gates de promocao

#### G0 - Source and Build Integrity

- Ruff, Pyright, typecheck, testes e builds verdes no mesmo SHA.
- Zero `F821`, `F823` ou `F811`.
- Zero unhandled errors nos test runners.
- Branch protection impede merge com gate vermelho.

#### G1 - Data Integrity

- Base vazia sobe ate `head`.
- Snapshot suportado sobe ate `head` sem perda.
- RLS/GRANT passam com role de runtime real.
- Constraints impedem referencias cross-tenant em todas as relacoes criticas.
- Restore de base reproduz dados e invariantes.

#### G2 - Contract and Security Boundary

- OpenAPI drift check verde.
- BFF e a unica fronteira browser/API do Manager.
- Zero access token em `localStorage`.
- Entitlements sao controlados por plataforma/billing.
- Cliente do tenant nunca e tratado como identidade global.
- Acesso de suporte e explicito, temporario, limitado e auditado.
- Matriz RBAC tem teste positivo e negativo.

#### G3 - Reliability and Offline

- Outbox e atomico com a mutacao de negocio.
- Governance aceita o contrato real e devolve identificador persistido.
- Retry, DLQ, replay e reconciliacao sao idempotentes.
- Driver funciona em cold start offline dentro do escopo aprovado.
- Cache nao atravessa tenant, driver, logout ou troca de sessao.

#### G4 - Production Operations

- Zero vulnerabilidades critical/high sem waiver formal e prazo.
- Backup/restore, DR, alertas e game day aprovados.
- P95 de leitura < 200 ms e sync batch < 500 ms nas condicoes acordadas;
  budgets alternativos exigem sign-off de Produto e SRE.
- Sem findings high/critical abertos no pentest.
- Runbooks, on-call e suporte estao activos.

#### G5 - Pilot Evidence

- Todas as jornadas criticas passam com servicos e dados reais.
- Isolamento e provado entre dois tenants, incluindo API, cache, ficheiros,
  workers, exports e analytics.
- Sete dias consecutivos de CI verde no branch de release.
- Janela de soak sem incidente Sev-1/Sev-2 nao resolvido.
- Produto, Engenharia, Seguranca e Operacoes assinam o ledger.

### 15.8 Release ledger obrigatorio

Cada release candidate deve manter uma tabela deste formato:

| Gate | Estado | SHA/versao | Evidencia | Owner | Data | Excepcao/prazo |
| --- | --- | --- | --- | --- | --- | --- |
| G0 | red/yellow/green | - | link CI/artefacto | - | - | - |
| G1 | red/yellow/green | - | migration/restore report | - | - | - |
| G2 | red/yellow/green | - | contract/security report | - | - | - |
| G3 | red/yellow/green | - | reliability/offline report | - | - | - |
| G4 | red/yellow/green | - | ops/security/performance | - | - | - |
| G5 | red/yellow/green | - | pilot/soak report | - | - | - |

`green` significa evidencia reproduzida no release candidate. `yellow` nunca
equivale a GO; apenas identifica trabalho em curso ou risco aceite antes da
reuniao de promocao.

### 15.9 Politica GO/NO-GO

GO exige simultaneamente:

1. G0 a G5 verdes no mesmo release candidate.
2. Zero risco critical/high sem mitigacao efectiva.
3. Nenhuma migration, flag ou dependencia manual nao documentada.
4. Rollback/forward-fix, backup e restore executaveis pela equipa de operacao.
5. Sign-off de TL, SEC, SRE e PO.

Qualquer gate vermelho produz NO-GO automatico. Um prazo comercial pode mudar a
data de release, mas nao pode mudar esta regra.

### 15.10 Primeira fila de execucao

O trabalho inicia por esta ordem, sem abrir novas features:

1. PR-00: owners, freeze e release ledger.
2. PR-01: corrigir `F821`, `F823` e `F811`; depois fechar o restante Ruff.
3. PR-04/PR-05: migrations em base vazia e snapshot.
4. PR-03: estabilizar Vitest Manager.
5. PR-18: actualizar Next/Sentry e fechar vulnerabilidades high.
6. PR-07/PR-08: entitlements e BFF-only.
7. PR-11/PR-12/PR-13: Unit of Work, outbox e contrato Governance.

Esta fila fecha primeiro os riscos que hoje impedem qualquer evidencia confiavel
de producao.

### 15.11 Replaneamento vinculativo frontend-backend — 2026-08-20

A auditoria real registada no Issue #42 e em
`docs/evidence/FRONTEND_BACKEND_E2E_AUDIT_20260820.md` confirmou endpoints
órfãos, falso estado vazio/sucesso, erros técnicos expostos e ausência de build
reproduzível do Driver na toolchain atual. Por isso:

1. novas features continuam congeladas;
2. PR-08, PR-09, PR-10, PR-15, PR-17 e PR-24 não podem ser tratados como
   fechados por evidência local anterior; ficam reabertos para convergência no
   release candidate;
3. Issue #42 torna-se a fila técnica imediata, nesta ordem:
   toolchain/RC -> ledger de fluxos e contratos -> contratos estruturais ->
   erros fail-closed -> RBAC/tenant/idempotência -> estados uniformes ->
   fluxos F-01 a F-14 -> revisão/CI/staging;
4. G2 permanece amarelo, G3 permanece amarelo, G4 permanece vermelho e a
   decisão global continua NO-GO;
5. nenhuma capacidade é comercialmente apresentável enquanto o respetivo
   percurso frontend -> BFF -> backend -> PostgreSQL -> resposta UI não tiver
   teste positivo, negativo e evidência no mesmo SHA.

Critério de recuperação: zero referências HTTP órfãs; schemas request/response
não vazios; zero 4xx/5xx silencioso; mutações críticas com replay e conflito
idempotente; matriz RBAC e tentativas cross-tenant reais; Governance com
contrato/BFF próprios; Manager e Driver reproduzíveis em Node 20; fluxos F-01 a
F-14 comprovados conforme `docs/FRONTEND_REFOUNDATION_PLAN.md`; CI remota com
jobs efetivamente executados.

## 16. Programa Integrado ERP e Business Intelligence

### 16.1 Mandato

Este programa executa as Waves 9 a 13 depois da estabilizacao aplicavel da Wave
8. E a continuacao do mesmo roadmap canonico, nao uma iniciativa paralela. O
ERP e a base transaccional obrigatoria; BI, dashboards e alertas sao promovidos
apenas depois de as respectivas fontes de verdade estarem reconciliadas.

Desenho e spikes podem iniciar antes de G4, mas novas capacidades de negocio nao
entram no branch de release enquanto o feature freeze da seccao 15 estiver
activo. Nenhum gate ERP/BI fica verde usando apenas mocks ou componentes
presentes no codigo.

### 16.2 Sequencia vinculativa

```text
G0-G3 de estabilizacao verdes
  -> E0 Fronteira SaaS e master data
  -> E1 Compras, inventario e AP
  -> E2 Vendas, AR, contabilidade e tesouraria
  -> E3 RH, payroll e activos
  -> E4 Camada semantica, dashboards e alertas
  -> E5 Piloto ERP/BI, fecho e certificacao
```

Trabalho preparatorio pode correr em paralelo, mas aceite e promocao respeitam
esta ordem.

### 16.3 Plano de Entregas

| ID | Entrega | Owner | Depende de | Evidencia de conclusao | Gate |
| --- | --- | --- | --- | --- | --- |
| ERP-00 | ADR de tenancy, entidades legais, ownership e dois billings | TL + BE + PO | G0-G2 | Modelo aprovado, threat model e contratos versionados | E0 |
| ERP-01 | Lifecycle de tenant, subscricao, entitlement e limites | BE + FE-M + SEC | ERP-00 | Provision/suspend/reactivate/offboard E2E | E0 |
| ERP-02 | Constraints, RLS, storage, cache e workers tenant-scoped | BE + SEC + QA | ERP-00 | Matriz cross-tenant real verde | E0 |
| ERP-03 | Entidades legais, filiais, centros de custo e sequencias | BE + FE-M | ERP-01 | CRUD, RBAC, auditoria e isolamento verdes | E0 |
| ERP-04 | Master data de clientes, fornecedores, artigos e colaboradores | BE + FE-M + PO | ERP-03 | Duplicados controlados e imports auditaveis | E0 |
| ERP-05 | Requisicao, cotacao, aprovacao e purchase order | BE + FE-M + PO | ERP-04 | Jornada real com segregacao de funcoes | E1 |
| ERP-06 | Recepcao, devolucao, inventario unificado e contagem | BE + FE-M + QA | ERP-05 | Stock atomico, concorrencia e reconciliacao | E1 |
| ERP-07 | Factura fornecedor, three-way match, AP e pagamento | BE + FE-M + QA | ERP-06 | P2P completo sem duplicacao | E1 |
| ERP-08 | Propostas, contratos, vendas, facturas, AR e recebimentos | BE + FE-M + PO | ERP-04 | O2C completo ligado a TMS/oficina | E2 |
| WKS-01 | Lifecycle canonico da oficina, snapshots e migracao dos estados legados | TL + BE + PO | G1 + ERP-04 | Matriz de transicoes, migration/backfill e invariantes aprovados | E2 |
| WKS-02 | Recepcao, diagnostico, checklists, fotos e aceite multicanal | BE + FE-M + PO | WKS-01 | Jornada agendada/walk-in real e auditavel | E2 |
| WKS-03 | Orcamento original/suplementar, aprovacao e reservas fail-closed | BE + FE-M + QA | WKS-02 + ERP-06 | Concorrencia/retry e gates por item verdes | E2 |
| WKS-04 | Execucao, tempos, consumos, ferramentas e QC | BE + FE-M + QA | WKS-03 | Reconciliacao e retorno de QC E2E verdes | E2 |
| WKS-05 | Factura imutavel, pagamentos, entrega e preventiva | BE + FE-M + PO | WKS-04 + ERP-08 | Jornada ate ENTREGUE e documentos correctivos verdes | E2 |
| ERP-09 | Plano de contas, diarios automaticos, periodos e fecho | TL + BE + QA | ERP-07 + ERP-08 | Razao balanceado e fecho reproduzivel | E2 |
| ERP-10 | Caixa, bancos, reconciliacao e demonstracoes | BE + FE-M + PO | ERP-09 | AP/AR/bancos/razao reconciliados | E2 |
| HRM-00 | ADRs HRM, threat model, matriz legal e classificacao de dados | TL + SEC + PO | G0-G3 + ERP-00 | Boundaries, regras, fontes e plano expand-contract aprovados | E3 |
| HRM-01 | Organization, pessoa, worker, vinculo, job e posicao | BE + FE-M + PO | HRM-00 + ERP-03/04 | RLS real, invariantes temporais, migration e lifecycle E2E | E3 |
| HRM-02 | Workforce planning, position control e headcount budget | RH + FIN + BE | HRM-01 | Plan, budget, forecast e actual reconciliados | E3 |
| HRM-03 | Talent acquisition, candidate portal e offer | RH + FE-M + BE | HRM-01/02 | Requisition-to-offer, fairness e retencao E2E | E3 |
| HRM-04 | Onboarding, journeys e workforce lifecycle | RH + BE + IT | HRM-01/03 | Pre-hire, onboarding, mobility e offboarding E2E | E3 |
| HRM-05 | Compensation, benefits e total rewards | RH + FIN + BE | HRM-01/02 | Review cycle, budget, eligibility e approvals | E3 |
| HRM-06 | Calendario, escalas, ponto, ferias e disponibilidade | BE + FE-M + QA | HRM-01 | Offline, leave ledger, conflitos e reconciliacao | E3 |
| HRM-07 | Skills, learning e certificacoes | RH + BE + FE-M | HRM-01/04 | Learning, compliance e recertification E2E | E3 |
| HRM-08 | Goals, performance, feedback e calibration | RH + BE + FE-M | HRM-01/07 | Review, calibration, appeal e bias controls | E3 |
| HRM-09 | Career, mobility, talent review e succession | RH + BE + FE-M | HRM-02/07/08 | Critical-role coverage e mobility E2E | E3 |
| HRM-10 | HR Service Delivery, knowledge e employee journeys | RH + BE + FE-M | HRM-01/04 | Case SLA, privacy e service analytics | E3 |
| HRM-11 | Engagement, employee relations, OHS e wellbeing | RH + LEGAL + SEC | HRM-01/10 | Anonymity, investigation e safety E2E | E3 |
| HRM-12 | Envelope, outbox/inbox e adapters corporativos | TL + BE + QA | HRM-01 + WKS-04 | Contract, replay, backfill, DLQ e reconciliacao | E3 |
| HRM-13 | Rule engine, inputs e payroll run FSM | TL + BE + QA | HRM-05/06/12 + ERP-09 | Golden cases, memoria e hash reproduziveis | E3 |
| HRM-14 | Posting, tesouraria, pagamento e outputs legais | BE + FIN + QA | HRM-13 + ERP-10 | Payroll-to-ledger-to-bank reconciliado | E3 |
| HRM-15 | Candidate, employee, manager e HR workspaces | FE-M + BE + UX | HRM-03..14 | Journeys por persona, field auth e WCAG | E3 |
| ERP-12 | Inventario e lifecycle contabilistico de activos | BE + FE-M + QA | ERP-06 + ERP-09 | Custodia, depreciacao, transferencia e abate | E3 |
| BI-01 | Catalogo semantico e contratos de eventos/KPIs | TL + BE + PO | E1 + E2 | Formula, owner, fonte, versao e SLO aprovados | E4 |
| BI-02 | Projections, backfill, rebuild e reconciliacao | BE + SRE + QA | BI-01 + PR-12 | Read models idempotentes e tenant-scoped | E4 |
| BI-03 | Boards, drill-down, metas e filtros | FE-M + BE + PO | BI-02 | KPIs reconciliados e jornadas aprovadas | E4 |
| BI-04 | Alert lifecycle, escalacao e canais | BE + FE-M + SRE | BI-02 | SLA, acknowledge, resolve e replay testados | E4 |
| BI-05 | Oficina Intelligence Layer e rentabilidade prevista/realizada | BE + FE-M + PO | WKS-05 + BI-02 | Margem, aging, conversao e retrabalho reconciliados | E4 |
| BI-06 | Recomendacoes explicaveis e comandos humanos auditados | BE + FE-M + QA | BI-04 + BI-05 | Regra/modelo versionado; zero escrita analitica directa | E4 |
| BI-07 | Forecast e simulador Oficina Digital Twin | BE + FE-M + PO | BI-05 | Backtest, cenarios imutaveis, incerteza e aplicacao controlada | E4 |
| BI-08 | Model governance, assistente e benchmarking privacy-preserving | TL + BE + SEC + QA | BI-06 + BI-07 | RBAC, lineage, drift, coorte minima e red-team verdes | E4 |
| HRM-16 | Human capital reporting, KPI catalog e workforce analytics | RH + BE + BI | HRM-02..12 + BI-01/02 | ISO metrics, rebuild, drill-down e reconciliacao | E4 |
| HRM-17 | HR Intelligence e model governance | TL + BE + SEC + QA | HRM-16 + BI-06/08 | Fairness, red-team, appeal, fallback e decisao humana | E4 |
| HRM-18 | Migracao, piloto e certificacao enterprise HRM | Todos | HRM-00..17 | Lifecycle completo, soak, DR e sign-offs | E5 |
| ERP-13 | Piloto real, inventario, payroll e fecho mensal | Todos | E0-E4 verdes | Ledger ERP/BI, soak e sign-off | E5 |

### 16.4 Gates ERP/BI

#### E0 - SaaS Boundary

- Dois tenants exercitados com dados e identificadores sobrepostos.
- Zero leitura, mutacao, inferencia, cache, ficheiro ou evento cross-tenant.
- Platform Admin, Tenant Admin e suporte temporario possuem fronteiras provadas.
- Cliente do tenant, fornecedor e colaborador sao identidades tenant-scoped.
- Billing SaaS e billing operacional usam agregados, permissoes e diarios
  separados.

#### E1 - Procure-to-Pay and Inventory

- Requisicao ate pagamento passa com aprovacao e segregacao reais.
- Recepcao, devolucao, reserva, transferencia e contagem reconciliam o stock.
- Combustivel, pecas, ferramentas e inventario geral nao mantem saldos
  contraditorios.
- Concorrencia e retry nao criam stock negativo ou documentos duplicados.

#### E2 - Order-to-Cash and Financial Close

- Contrato/servico ate recebimento e diario passa ponta a ponta.
- Oficina percorre `RECEBIDO -> ENTREGUE` numa jornada real, com orcamento
  original e suplementar, reserva/consumo, QC, factura e pagamento
  reconciliados.
- Nenhum gate da oficina pode ser ultrapassado por API, worker, interface,
  concorrencia, retry ou papel sem permissao.
- Migracao/backfill dos estados legados preserva historico e identifica todo
  registo ambiguo para reconciliacao, sem promover estado por inferencia
  silenciosa.
- AP, AR, caixa, bancos e razao reconciliam no mesmo periodo.
- Diarios finalizados sao balanceados e append-only.
- Fecho, reabertura e correccoes sao autorizados e auditaveis.

#### E3 - People and Assets

- `docs/PRD_HRM_ROTAS.md` HRM-00 a HRM-15 possuem evidencia e sign-off.
- Pessoa, vinculo, posicao, compensacao e perfis operacionais nao sao fundidos;
  as ligacoes sao tenant-scoped, temporais e auditaveis.
- Workforce plan, position budget, recruiting, candidate, offer e onboarding
  fecham sem criar headcount ou person record por inferencia.
- Learning, performance, carreira, mobilidade, succession, rewards e benefits
  possuem workflows, contexto, appeal e maker-checker adequados.
- HR Service Delivery, engagement, employee relations e OHS provam SLA,
  anonimato, evidence chain e segregacao de dados restritos/medicos.
- Ponto offline, ferias, skills, certificacoes e disponibilidade reconciliam com
  TMS/Oficina sem duplicar factos.
- Payroll usa regra legal versionada, snapshot, memoria e hash reproduziveis.
- Payroll aprovado reconcilia com tesouraria, banco, contabilidade e outputs
  legais; retry nao duplica efeito.
- Diario de payroll so nasce depois de aprovacao; folha fechada so aceita ajuste
  referenciado.
- Segregacao de HR/payroll, field-level authorization e desligamento sao
  provados.
- Dois tenants com identificadores sobrepostos provam isolamento na API, RLS,
  ficheiros, cache, eventos, workers e exports.
- Cada activo possui owner, localizacao, valor e lifecycle reconstruivel.

#### E4 - Trusted BI

- KPIs tenant-scoped reconciliam com fontes transaccionais.
- Drill-down explica os agregados sem expor outro tenant.
- Freshness SLO, atraso, rebuild e reconciliacao sao observaveis.
- Alertas sao persistidos, accionaveis, escalaveis e auditaveis.
- Facto, previsao, recomendacao e simulacao sao distintos na API, persistencia e
  interface.
- Analytics nao possui permissao de escrita directa no schema transaccional.
- Accao recomendada aceite passa por comando de dominio autorizado, idempotente
  e auditado; rejeicao ou timeout nao muda o nucleo.
- Margem, retrabalho, conversao, aging e forecast da oficina possuem formula,
  lineage, owner, versao e evidencia de reconciliacao.
- Modelos possuem dataset/feature lineage, metrica de qualidade, limiar,
  monitorizacao de drift, fallback e rollback.
- Simulacoes sao imutaveis e nao se tornam plano/preco oficial sem aprovacao.
- Benchmark cross-tenant prova consentimento, anonimizacao, coorte minima e
  resistencia a inferencia.
- HRM-16 e HRM-17 passam reconciliacao, fairness, contestacao, fallback,
  kill switch e decisao humana; recomendacao nunca aplica decisao laboral
  adversa directamente.

#### E5 - ERP/BI Pilot Evidence

- Um tenant executa compras, vendas, stock, oficina, TMS, payroll e fecho mensal
  com dados autorizados reais.
- Um segundo tenant controlado prova isolamento durante a mesma janela.
- Inventario fisico, bancos, AP, AR, payroll e razao reconciliam.
- HRM-18 fecha migracao, lifecycle enterprise, payroll mensal, DR e sign-off de
  RH/Legal/Financas.
- Dashboards reproduzem o fecho e eventos operacionais dentro dos SLOs.
- Produto, Engenharia, Seguranca, Financas e Operacoes assinam o ledger.

Qualquer gate E0-E5 vermelho produz NO-GO para declarar o ROTAS um ERP/TMS SaaS
com BI incorporado, mesmo que modulos isolados estejam presentes ou tenham
testes unitarios verdes.

### 16.5 Atualizacao de execucao F7 — 2026-08-20

- F-05, F-08 e F-10 receberam correcoes locais de contrato e falso vazio;
- F-08 e F-10 passaram pela UI em Chrome isolado contra backend/PostgreSQL;
- F-09 passou contrato e efeito backend real, incluindo pagamento atomico, mas
  aguarda repeticao integral no browser;
- o seed PGC e o runtime financeiro passaram a convergir em `4.2`, `1.2` e
  `6.3`, preservando leitura dos codigos legados sem ponto;
- o ledger automatico ainda reporta 160 violacoes: sete operacoes ausentes e
  153 respostas OpenAPI sem schema;
- F-11 Governance permanece bloqueante ate existir decisao aprovada de BFF,
  identidade, tenant, credencial server-side, idempotencia e reconciliacao;
- testes locais: Manager 95/95; backend 708 executados e verdes, um skip.

Veredito mantido: **NO-GO comercial e de producao**. Esta execucao converteu
quebras confirmadas em incrementos verificaveis, mas nao fecha F7 nem altera os
gates G0-G5/E0-E5.

### 16.6 Atualizacao F-11 Governance/Workshop — 2026-08-20

- BFF Governance dedicado e tenant-scoped implementado, sem credencial no
  browser e sem reutilizar o Bearer ROTAS no servico externo;
- chave do Manager separada da chave do adaptador e limitada a
  `cases:read/cases:write`; catalogo de tipos deixou de exigir `admin:read`;
- sessao/tenant ROTAS e revalidada no backend antes da selecao da chave;
- criacao, listagem, detalhe e resolucao de caso passaram ponta a ponta no
  Chromium contra Manager, ROTAS, Governance e PostgreSQL reais;
- criacao de viatura e criacao/listagem de pedido Oficina passaram no mesmo
  teste; o detalhe ausente foi implementado e testado no backend;
- notas Governance e execucao/custos simulados deixaram de produzir chamadas ou
  sucesso falso;
- Manager 108/108, Governance 52/52, backend 714/714 executados + 1 skip,
  build Manager e staging validator verdes;
- ledger automatico melhorou de 160 para 99 violacoes e de sete para zero
  operacoes ausentes; 14 operacoes F-11/dependencias receberam modelos de
  sucesso explicitos; nove operacoes F-01 de autenticacao/sessao tambem foram
  tipadas; 20 operacoes F-02 de clientes, contratos, ordens e viagens foram
  tipadas e as 99 referencias restantes apontam para schemas de
  sucesso vazios.
- password reset deixou de devolver token/URL em staging ou producao; a
  exposicao de conveniencia ficou limitada a development/test e protegida por
  teste de abuso.
- o runtime Chromium F-02 confirmou cliente→contrato com persistencia real;
  foram corrigidos cache pós-mutacao, popover atrás da modal e o payload de
  atribuicao divergente do backend; a revisão seguinte corrigiu também o corpo
  obrigatório de início (`km_start`) e o contrato de fecho operacional.
  Manager passou 112/112, build de 74 rotas
  e o E2E focado 2/2;
- F-02 continua parcial: não existe UI de criar/confirmar trip-order e a
  renovacao concorrente de sessão foi observada a rodar o mesmo refresh token,
  causando 401 e retorno ao dashboard. A alteração de autenticacao aguarda
  aprovação de segurança específica e teste de concorrência.

F-11 muda de **quebrado** para **parcial/funcional local**. Nao muda para
`fechado`, porque faltam credenciais multi-tenant dinamicas, transicoes com
campos/anexos, notas, associacao caso↔OS, negativos RBAC/cross-tenant,
replay/conflito, outbox/DLQ, staging e piloto no mesmo RC.

Veredito mantido: **NO-GO comercial e de producao**.

### 16.7 Atualizacao F-02 e sessão concorrente — 2026-08-21

- o Manager passou a criar ordem de transporte vinculada a contrato/cliente,
  confirmar o rascunho e atribuir viatura/motorista antes de gerar a viagem;
- o fluxo Chromium percorreu cliente→contrato→ordem→confirmação→atribuição→
  viagem persistida, sem erros de consola nem respostas API 4xx/5xx observadas;
- a rotação backend passou a bloquear refresh token e sessão na mesma
  transação: a corrida reproduzida como 200/200 passou a aceitar uma única
  rotação e rejeitar o replay com 401;
- o Manager centralizou o single-flight por processo e passou a renovar no
  proxy antes da renderização Server Component. O Chromium abriu o dashboard
  com access token expirado e refresh HttpOnly real;
- gates locais: Manager 117/117, typecheck e build 74 rotas; backend 715/715
  executados + 1 skip, Pyright 0 erros; E2E focado 3/3;
- dívida impeditiva: 99 referências OpenAPI 2xx sem schema, 51 ocorrências no
  Ruff global preexistentes, ausência de prova multi-instância/multi-tenant,
  CI remota, staging, soak e piloto no mesmo release candidate.

F-02 muda para **funcional local até criação da viagem**. O refresh está
comprovado localmente num processo e protegido no banco, mas a experiência sob
múltiplas réplicas ainda exige staging. Veredito global mantido: **NO-GO
comercial e de producao**.

### 16.8 Autorizacao de saida, Torre e inicio da viagem — 2026-08-21

- foi fechado o bypass que permitia iniciar uma viagem `planned`; backend e
  Manager agora exigem clearance aprovado, despacho e só depois `km_start`;
- as sete verificacoes de saida exigem confirmacao explicita do operador. Um
  Load Permit declarado obrigatório continua a exigir documento real no
  backend;
- negativos locais cobrem isolamento tenant (`404`), RBAC (`403`) e reutilizacao
  da mesma chave idempotente com payload diferente (`409`);
- retries de sessao preservam a chave idempotente, enquanto uma reavaliacao
  deliberada de clearance recebe uma nova chave de comando;
- a Torre deixou de servir cache não invalidável e passou a separar tenant,
  data e paginacao; viagens `dispatched` já não permanecem em
  `pending_dispatch`;
- Chromium 3/3 percorreu cliente→contrato→ordem→confirmacao→atribuicao→pedido de
  saida→aprovacao→despacho→inicio, sem erros de consola nem API 4xx/5xx;
- gates locais: Manager 123/123, typecheck, build 74 rotas, BFF/design/no-demo/
  acessibilidade verdes; backend 719 verdes + 1 skip + 1 falha por drift RLS,
  Ruff do escopo verde e Pyright 0 erros;
- o gate OpenAPI permanece vermelho em 99 referencias. A base local esta em
  Alembic `rec15` enquanto o checkout termina em `rec13`; a tabela externa
  `trip_document_requests` impede o gate RLS integral e precisa de reconciliacao
  numa base limpa criada por `upgrade head`.

F-02 muda para **funcional local até viagem iniciada**. Continuam por provar o
fluxo documental obrigatório pela UI, staging multi-tenant/multi-instancia, CI
remota, soak e piloto do mesmo RC. Veredito global mantido: **NO-GO comercial e
de producao**.

### 16.9 Base limpa, OpenAPI e Gestão de Acessos — 2026-08-21

- uma base PostgreSQL vazia foi migrada com `alembic upgrade head` até `rec13`;
  `alembic current`, `alembic check` e RLS 6/6 ficaram verdes, sem alterar a
  base antiga em `rec15`;
- a suíte backend integral passou 721 testes + 1 skip. A falha de
  `trip_document_requests` registada em 16.8 fica classificada como drift do
  ambiente antigo, não como defeito reproduzível no checkout atual;
- alertas, notificações e utilizadores passaram a declarar schemas OpenAPI de
  sucesso; a dívida caiu de 99 para 88 referências 2xx sem schema;
- Gestão de Acessos foi corrigida para representar a operação real da API:
  criação imediata de utilizador com password temporária, seguida de
  invalidação da página;
- Chromium autenticado 2/2 comprovou criação e atualização visível da lista,
  sem erros de consola nem respostas API falhadas;
- regressão final: Manager 124/124, typecheck, build 74 rotas e cliente
  OpenAPI sem drift; `git diff --check` verde.

Esta evidência eleva Gestão de Acessos a **funcional local** e remove a base
antiga como bloqueio do checkout atual. O gate OpenAPI continua vermelho em 88,
e faltam a certificação integral F-01 a F-14, CI remota, staging
multi-tenant/multi-instância, soak, segurança operacional e piloto do mesmo RC.
Veredito global mantido: **NO-GO comercial e de produção**.

### 16.10 Contratos de Motoristas e Rotas Conhecidas — 2026-08-21

- Motoristas recebeu contratos de resposta explícitos para listagem, criação,
  detalhe, edição, pairing, scorecard e histórico;
- Rotas Conhecidas recebeu modelos explícitos de entrada e saída para o CRUD,
  substituindo payloads públicos genéricos;
- o auditor Manager/OpenAPI caiu de 88 para 72 referências 2xx sem schema e
  mantém zero operações frontend ausentes;
- OpenAPI versionado, cliente TypeScript e drift check ficaram alinhados;
- regressão integral: backend 723/723 + 1 skip na base limpa `rec13`; Manager
  124/124, typecheck e build de 74 rotas verdes;
- um teste do worker HOS dependia da hora UTC e foi tornado determinístico. A
  regra de calendário UTC versus turno contínuo/rolling 24h permanece uma
  decisão de domínio/conformidade ainda não certificada.

Motoristas e Rotas Conhecidas ficam **fechados localmente ao nível de contrato**.
O gate OpenAPI agregado continua vermelho em 72; CI, staging, multi-instância,
soak, piloto e validação HOS permanecem abertos. Veredito global mantido:
**NO-GO comercial e de produção**.

### 16.11 Auditoria de convergência vinculativa — 2026-08-22

Esta atualização substitui as contagens e conclusões locais das secções
16.5-16.10 quando houver conflito. A baseline completa está em
`docs/CURRENT_STATE_AND_CONVERGENCE_PLAN_20260822.md` e a precedência
documental em `AGENTS.md`/`ADR-009`.

Estado auditado da branch `codex/issue42-convergencia-manager-driver-backend`,
SHA `c912cb1c9e098b8cd4899c138232af7a02432c54`:

- backend 936 passed + 1 skipped, Ruff/compileall verdes e Pyright com 4 erros;
- Manager 128/128, contratos Manager/BFF/no-demo/acessibilidade estática
  verdes; build atual inconclusivo por `EPERM` no OneDrive;
- Driver 30/30, typecheck/build verdes, mas a aplicação funcional regressou à
  versão que cria viagens e documentos;
- os commits Android `ebb583b` e `50955e1` não são ancestrais do SHA atual;
- Sync não prova ownership intra-tenant nem owner de idempotência por
  motorista/dispositivo;
- seis endpoints Driver/Sync continuam com schema OpenAPI de sucesso vazio;
- pairing concorrente não possui consumo serializado;
- CI remota teve `startup_failure` e não executou os gates do SHA.

Consequentemente, F-02/Driver e F7 não estão fechados. G0, G2, G3, G4 e G5
ficam vermelhos; G1 permanece amarelo. PR #44 requer alterações e Issue #42
continua aberta.

Sequência vinculativa antes de retomar ERP-00..13/BI-01..08:

1. C0: freeze, branch/PR canónico e matriz integrar/portar/substituir/descartar;
2. C1: autorização/ownership/idempotência/pairing Driver e Sync fail-closed;
3. C2: viagens atribuídas, histórico, documentos, pedidos e lifecycle fechado;
4. C3: OpenAPI Driver, Pyright, CI Driver, Node/Actions fixados e bases de prova;
5. C4: mesmo SHA em CI, staging multi-instância e Android físico.

Issue #43 começa apenas após C0-C4. Depois seguem E0 SaaS Boundary, E1 P2P e
inventário, E2 O2C/oficina/fecho, E3 pessoas/payroll/ativos, E4 Trusted BI e E5
piloto. Nenhum agente pode promover etapa posterior contornando um gate
anterior vermelho.

### 16.12 C1-I0 — Isolamento fail-closed do pytest — 2026-08-22

- `0b7a36c` tornou `TEST_DATABASE_URL` obrigatório antes da coleção e rejeita
  nome fora de `rotas_test_*`, host não autorizado e colisão física com URLs
  operacionais, mesmo quando as credenciais diferem;
- `3acabde` criou o runner serial que provisiona de `template0`, migra até
  Alembic `head`, executa pytest e elimina a base em `finally`;
- a prova real chegou a `rec13`, passou 8 testes em 0,47 s e uma inspeção
  posterior encontrou zero bases `rotas_test_*`;
- a base operacional observada em `localhost:55432/rotas` não foi limpa nem
  usada pelo pytest;
- `xdist` é rejeitado até existir uma base independente por worker.

C1-I0 fica **fechado localmente em modo serial**. G0/G1 continuam vermelhos
porque faltam regressão integral nesta infraestrutura, CI/revisão independente,
snapshot/restore e provas RLS do release candidate. O próximo trabalho continua
em C1: ownership residual, idempotência por motorista/dispositivo e pairing
concorrente; o veredito global permanece **NO-GO**. A secção 16.13 regista o
fecho posterior do ownership residual.

### 16.13 C1 — Ownership de updates operacionais Sync — 2026-08-22

- um RED com JWT Driver real demonstrou que checklist, paragem e prova de
  entrega de outro motorista do mesmo tenant eram atualizados com sucesso;
- `5c7588e` passou a validar checklist pelo seu `driver_id` e paragem/prova pela
  viagem atribuída antes de qualquer dispatch;
- paragens só são mutáveis em viagem ativa; provas permitem a fase `delivered`,
  mas não viagem `closed/cancelled`;
- o teste verifica o código `driver_record_forbidden` e os três valores físicos
  inalterados;
- a partição isolada `test_driver_app_api.py` passou `16/16`; Ruff e Pyright
  focados passaram sem diagnósticos.

O ownership residual de entidades permitidas pelo Sync fica **fechado
localmente**. Permanecem P0 em C1 a idempotência por
tenant/motorista/dispositivo e o consumo concorrente do pairing. O estado global
continua **NO-GO**.

### 16.14 C1 — Idempotência por motorista/dispositivo — 2026-08-23

- o RED com JWT Driver real demonstrou que outro motorista ou dispositivo do
  mesmo tenant recebia a resposta `processed` e o `server_id` cacheado;
- `9698314` passou a validar `driver_id` e `device_id` antes do hash e antes de
  qualquer retorno de cache, tanto no replay normal como na recuperação de
  colisão de unicidade;
- owner mismatch devolve `idempotency_owner_mismatch`, sem `server_id`, e grava
  um `SyncEvent` associado ao principal/dispositivo que tentou o replay;
- um segundo RED concorrente demonstrou uma falha mais profunda: duas chamadas
  simultâneas davam uma resposta processada e uma em conflito, mas persistiam
  duas paragens porque o domínio fazia commit antes da chave;
- `e1d69c4` passou a consolidar efeito de domínio, chave idempotente e evento na
  mesma transação. A corrida entre dois dispositivos aceita exatamente um
  consumidor e deixa um único efeito físico;
- o runner descartável migrou até `rec13`; a partição Driver/Sync passou
  `57/57`. Ruff e Pyright focados passaram sem diagnósticos.

P0-SYNC-02 fica **fechado localmente**. C1 ainda não fecha: o próximo gate é o
consumo concorrente do pairing com exatamente um vencedor; depois seguem os
schemas OpenAPI Driver/Sync. Regressão backend integral isolada, CI, staging,
Android no mesmo SHA e release candidate permanecem pendentes. Veredito global:
**NO-GO**.

### 16.15 C1 — Pairing concorrente e identidade do dispositivo — 2026-08-23

- o RED com duas chamadas simultâneas ao mesmo código de pairing devolveu
  `200/200`, criando dois consumidores válidos;
- `9ae52b5` passou a selecionar o motorista com `FOR UPDATE`; a chamada perdedora
  só reavalia o código depois do commit vencedor e recebe
  `invalid_pairing_code` (`401`);
- a corrida real passou a produzir `200/401`, exatamente um `DriverDevice` e
  uma `DriverSession`;
- um segundo RED provou que a base aceitava duas identidades iguais para o
  mesmo `(tenant_id, driver_id, device_id)`;
- `rec14` reconcilia duplicados históricos conservando deterministicamente o
  registo ativo/mais recente, cria a constraint única física e possui downgrade
  explícito da constraint;
- uma base descartável migrou do zero até a única head `rec14`; a constraint
  rejeitou o duplicado e a regressão combinada Driver/Sync/Auth passou `74/74`
  no SHA `9ae52b5`. Ruff e Pyright focados passaram sem diagnósticos.

P1-AUTH-01 fica **fechado localmente**. O próximo gate obrigatório são os seis
schemas públicos Driver/Sync vazios e os contract tests correspondentes; depois
vem a regressão backend integral isolada. CI, staging, Android físico e release
candidate permanecem pendentes. Veredito global: **NO-GO**.

### 16.16 C3 — Contratos públicos Driver/Sync — 2026-08-23

- o contract test RED confirmou schemas `{}` nos sucessos Driver/Sync;
- `987273c` introduziu DTOs próprios para perfil, templates, viagem ativa,
  bootstrap e Sync, sem reutilizar o serializer integral do gestor;
- `DriverTripRead` exclui tenant/contrato, billing, custos, receita, margem e
  reconciliação; uma prova de runtime carregou esses valores na viagem física e
  confirmou ausência tanto na viagem ativa como no bootstrap;
- `/driver/vehicles` e `POST /driver/trips` são sempre proibidos: deixaram de
  anunciar um sucesso impossível e expõem contrato estruturado `403`;
- `checklist-templates`, embora ausente da lista histórica dos seis, também foi
  tipado por pertencer à mesma fronteira pública;
- OpenAPI e cliente TypeScript foram regenerados pelo fluxo oficial. O digest
  integral atual, após a correção HR de `ccb4dc4`, é
  `abadc941169773797976f4db9ff2c6b48cf37eabed8e4ff40f9863739e6fc0c4`;
- numa base descartável até `rec14`, OpenAPI/Driver/Sync passou `68/68`; Ruff e
  Pyright focados, drift OpenAPI, check dos tipos gerados, Manager typecheck e
  auditor `208 referências / 158 operações / 0 violações` ficaram verdes.

P1-API-01 fica **fechado localmente**. O próximo gate obrigatório é a regressão
backend integral pelo runner isolado, seguida de Ruff/Pyright globais e
reconciliação das falhas reais sem reduzir gates. CI, staging, Android no mesmo
SHA e release candidate continuam pendentes. Veredito global: **NO-GO**.

### 16.17 Regressão backend integral e gates estáticos — 2026-08-23

- `ccb4dc4` separou o contrato comum do colaborador dos contratos de criação e
  leitura: `base_salary` permanece obrigatório na criação e nullable quando a
  permissão salarial exige redação; os seis erros Pyright foram eliminados;
- OpenAPI foi regenerado pelo fluxo oficial e o Manager permaneceu alinhado:
  check de tipos, typecheck e auditor `208 referências / 158 operações / 0
  violações` verdes;
- a primeira regressão integral encontrou `967 passed, 1 skipped`; o skip
  “null limit guard not yet implemented” não foi aceite como gate verde;
- `97e365d` substituiu o placeholder por uma prova ativa: um tenant com
  `max_vehicles = NULL` cria mais de cinco viaturas sem receber `403`;
- no SHA `97e365d`, a base efémera foi criada de `template0`, migrada até
  `rec14`, executou `968 passed` sem skips e foi eliminada. A base operacional
  online permaneceu intocada;
- Ruff canónico `app tests`, Pyright `0/0/0` e drift OpenAPI ficaram verdes.

O slice backend C1/C3 fica **fechado localmente**, mas G0-G5 permanecem
vermelhos. O próximo incremento obrigatório é C2: substituir a jornada PWA
Driver administrativa por Minhas Viagens atribuídas, histórico, documentos
emitidos, pedidos de documento e viagem fechada somente leitura. Depois seguem
build reproduzível, Actions/supply chain, CI real, staging e Android físico no
mesmo RC. Veredito global: **NO-GO**.
