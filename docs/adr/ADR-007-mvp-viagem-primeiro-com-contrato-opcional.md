# ADR-007: MVP com viagem primeiro e contrato opcional

## Status

Accepted

## Contexto

O ROTAS precisa suportar dois modos operacionais de transporte contratual:

- Modo A: contrato primeiro, depois viagem, Load Permit, descarga e cobranca.
- Modo B: viagem primeiro, depois associacao a contrato, regularizacao documental e cobranca.

No contexto das PME de transporte em Mocambique, muitas operacoes ainda acontecem de forma semi-formal: a viagem pode nascer antes de todos os dados contratuais estarem organizados no sistema. O produto deve capturar a realidade operacional sem bloquear o motorista ou o gestor, mas tambem deve conduzir a empresa para melhor controlo documental e financeiro.

## Decisao

O MVP tera o Modo B como fluxo principal:

1. Viagem pode ser aberta sem `contract_id`.
2. Gestor pode associar contrato existente ou criar contrato retroactivamente.
3. Load Permit pode ser carregado antes da partida quando existir, ou regularizado posteriormente com estado documental explicito.
4. Viagem contratual sem documento de descarga valido fica `pending_delivery_proof`.
5. Cobranca financeira real so nasce depois da prova de descarga valida.
6. `billing_items` representam linhas de documento de cobranca, nao simples previsoes operacionais.

O sistema tambem deve permitir Modo A para clientes mais estruturados:

1. Contrato criado previamente.
2. Viagem nasce vinculada a `contract_id`.
3. Regras de tarifa, rota e obrigatoriedade documental sao herdadas do contrato.
4. Load Permit e manifesto podem ser exigidos antes da partida.

## Consequencias Tecnicas

- `trips.contract_id` e nullable no MVP.
- `load_permits.contract_id`, `delivery_proofs.contract_id`, `cargo_manifests.contract_id` e `transport_documents.contract_id` sao nullable para permitir regularizacao posterior.
- `billing_documents.contract_id` e nullable tecnicamente, mas deve ser preenchido sempre que a cobranca for contratual.
- `billing_items` nao devem ser criados antes da prova de descarga, salvo se o produto introduzir explicitamente uma entidade separada de previsao/proforma.
- A lista de cobranca deve trabalhar com candidatos billable, nao criar itens financeiros prematuramente.
- Estados documentais devem ser explicitos: `missing_contract`, `pending_load_permit`, `pending_delivery_proof`, `billable`, `billed`, `disputed`.

## Risco Aceite

O Modo B permite entrada de dados incompletos. O risco e controlado por estados, alertas, auditoria e bloqueio de cobranca sem prova de descarga.

## Criterio de Sucesso

Uma transportadora piloto deve conseguir:

- abrir viagem mesmo sem contrato previamente cadastrado;
- regularizar contrato e Load Permit depois;
- anexar documento de descarga;
- ver a viagem tornar-se cobravel no mes da descarga;
- gerar cobranca mensal sem duplicar viagens ja cobradas.
