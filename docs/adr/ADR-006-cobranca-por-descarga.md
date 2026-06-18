# ADR-006 - Cobranca por Data de Descarga

## Estado

Aceite.

## Contexto

Em contratos de transporte de carga, Load Permit, guias e documentos de carga provam o carregamento, mas a cobranca so deve ser validada quando existe documento de descarga/entrega.

## Decisao

A competencia da cobranca contratual sera a data de descarga (`delivered_at`), nao a data de carregamento.

## Consequencias

- Viagem descarregada sem documento fica `pending_delivery_proof`.
- Documento de descarga validado torna viagem `billable`.
- Viagem carregada num mes e descarregada no mes seguinte entra na cobranca do mes da descarga.
- Viagens `billed` nao entram novamente em documento de cobranca.

