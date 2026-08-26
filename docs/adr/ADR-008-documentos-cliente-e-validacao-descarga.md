# ADR-008: Documentos emitidos pelo cliente e validacao manual da descarga

## Status

Accepted

## Contexto

Em contratos de transporte de carga, o Load Permit/Autorizacao de Carregamento e emitido pelo cliente. O documento autoriza o transportador a carregar num distrito/local e e usado pelo cliente para controlo interno da solicitacao de transporte.

Na descarga, o cliente pode:

- carimbar/assinar a guia de transporte;
- emitir uma guia/documento de descarga;
- incluir no documento de descarga o numero do Load Permit;
- em caso de cliente individual, nao emitir documento formal.

## Decisao

O ROTAS nao emite o Load Permit no MVP. O ROTAS rastreia, valida e liga o documento ao fluxo operacional e financeiro.

A apresentação e as permissões desse documento na PWA Driver seguem a
`ADR-012`: nome principal “Autorização de carregamento”, origem no cliente/dono
da carga e apenas consulta ou pedido em falta pelo motorista.

Para descarga, o MVP usa validacao manual pelo gestor:

1. Motorista submete prova de descarga.
2. A prova pode ser documento do cliente, guia carimbada, assinatura/codigo, foto/GPS ou excepcao para cliente individual.
3. Gestor valida ou rejeita.
4. Apenas provas `validated`/`verified` tornam a viagem candidata a cobranca.
5. Se nao houver contrato associado, a viagem fica `uncontracted` e nao cria `billing_item`.

## Consequencias Tecnicas

- `load_permits.issuer_type` usa `client` por defeito.
- `delivery_proofs.load_permit_id` e `delivery_proofs.load_permit_number` permitem ligar descarga ao Load Permit mencionado pelo cliente.
- `delivery_proofs.proof_type` distingue `client_discharge_note`, `stamped_transport_guide`, `recipient_signature`, `recipient_code`, `photo_gps`, `individual_no_document` e outros.
- `delivery_proofs.client_type` distingue `company` e `individual`.
- `delivery_proofs.validation_method` regista como o gestor validou a prova.
- `billing_items` so devem nascer apos prova validada e contrato associado.

## Risco Aceite

Clientes individuais podem nao gerar prova formal. O risco e controlado por foto, GPS, assinatura/codigo quando possivel e aprovacao manual auditada pelo gestor.
