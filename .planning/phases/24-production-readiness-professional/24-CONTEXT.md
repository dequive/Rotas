# Phase 24 — Third Party Completion: Context & Architecture Decisions

## Origem

Phase 23 criou o backend completo do módulo de terceiros (tabelas, serviço, API). Phase 24 completa o módulo para produção enterprise com: UI no manager dashboard, conta corrente de fornecedor, sub-contactos, avaliação de fornecedores, supplier/service-provider pickers nos formulários existentes, e idempotency em todas as mutações.

A scope deste phase foi derivada de:
1. Gap analysis pós-Phase 23 (módulo sem UI = ninguém usa)
2. Análise comparativa com PHC CS ERP (Junho 2026)

---

## O que já existe (Phase 23 — não tocar)

### Backend (tudo em `backend/app/modules/third_party/`)
- `models.py` — `ThirdParty`, `ThirdPartyRole`, `SupplierProfile`, `ServiceProviderProfile`, `DriverVehicleAssignment`, `OperationalDocument`, `MzProvince`
- `service.py` — CRUD completo, `check_driver_eligibility`, `assign_driver_to_vehicle`, `create_operational_document`, `get_expiring_documents`, `search_party_directory` (UNION ALL)
- `router.py` — endpoints registados em `/api/v1/third-party`
- `eligibility.py` — `check_driver_eligibility(driver, reference_date) -> EligibilityResult`
- Migrations: `tp01a` (mz_provinces), `tp01b` (core tables), `tp03` (nullable FKs), `tp05` (assignments), `tp06` (operational_documents)
- Seed script: `backend/scripts/seed_mz_provinces.py`

### Modelos externos com nullable FKs adicionados:
- `FuelPurchase.supplier_third_party_id` (nullable, ON DELETE SET NULL)
- `SparePartInventory.supplier_third_party_id` (nullable, ON DELETE SET NULL)
- `WorkOrder.service_provider_third_party_id` (nullable, ON DELETE SET NULL)

---

## Requisitos Phase 24

### Backend novos

**TP2-01 — Sub-contactos por terceiro**
- Nova tabela `third_party_contacts`: `id, tenant_id, third_party_id → third_parties.id, name, role, phone, email, is_primary, created_at`
- RLS + GRANT na mesma migration (v2.0 rule)
- CRUD endpoints: `POST /api/v1/third-party/{id}/contacts`, `GET /api/v1/third-party/{id}/contacts`, `DELETE /api/v1/third-party/{id}/contacts/{contact_id}`

**TP2-02 — Código de actividade e sector**
- Adicionar a `third_parties`: `activity_code VARCHAR(20)`, `sector VARCHAR(80)` — migration additive, nullable
- Expor nos schemas e serializer

**TP2-03 — Conta corrente de fornecedor**
- Nova tabela `supplier_ledger_entries`: `id, tenant_id, third_party_id, entry_type VARCHAR(10) CHECK IN ('debit','credit'), amount NUMERIC(14,2), source_type VARCHAR(40), source_id UUID nullable, description TEXT, entry_date DATE, created_at`
- RLS + GRANT na mesma migration
- `GET /api/v1/third-party/{id}/account` → `{third_party_id, total_debits, total_credits, balance, entries: [...]}`
- Saldo = `sum(credits) - sum(debits)` — NUNCA desnormalizado, sempre calculado

**TP2-04 — Pagamentos a fornecedores**
- `POST /api/v1/third-party/{id}/payments` → cria `supplier_ledger_entry` com `entry_type=credit`, `source_type=manual_payment`
- Opcionalmente liga a `fuel_purchase_id` ou `work_order_id` como `source_type=fuel_purchase` / `source_type=work_order`

**TP2-05 — Avaliação de fornecedores**
- Nova tabela `supplier_evaluations`: `id, tenant_id, third_party_id, evaluated_by → users.id, evaluation_date DATE, criteria JSONB, score NUMERIC(4,2), notes TEXT, created_at`
- `criteria` JSONB: `[{"name": "prazo_entrega", "weight": 0.4, "score": 8}, ...]`
- Score final = média ponderada dos critérios
- RLS + GRANT na mesma migration
- `POST /api/v1/third-party/{id}/evaluations`, `GET /api/v1/third-party/{id}/evaluations`
- `serialize_third_party` actualizado para incluir `average_score: float | None`

**TP2-06 — Idempotency keys**
- Todos os endpoints POST/PUT de terceiros aceitam `Idempotency-Key` header
- Usar o `IdempotencyKey` model existente em `sync/models.py`
- Padrão já implementado no módulo de billing — replicar exactamente

### Frontend (apps/manager)

**TP2-07 — Página `/terceiros`**
- Lista paginada com colunas: Nome, Tipo (roles), Sector, Estado, Score médio, Acções
- Filtros: `role_type` (dropdown), `status` (dropdown), `sector` (texto)
- Botão "Novo Terceiro" → modal de criação
- Clicar na linha → `/terceiros/[id]` (página de detalhe)
- Route: `apps/manager/app/terceiros/page.tsx` (Server Component)
- API proxy: `apps/manager/app/api/third-party/route.ts`

**TP2-08 — Página de detalhe `/terceiros/[id]`**
- Header: nome, estado badge, score, botão "Editar"
- Tabs: **Info** | **Contactos** | **Documentos** | **Conta Corrente** | **Avaliações**
- Tab Info: campos de identidade + roles + perfis (supplier/service_provider)
- Tab Contactos: lista de sub-contactos + botão "Adicionar Contacto"
- Tab Documentos: lista de operational_documents + botão "Upload Documento"
- Tab Conta Corrente: saldo em destaque (IBM Plex Mono, grande), tabela de movimentos
- Tab Avaliações: score médio + lista de avaliações + botão "Nova Avaliação"
- Routes: `apps/manager/app/terceiros/[id]/page.tsx`

**TP2-09 — Supplier picker no formulário de abastecimento**
- No formulário de criação/edição de abastecimento (fuel purchase), adicionar combobox para supplier
- Quando seleccionado: preenche `supplier_third_party_id`, mantém `supplier_name` como snapshot
- Quando deixado vazio: funciona como antes (texto livre)
- Localização: identificar o formulário actual em `apps/manager/` — ler ficheiros antes

**TP2-10 — Service provider picker nas ordens de trabalho**
- No formulário de criação/edição de work order, adicionar combobox para service provider
- Filtrado por `role_type=service_provider`
- Quando seleccionado: preenche `service_provider_third_party_id`
- Localização: identificar formulário actual em `apps/manager/`

**TP2-11 — UI para documentos operacionais**
- Na tab Documentos do detalhe de terceiro: upload + lista
- Também acessível no perfil de motorista (tab Documentos)
- Componente reutilizável `OperationalDocumentsList` + `DocumentUploadModal`

**TP2-12 — UI para driver-vehicle assignments**
- Na página de detalhe de veículo: tab ou secção "Motoristas Atribuídos" (histórico + actual)
- Na página de detalhe de motorista: tab ou secção "Viaturas Atribuídas"
- Botão "Atribuir Motorista" / "Remover Atribuição"

### Infraestrutura

**TP2-13 — Migrations + seed**
- Documentar e executar `alembic upgrade head` — verificar que todas as migrations de Phase 23 + 24 foram aplicadas
- Executar `python scripts/seed_mz_provinces.py` — verificar que 11 províncias estão na DB
- Incluir estes steps como tasks explícitas no plano (não assumir que foram feitos)

---

## Padrões a seguir (do codebase)

### Serviço
- `_require_third_party(db, id, tenant_id)` já existe em `service.py`
- Audit log: `record_audit_log(db, ...)` dentro da mesma sessão antes do commit
- Serializer: `serialize_*` retorna `dict` puro (nunca ORM object)
- Flush → refresh → audit_log → commit → refresh

### Router
- `principal = Depends(get_current_principal)` para `tenant_id` + `user_id`
- Rotas fixas antes de `/{id}` para evitar conflito de paths
- Sem lógica de negócio no router

### Frontend
- Manrope para UI/corpo; IBM Plex Mono para valores monetários e IDs
- `amber-500` para acções primárias; `amber-600` hover
- Badges com ponto colorido `::before`
- Server Components para páginas; Client Components para interactividade
- `apiFetch` + `requireSession` para chamadas de Server Components
- Sem Tailwind config — usar classes Tailwind directamente (já configurado)

### Idempotency
- Ver `backend/app/modules/billing/router.py` — padrão com `Idempotency-Key` header
- `IdempotencyKey` model em `backend/app/modules/sync/models.py`
- TTL: 30 dias para entidades operacionais

### v2.0 Migration Rule (BLOCKER se violado)
Todo CREATE TABLE com `tenant_id` deve incluir na MESMA migration:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app;
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));
```

---

## Wave structure sugerida

**Wave 1 (paralelo, sem deps):**
- 24-01: Migrations novas + seed infra (TP2-01 tabela contacts, TP2-02 campos, TP2-03 ledger, TP2-05 evaluations)
- 24-02: Backend service + API (contacts, ledger, payments, evaluations, idempotency)

**Wave 2 (paralelo, deps wave 1):**
- 24-03: Página `/terceiros` lista + detalhe com tabs (TP2-07, TP2-08)
- 24-04: Supplier/service picker nos formulários existentes (TP2-09, TP2-10)

**Wave 3 (deps wave 2):**
- 24-05: UI documentos operacionais + assignments (TP2-11, TP2-12)
- 24-06: Migrations infra + seed + verificação end-to-end (TP2-13)
