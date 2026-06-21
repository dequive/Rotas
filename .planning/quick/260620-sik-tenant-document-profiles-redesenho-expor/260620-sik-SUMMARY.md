# Quick Task 260620-sik — SUMMARY

**Task:** tenant_document_profiles + redesenho exporters PDF fatura modelo PHC  
**Date:** 2026-06-21  
**Status:** Complete

---

## O que foi implementado

### Task 1 — Alembic migrations (commits 596c3a1 + 07b4443)
- **Migration A** (`a3b4c5d6e7f8`): tabela `tenant_document_profiles` com RLS + GRANT (v2.0 Migration Rules)
- **Migration B** (`c5d6e7f8a9b0`): 8 colunas de snapshot em `billing_documents`

### Task 2 — TenantDocumentProfile model + service + endpoints (commit 703441b)
- `TenantDocumentProfile` ORM model em `backend/app/modules/tenants/models.py`
- Schemas `TenantDocumentProfileResponse` + `TenantDocumentProfileUpdate` em `schemas.py`
- `get_document_profile` + `upsert_document_profile` em `service.py`
- Endpoints `GET /api/v1/tenants/me/document-profile` + `PUT /api/v1/tenants/me/document-profile` (owner/admin only)

### Task 3 — Numeração configurável + snapshot (commit 2351845)

**Novas colunas em `BillingDocument`:**
- `issuer_address` (Text) — morada snapshot do perfil
- `issuer_phone` (String 40)
- `issuer_email` (String 120)
- `issuer_city` (String 80)
- `issuer_bank_details` (Text) — texto formatado "Banco X | Titular: Y | Conta: Z | NIB: W"
- `payment_conditions` (String 80)
- `commercial_discount` (Numeric 5,4)
- `financial_discount` (Numeric 5,4)

**`_assign_invoice_number` actualizado:**
- Lê `TenantDocumentProfile` para obter `invoice_prefix`, `invoice_seq_padding`, `invoice_start_seq`, `per_type_sequences`
- Formato com prefixo: `"{prefix} {year}/{seq:0{padding}d}"`
- Sequências separadas por tipo se `per_type_sequences=True` (ex: `invoice_seq_{tid}_{year}_invoice`)
- Fallback para `YYYY/NNNN` (padding=4, sem prefixo) quando não há perfil — compatibilidade total com documentos existentes

**`_snapshot_profile` novo helper:**
- Chamado após `db.add(document); await db.flush()` em `create_document`, `create_debit_note`, `create_credit_note`, `create_invoice_receipt`
- Copia `address`, `phone`, `email`, `city`, `payment_conditions`, `bank_details` do perfil para o documento

### Task 4 — Redesenho PDF layout PHC (commit 2351845)

**Novo layout `_render_pdf`** seguindo o modelo de referência Digitus/PHC Software:

| Zona | Antes | Depois |
|------|-------|--------|
| Cabeçalho | Navy band com nome em branco | 2 colunas: emitente (esq) + box cliente com bordas (dir) |
| Metadados | Lista de linhas label:valor | Barra cinza horizontal com doc number em destaque à direita |
| Tabela | Data/Origem/Destino/Carga/Estado/Qtd/Unit/Total (8 col) | Referência/Designação/Quant/Pr.Unitário/IVA%/Total (6 col) |
| Dados bancários | Ausente | Linha "Dados Bancários: ..." antes dos totais |
| Totais | SUBTOTAL/IVA/TOTAL em bloco simples | 2 colunas: tabela IVA por taxa (esq) + Valores do Documento (dir) |
| Rodapé | Nome empresa + Página X | "Documento Processado por Computador" + "ROTAS" (bold) + "Página X de Y" |

**Compatibilidade mantida:**
- Assinatura `render_billing_export(document, items, export_format)` inalterada
- `iva_rate=None` continua a levantar `ValueError`
- XLSX não alterado
- Fallback gracioso: sem perfil = layout funciona com `issuer_name`/`issuer_nuit` existentes

---

## Commits

| Hash | Conteúdo |
|------|----------|
| `596c3a1` | Migrations A + B |
| `07b4443` | Fix migration conflict (insurance + document-profile heads) |
| `703441b` | Model + service + endpoints |
| `3ff14b2` | Ruff fix imports |
| `2351845` | Tasks 3+4: BillingDocument cols + numeração configurável + PDF PHC layout |

---

## Desvios do plano

- Logo rendering deixado como extensão futura (não há coluna `logo_file_id` em `BillingDocument` ainda)
- `invoice_footer` do perfil não é ainda copiado para `BillingDocument` (campo não existe no modelo de documento) — pode ser adicionado numa migration futura
