---
phase: "15.1"
name: "Documentos Fiscais e Operacionais"
status: planning
depends_on: ["15"]
---

# Phase 15.1 — Documentos Fiscais e Operacionais

## Goal

Completar o ciclo documental do ROTAS para cumprir os requisitos legais e operacionais do transporte rodoviário moçambicano. Esta fase cobre dois domínios:

1. **Documentos Fiscais**: Estender `billing_documents` com `document_type` e `parent_document_id` para suportar Nota de Débito, Nota de Crédito, Fatura-Recibo e Recibo; adicionar AR básico (`due_date`, `aging_bucket`).
2. **Documentos Operacionais**: Formalizar os tipos de `transport_documents` com validação de campos obrigatórios por tipo; adicionar `extra_fields JSONB` para campos específicos de cada tipo; gerar PDF para documentos operacionais críticos.

## Context — O que já existe

### Fiscal
- `billing_documents` table — campos existentes: `id, tenant_id, contract_id, client_name, billing_period_start, billing_period_end, currency, subtotal, tax_amount, total_amount, status (draft|issued|paid|cancelled), issued_at, paid_at, invoice_number, iva_rate, file_id`
- **Falta**: `document_type`, `parent_document_id`, `due_date`, `client_nuit`
- `billing_items` table — campos: amount, iva_rate, iva_amount, trip_id
- Service: `issue_document()`, `_assign_invoice_number()`, PDF/XLSX exporters

### Operacional
- `transport_documents` table — campos: `id, tenant_id, contract_id, trip_id, document_type (free text, String 40), document_number, issuer, client_name, issued_at, valid_from, valid_until, origin, destination, district, location_name, file_id, status, notes`
- **Falta**: `extra_fields JSONB` para campos específicos por tipo (border_post, country_destination para CPI; authorization_code para INATTER/DAV), `recipient_nuit` para Guia de Remessa
- `cargo_manifests` — manifesto de carga já parcialmente implementado (cargo description, hazmat, weights)
- `load_permits` — guias de carregamento/descarga já implementadas
- `delivery_proofs` — comprovativo de entrega já implementado (com SM states)

## Mozambique Transport Document Types

### Fiscais (billing_documents)
| document_type | Descrição | Quando emitir |
|---|---|---|
| `invoice` (default existente) | Fatura definitiva | Após conclusão de serviços |
| `proforma` | Fatura proforma | Antes de início de serviços |
| `debit_note` | Nota de Débito | Para cobrar valor adicional sobre fatura emitida |
| `credit_note` | Nota de Crédito | Para reembolsar/corrigir fatura emitida |
| `invoice_receipt` | Fatura-Recibo | Fatura + comprovativo de pagamento simultâneos |
| `receipt` | Recibo | Comprovativo de pagamento de fatura emitida anteriormente |

### Operacionais (transport_documents)
| document_type | Descrição | Campos específicos |
|---|---|---|
| `guia_remessa` | Guia de Remessa — acompanha mercadoria | recipient_nuit, cargo_description, package_count, gross_weight |
| `carta_porte_internacional` | Carta de Porte Internacional (CPI/CMR SADC) | border_post, country_destination, sadc_cpi_number, consignee_name |
| `dav` | Documento de Acompanhamento de Viagem (INATTER) | authorization_code, valid_routes, inatter_office |
| `guia_transporte_inatter` | Guia de Transporte INATTER | authorization_code, inatter_office, route_description |
| `declaracao_carga_perigosa` | Declaração de Carga Perigosa (Hazmat) | un_number, hazmat_class, emergency_contact |

**Nota**: `cargo_manifests` e `load_permits` já têm tabelas próprias — não precisam ser migradas para `transport_documents`.

## Requirements

### FDOC-01: DDL Migration — Billing Documents Extension
Add to `billing_documents`:
- `document_type VARCHAR(30) NOT NULL DEFAULT 'invoice'` — discriminator
- `parent_document_id UUID FK billing_documents.id NULLABLE` — for debit/credit notes and receipts
- `due_date DATE NULLABLE` — for AR (calculated: issued_at + contract.payment_terms_days, default 30 days)
- `client_nuit VARCHAR(20) NULLABLE` — client NUIT for AT compliance (denormalized from contract)

Constraint: `parent_document_id` must be NULL when `document_type = 'invoice'` or `'proforma'`.

### FDOC-02: Nota de Débito
- Service: `create_debit_note(db, tenant_id, parent_id, amount, reason, iva_rate=0.17)` — creates a new `billing_document` with `document_type='debit_note'`, `parent_document_id=parent_id`, positive amount
- Parent must be in status `issued` or `paid`
- Auto-assigns `invoice_number` using existing FISC-01 sequence (Nota de Débito also gets sequential number)
- Endpoint: `POST /api/v1/billing/documents/{id}/debit-note`
- Response includes `{id, invoice_number, document_type, amount, parent_invoice_number}`

### FDOC-03: Nota de Crédito
- Service: `create_credit_note(db, tenant_id, parent_id, amount, reason, iva_rate=0.17)` — creates a new `billing_document` with `document_type='credit_note'`, negative amount (or positive and type distinguishes polarity)
- Parent must be in status `issued` or `paid`
- Auto-assigns invoice_number from same FISC-01 sequence
- Endpoint: `POST /api/v1/billing/documents/{id}/credit-note`
- Amount represents the credit amount (positive value, type signals direction)

### FDOC-04: Fatura-Recibo e Recibo
- `create_invoice_receipt(db, tenant_id, parent_id)` — transitions parent `invoice` to status `paid`, sets `paid_at=now()`, creates new `billing_document` with `document_type='invoice_receipt'` linking parent; emits PDF
- `create_receipt(db, tenant_id, parent_id, amount_paid)` — creates `billing_document` with `document_type='receipt'`, `parent_document_id=parent_id`; does NOT change parent status (partial payment scenario)
- Endpoints:
  - `POST /api/v1/billing/documents/{id}/invoice-receipt` — full payment, parent transitions to paid
  - `POST /api/v1/billing/documents/{id}/receipt` — standalone receipt (partial or confirmation)

### FDOC-05: AR Básico (Contas a Receber)
- Add computed fields to `serialize_billing_document()`: `days_overdue` (int, 0 if not overdue) and `aging_bucket` (enum: `current | 1_30 | 31_60 | 61_90 | over_90`)
- `days_overdue = max(0, (today - due_date).days)` when status = `issued` and `due_date < today`
- `GET /api/v1/billing/ar?aging_bucket=&contract_id=&limit=&offset=` — returns issued documents with due_date set, ordered by days_overdue DESC

### OPDOC-01: DDL Migration — Transport Documents Extension
Add to `transport_documents`:
- `extra_fields JSONB NULLABLE` — type-specific metadata (border_post, sadc_cpi_number, authorization_code, etc.)
- `recipient_name VARCHAR(160) NULLABLE` — for guia_remessa (rename vs reuse client_name)
- `recipient_nuit VARCHAR(20) NULLABLE` — for guia_remessa fiscal compliance

### OPDOC-02: Guia de Remessa
- Service: `create_guia_remessa(db, tenant_id, trip_id, payload)` — creates `transport_document` with `document_type='guia_remessa'`; validates required fields: `client_name` (shipper), `recipient_name`, `origin`, `destination`, `document_number`
- PDF generation via `generate_guia_remessa_pdf()` — A4 landscape, ROTAS header, shipper/recipient columns, cargo table, signature block
- Endpoint: `POST /api/v1/cargo/trips/{trip_id}/guia-remessa`
- PDF accessible via existing `GET /billing/documents/{id}/pdf` pattern (or new route at `GET /cargo/transport-documents/{id}/pdf`)

### OPDOC-03: Carta de Porte Internacional (CPI)
- Service: `create_carta_porte(db, tenant_id, trip_id, payload)` — creates `transport_document` with `document_type='carta_porte_internacional'`; `extra_fields = {border_post, country_destination, sadc_cpi_number, consignee_name, consignee_nuit}`; validates international trip context
- PDF generation: A4, bilingual headers (PT/EN), SADC CPI fields, customs declaration block
- Endpoint: `POST /api/v1/cargo/trips/{trip_id}/carta-porte`

### OPDOC-04: DAV / Guia INATTER
- Service: `create_dav(db, tenant_id, trip_id, payload)` — creates `transport_document` with `document_type='dav'`; `extra_fields = {authorization_code, inatter_office, valid_routes}`
- No PDF generation required (physical document issued by INATTER externally; this is the digital record)
- Endpoint: `POST /api/v1/cargo/trips/{trip_id}/dav`
- Fields: `document_number` (INATTER-issued number), `valid_from`, `valid_until`, `extra_fields.authorization_code`

### OPDOC-05: Document Checklist per Trip Type
- New computed endpoint: `GET /api/v1/cargo/trips/{trip_id}/document-checklist`
- Returns required vs present documents based on trip characteristics:
  - Domestic trip: [cargo_manifest, load_permit, dav, guia_remessa]
  - International trip: [cargo_manifest, load_permit, carta_porte_internacional, guia_remessa, declaracao_carga_perigosa (if hazmat)]
  - Hazmat trip (any): [+ declaracao_carga_perigosa]
- Response: `{required: [{type, label, present: bool, document_id: uuid|null}]}`

## Existing Files to Modify

| File | Change |
|---|---|
| `backend/alembic/versions/NEW_add_billing_document_types.py` | DDL for FDOC-01 (document_type, parent_document_id, due_date, client_nuit) |
| `backend/alembic/versions/NEW_add_transport_doc_extra_fields.py` | DDL for OPDOC-01 (extra_fields, recipient_nuit) |
| `backend/app/modules/billing/models.py` | Add 4 new fields to BillingDocument |
| `backend/app/modules/billing/service.py` | create_debit_note, create_credit_note, create_invoice_receipt, create_receipt, AR query |
| `backend/app/modules/billing/router.py` | 4 new POST endpoints + GET /ar |
| `backend/app/modules/billing/exporters.py` | PDF templates for Nota de Débito/Crédito, Fatura-Recibo |
| `backend/app/modules/cargo/models.py` | Add extra_fields, recipient_nuit to TransportDocument |
| `backend/app/modules/cargo/service.py` | create_guia_remessa, create_carta_porte, create_dav, get_document_checklist |
| `backend/app/modules/cargo/router.py` | 3 new POST endpoints + GET /document-checklist |
| `backend/tests/test_fiscal_documents.py` | NEW — integration tests for all FDOC-* requirements |
| `backend/tests/test_operational_documents.py` | NEW — integration tests for all OPDOC-* requirements |

## Success Criteria

1. `POST /billing/documents/{id}/debit-note` creates a Nota de Débito with sequential `invoice_number` and `parent_document_id` set
2. `POST /billing/documents/{id}/credit-note` creates a Nota de Crédito; parent document unaffected
3. `POST /billing/documents/{id}/invoice-receipt` transitions parent to `paid` and creates Fatura-Recibo
4. `GET /billing/ar?aging_bucket=31_60` returns only documents with `days_overdue` between 31 and 60
5. `POST /cargo/trips/{id}/guia-remessa` creates a transport_document and returns a PDF URL
6. `POST /cargo/trips/{id}/carta-porte` creates CPI with border_post and country_destination in extra_fields
7. `GET /cargo/trips/{id}/document-checklist` returns correct required docs for domestic trip (4 types) and international trip (5+ types)
8. All new endpoints require tenant_id filtering — cross-tenant isolation tests pass
9. All migrations include RLS policies per CLAUDE.md v2.0 rules (no new tenant_id tables exist in this phase — only ALTERs to existing tables, so RLS is already on these tables)
