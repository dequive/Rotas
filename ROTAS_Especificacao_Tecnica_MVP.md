# ROTAS - Especificacao Tecnica do MVP

Versao: 0.1  
Data: 2026-05-29  
Base: `ROTAS_Plano_Mestre_Execucao.md` v0.2

## 1. Objectivo

Esta especificacao transforma o plano mestre em contratos tecnicos para construcao do MVP.

O MVP deve entregar:

- Gestao multi-tenant.
- Autenticacao do dashboard.
- Cadastro de viaturas e motoristas.
- Upload de fotos/documentos.
- Checklists pre-partida e chegada.
- Registo de combustivel.
- Abertura e fecho de viagens.
- Autorizacao de Carregamento / Load Permit por viagem ou trecho.
- Guia de transporte e outros documentos de carga por viagem.
- Documento de descarga/entrega como prova final de entrega.
- Estado carregado/vazio por ida e volta.
- Manifesto de Carga para produtos manufaturados quando aplicavel.
- Custos variaveis de transporte por contrato, rota e evento.
- Base de cobranca mensal por contrato, gerada a partir de entregas descarregadas.
- PWA motorista offline-first.
- Sync idempotente.
- Alertas internos.
- Auditoria basica.

## 2. Decisoes de Implementacao

### 2.1 Monolito Modular

O backend sera um unico servico FastAPI, organizado por modulos:

```text
app/
  main.py
  config.py
  database.py
  core/
    auth.py
    permissions.py
    tenant.py
    errors.py
  modules/
    auth/
    tenants/
    users/
    drivers/
    vehicles/
    files/
    checklists/
    fuel/
    trips/
    cargo/
    billing/
    alerts/
    sync/
    audit/
```

Cada modulo deve ter, quando aplicavel:

```text
models.py
schemas.py
router.py
service.py
repository.py
permissions.py
tests/
```

### 2.2 Users vs Drivers

Decisao do MVP:

- `users`: utilizadores do dashboard.
- `drivers`: motoristas operacionais.
- Motoristas nao entram inicialmente como `users`.
- Acesso PWA do motorista usa `driver_sessions` e `driver_devices`.
- Se no futuro motorista precisar entrar no dashboard, adiciona-se `drivers.user_id`.

Motivo:

- Mantem permissoes simples.
- Evita misturar RBAC administrativo com operacao de campo.
- Permite login por PIN/codigo/dispositivo no PWA.

### 2.3 Redis

Redis nao e obrigatorio no primeiro build.

Se Redis nao estiver activo:

- refresh tokens ficam em `refresh_tokens`;
- idempotencia fica em `idempotency_keys`;
- rate limit pode comecar in-memory em dev e ir para Redis antes de producao.

### 2.4 IndexedDB Stores do PWA

Stores minimas:

- `driverProfile`
- `vehicles`
- `checklistTemplates`
- `pendingChecklists`
- `checklistResponses`
- `activeTrip`
- `tripStops`
- `loadPermits`
- `transportDocuments`
- `deliveryProofs`
- `cargoManifests`
- `tripCosts`
- `pendingFuelLogs`
- `photoQueue`
- `syncQueue`
- `destinations`

## 3. Roles e Permissoes

### 3.1 Roles do Dashboard

Roles em `users.role`:

- `owner`: dono do tenant, gere plano, users e tudo.
- `admin`: gere operacao e configuracoes.
- `manager`: opera frota, aprova/rejeita, ve relatorios.
- `viewer`: leitura, relatorios, sem edicao operacional.

### 3.2 Acesso do Motorista

Motorista nao usa `users.role`.

O PWA recebe um token com claims:

```json
{
  "sub": "driver:<driver_id>",
  "tenant_id": "<tenant_id>",
  "driver_id": "<driver_id>",
  "device_id": "<device_id>",
  "scope": "driver_app",
  "type": "access"
}
```

### 3.3 Matriz de Permissoes MVP

| Recurso | owner | admin | manager | viewer | driver_app |
|---|---:|---:|---:|---:|---:|
| Tenants settings | W | W | R | R | - |
| Users | W | W | - | - | - |
| Drivers | W | W | W | R | R proprio |
| Vehicles | W | W | W | R | R autorizadas |
| Files | W | W | W | R | W proprio |
| Checklist templates | W | W | W | R | R |
| Checklists | W | W | W | R | W proprio |
| Fuel logs | W | W | W | R | W proprio |
| Trips | W | W | W | R | W proprio |
| Alerts | W | W | W | R | - |
| Audit logs | R | R | - | - | - |

`W` inclui criar/editar/arquivar conforme regra de negocio.

## 4. Padrao de API

### 4.1 Base

- Prefixo: `/api/v1`
- Formato: JSON.
- Auth dashboard: `Authorization: Bearer <access_token>`.
- Auth motorista: `Authorization: Bearer <driver_access_token>`.
- Erros seguem envelope unico.

### 4.2 Resposta de Erro

```json
{
  "error": {
    "code": "vehicle_plate_exists",
    "message": "Matricula ja existe neste tenant.",
    "details": {
      "plate": "ABC-123-MZ"
    },
    "request_id": "req_01HV..."
  }
}
```

### 4.3 Paginacao

Para listas no MVP:

```text
?limit=50&offset=0
```

Resposta:

```json
{
  "items": [],
  "limit": 50,
  "offset": 0,
  "total": 124
}
```

Cursor pagination pode entrar depois.

### 4.4 Filtros Padrao

Sempre que fizer sentido:

- `status`
- `vehicle_id`
- `driver_id`
- `date_from`
- `date_to`
- `search`

## 5. Modelo de Dados MVP

### 5.1 Extensoes PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Usar `gen_random_uuid()` via `pgcrypto`.

### 5.2 Tabelas

#### tenants

Campos principais:

- `id`
- `name`
- `slug`
- `plan`
- `max_vehicles`
- `max_drivers`
- `max_users`
- `is_active`
- `is_trial`
- `trial_ends_at`
- `whatsapp_number`
- `timezone`
- `currency`
- `created_at`
- `updated_at`

#### users

Campos:

- `id`
- `tenant_id`
- `email`
- `password_hash`
- `full_name`
- `phone`
- `role`: `owner`, `admin`, `manager`, `viewer`
- `is_active`
- `last_login_at`
- `created_at`
- `updated_at`

Constraints:

- `UNIQUE(tenant_id, email)`

#### refresh_tokens

Usar se Redis nao estiver activo.

Campos:

- `id`
- `tenant_id`
- `user_id`
- `token_hash`
- `expires_at`
- `revoked_at`
- `created_at`
- `created_by_ip`
- `user_agent`

#### drivers

Campos:

- `id`
- `tenant_id`
- `full_name`
- `phone`
- `email`
- `emergency_contact_name`
- `emergency_contact_phone`
- `license_number`
- `license_category`
- `license_valid_until`
- `inatter_license`
- `inatter_valid_until`
- `inss_number`
- `employment_type`
- `status`
- `score`
- `photo_file_id`
- `created_at`
- `updated_at`

#### driver_devices

Campos:

- `id`
- `tenant_id`
- `driver_id`
- `device_id`
- `device_name`
- `platform`
- `last_seen_at`
- `is_active`
- `created_at`

#### driver_sessions

Campos:

- `id`
- `tenant_id`
- `driver_id`
- `device_id`
- `token_hash`
- `expires_at`
- `revoked_at`
- `created_at`

#### vehicles

Campos:

- `id`
- `tenant_id`
- `plate`
- `chassis`
- `brand`
- `model`
- `year`
- `color`
- `category`: `pesado`, `ligeiro`, `moto`, `reboque`, `especial`
- `status`: `active`, `maintenance`, `retired`, `blocked`
- `current_km`
- `fuel_type`: `gasoleo`, `gasolina`, `gpl`, `outro`
- `documents`
- `qr_code_hash`
- `photo_file_id`
- `avg_consumption_target`
- `fuel_limit_daily`
- `created_at`
- `updated_at`

Constraints:

- `UNIQUE(tenant_id, plate)`

#### files

Campos:

- `id`
- `tenant_id`
- `entity_type`
- `entity_id`
- `file_type`: `photo`, `document`, `signature`, `receipt`
- `original_name`
- `storage_key`
- `storage_provider`
- `mime_type`
- `size_bytes`
- `sha256_hash`
- `uploaded_by_user_id`
- `uploaded_by_driver_id`
- `uploaded_at`
- `confirmed_at`

Nota: `entity_type/entity_id` e polimorfico. Validacao fica no service layer.

#### checklist_templates

Campos:

- `id`
- `tenant_id`
- `name`
- `type`: `pre_partida`, `chegada`, `carregamento`, `entrega`
- `category`
- `is_active`
- `items`
- `created_at`
- `updated_at`

`items` e JSONB com estrutura:

```json
[
  {
    "id": "oil_level",
    "label": "Nivel de oleo",
    "type": "boolean",
    "is_blocking": true,
    "requires_photo": false,
    "category": "mecanico"
  }
]
```

#### checklists

Campos:

- `id`
- `tenant_id`
- `vehicle_id`
- `driver_id`
- `template_id`
- `type`
- `status`: `in_progress`, `completed`, `failed`, `conflict`
- `responses`
- `location`
- `gps_accuracy_m`
- `gps_source`
- `client_captured_at`
- `server_received_at`
- `signature_file_id`
- `started_at`
- `completed_at`
- `duration_seconds`
- `created_at`

#### fuel_logs

Campos:

- `id`
- `tenant_id`
- `vehicle_id`
- `driver_id`
- `fuel_date`
- `station_name`
- `station_location`
- `fuel_type`
- `liters`
- `price_per_liter`
- `total_cost`
- `km_at_refuel`
- `km_since_last`
- `consumption_l_per_100km`
- `receipt_file_id`
- `odometer_file_id`
- `payment_method`
- `payment_reference`
- `is_verified`
- `verified_by_user_id`
- `verified_at`
- `flagged`
- `client_captured_at`
- `server_received_at`
- `created_at`

#### contracts

Contrato de prestacao de servicos entre transportadora e cliente. E a entidade que organiza Load Permits, viagens, documentos de descarga e cobranca mensal.

Campos:

- `id`
- `tenant_id`
- `client_name`
- `contract_reference`
- `title`
- `status`: `active`, `paused`, `completed`, `cancelled`
- `service_type`: `cargo_transport`, `distribution`, `dedicated_fleet`, `other`
- `billing_cycle`: `monthly`, `weekly`, `per_trip`
- `billing_basis`: `trip`, `ton`, `km`, `route`, `custom`
- `currency`
- `default_unit_price`
- `requires_load_permit`
- `requires_delivery_proof`
- `requires_cargo_manifest_for_manufactured_goods`
- `pricing_rules`
- `starts_at`
- `ends_at`
- `notes`
- `created_at`
- `updated_at`

Regras:

- Viagens contratuais devem apontar para `contract_id`.
- `contract_reference` deve continuar gravado em viagens e documentos para leitura humana e auditoria.
- Regras de preco por rota, distrito, carga ou unidade entram em `pricing_rules`.
- Documento de cobranca mensal agrupa itens por cliente, contrato e periodo de descarga.

#### trips

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `vehicle_id`
- `driver_id`
- `origin`
- `origin_location`
- `destination`
- `destination_location`
- `cargo_type`
- `cargo_class`: `raw_material`, `manufactured`, `agricultural`, `fuel`, `general`, `other`
- `cargo_weight`
- `cargo_volume`
- `cargo_volumes`
- `cargo_file_id`
- `load_state`: `loaded_out_empty_return`, `empty_out_loaded_return`, `loaded_out_loaded_return`, `empty_out_empty_return`, `one_way_loaded`, `one_way_empty`
- `requires_load_permit`
- `requires_cargo_manifest`
- `waybill_number`
- `km_start`
- `km_start_file_id`
- `km_end`
- `km_end_file_id`
- `status`: `planned`, `in_progress`, `completed`, `cancelled`, `conflict`
- `planned_departure`
- `actual_departure`
- `planned_arrival`
- `actual_arrival`
- `recipient_name`
- `recipient_signature_file_id`
- `delivery_file_id`
- `cargo_status`
- `total_fuel_cost`
- `total_expense_cost`
- `total_transport_cost`
- `contract_reference`
- `billing_status`: `not_billable`, `pending_delivery_proof`, `billable`, `billed`, `billing_disputed`
- `billable_at`
- `billed_at`
- `billing_document_id`
- `created_at`
- `updated_at`

Regras de contrato:

- `contract_id` e nullable no MVP para suportar viagem primeiro.
- Viagens podem nascer sem contrato e ser regularizadas pelo gestor antes da cobranca.
- Se a viagem for contratual e nao tiver contrato associado, deve aparecer como pendencia operacional.
- Clientes maduros podem usar contrato primeiro; neste caso a viagem herda regras de tarifa, rota e documentos obrigatorios do contrato.

#### load_permits

Representa a Autorizacao de Carregamento / Load Permit emitida pelo cliente para um distrito ou local.

Nota de dominio: o ROTAS nao emite este documento no MVP. O cliente emite, e o ROTAS regista numero, ficheiro, validade, local, contrato e relacao com a viagem.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `trip_id`
- `client_name`
- `client_reference`
- `permit_number`
- `issuer_type`: `client`
- `issuer_name`
- `district`
- `location_name`
- `origin`
- `destination`
- `valid_from`
- `valid_until`
- `leg_type`: `outbound`, `return`, `single`, `multi_stop`
- `load_state`: `loaded`, `empty`
- `file_id`
- `status`: `pending`, `valid`, `expired`, `cancelled`, `used`
- `notes`
- `created_at`
- `updated_at`

Regras:

- Cada ida ou volta pode ter Load Permit proprio.
- Viagem que exige Load Permit nao pode iniciar sem permit valido, salvo override de `admin`.
- Load Permit expirado gera alerta.
- Load Permit deve ficar associado a documento digital em `files`.
- O mesmo Load Permit nao deve ser usado em duas viagens concluidas, salvo se o cliente emitir autorizacao multi-trecho.

#### cargo_manifests

Documento emitido pelo transportador quando a carga, especialmente produtos manufaturados, exige Manifesto de Carga.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `trip_id`
- `manifest_number`
- `issuer_user_id`
- `client_name`
- `shipper_name`
- `recipient_name`
- `cargo_description`
- `cargo_type`
- `cargo_class`
- `package_count`
- `gross_weight`
- `origin`
- `destination`
- `issued_at`
- `file_id`
- `status`: `draft`, `issued`, `cancelled`
- `created_at`
- `updated_at`

Regras:

- Se `trips.requires_cargo_manifest = true`, a viagem nao deve ser fechada sem manifesto emitido.
- Manifesto cancelado nao serve como documento valido.
- Manifesto deve poder ser exportado para PDF em fase posterior.

#### transport_documents

Documentos de carga associados a viagem, incluindo guia de transporte, Load Permit, carta de porte, manifesto, ordem do cliente e outros documentos operacionais.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `trip_id`
- `document_type`: `load_permit`, `transport_guide`, `waybill`, `cargo_manifest`, `client_order`, `delivery_proof`, `other`
- `document_number`
- `issuer`
- `client_name`
- `issued_at`
- `valid_from`
- `valid_until`
- `origin`
- `destination`
- `district`
- `location_name`
- `file_id`
- `status`: `pending`, `valid`, `expired`, `cancelled`, `used`, `rejected`
- `notes`
- `created_at`
- `updated_at`

Regras:

- Load Permit tambem pode ser representado nesta tabela, mas a entidade `load_permits` guarda campos especificos de autorizacao.
- Guia de transporte e demais documentos entram no pacote documental da viagem.
- Documentos rejeitados nao podem validar cobranca.
- Documentos expirados ou ausentes podem gerar alerta.

#### delivery_proofs

Documento de descarga/entrega recebido pelo motorista ao descarregar mercadoria. E a prova principal que valida a cobranca do transporte.

Para cliente empresa, a prova normal e guia carimbada/assinada ou documento de descarga emitido pelo cliente. Para cliente individual, pode nao existir documento formal; neste caso o ROTAS aceita prova alternativa com aprovacao manual auditada.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `trip_id`
- `load_permit_id`
- `load_permit_number`
- `document_number`
- `proof_type`: `client_discharge_note`, `stamped_transport_guide`, `recipient_signature`, `recipient_code`, `photo_gps`, `individual_no_document`, `other`
- `client_type`: `company`, `individual`
- `receiver_name`
- `receiver_contact`
- `delivery_location`
- `delivered_at`
- `cargo_condition`: `intact`, `damaged`, `partial`, `rejected`
- `quantity_delivered`
- `validation_method`
- `notes`
- `file_id`
- `created_by_driver_id`
- `verified_by_user_id`
- `verified_at`
- `status`: `pending`, `validated`, `verified`, `rejected`
- `created_at`
- `updated_at`

Regras:

- Viagem de carga contratual fica `pending_delivery_proof` ate existir documento de descarga valido.
- Documento de descarga validado muda viagem para candidata a cobranca.
- Se `contract_id` ainda estiver ausente, a viagem fica `uncontracted` e nao gera `billing_item`.
- `billing_item` so e criado quando existir contrato associado e prova de descarga validada.
- A competencia de cobranca e determinada por `delivered_at`, nao por data de carregamento.
- Se carregou num mes e descarregou no mes seguinte, a cobranca entra no mes da descarga.

#### billing_documents

Documento de cobranca mensal gerado para contratos de transporte.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `client_name`
- `contract_reference`
- `billing_period_start`
- `billing_period_end`
- `currency`
- `subtotal`
- `tax_amount`
- `total_amount`
- `status`: `draft`, `issued`, `paid`, `cancelled`, `disputed`
- `issued_at`
- `paid_at`
- `file_id`
- `created_at`
- `updated_at`

#### billing_items

Linhas de cobranca geradas a partir de viagens/trechos descarregados.

Campos:

- `id`
- `tenant_id`
- `contract_id`
- `billing_document_id`
- `trip_id`
- `load_permit_id`
- `cargo_manifest_id`
- `transport_document_id`
- `delivery_proof_id`
- `client_reference`
- `origin`
- `destination`
- `district`
- `cargo_description`
- `cargo_class`
- `load_state`
- `loaded_at`
- `delivered_at`
- `quantity`
- `unit_price`
- `amount`
- `status`: `draft`, `billed`, `disputed`, `cancelled`
- `created_at`

Regras:

- Uma viagem so pode entrar numa cobranca se `billing_status = billable`.
- Uma viagem ja `billed` nao deve entrar em nova cobranca.
- `billing_items` nao devem ser criados antes de existir prova de descarga valida; previsoes devem aparecer como candidatos de cobranca, nao como linhas financeiras definitivas.
- O documento de cobranca mensal deve responder:
  - quantos carregamentos foram feitos;
  - o que foi transportado;
  - para onde foi transportado;
  - que valor cobrar ao cliente;
  - o que ja foi cobrado;
  - o que falta cobrar.

#### trip_stops

Campos:

- `id`
- `tenant_id`
- `trip_id`
- `stop_type`: `abastecimento`, `refeicao`, `avaria`, `fiscalizacao`, `pernoite`, `outro`
- `location`
- `address`
- `notes`
- `photo_file_id`
- `cost`
- `expense_category`
- `stopped_at`
- `resumed_at`
- `created_at`

#### trip_costs

Custos de transporte sao variados e nao devem ficar presos apenas em combustivel ou portagens.

Campos:

- `id`
- `tenant_id`
- `trip_id`
- `cost_type`: `fuel`, `toll`, `barge`, `driver_allowance`, `meal`, `lodging`, `loading_fee`, `unloading_fee`, `waiting_time`, `escort`, `fine`, `repair`, `other`
- `description`
- `amount`
- `currency`
- `paid_by`: `driver`, `company`, `client`
- `payment_method`
- `receipt_file_id`
- `incurred_at`
- `created_at`

Regras:

- Custos podem ser registados pelo motorista ou gestor.
- Custos com recibo obrigatorio devem ter `receipt_file_id`.
- Custos declarados pelo motorista podem exigir verificacao do gestor.
- `total_transport_cost` da viagem deve ser derivado de `trip_costs`, combustivel e custos adicionais aprovados.

#### alerts

Campos:

- `id`
- `tenant_id`
- `alert_type`
- `priority`: `critical`, `high`, `medium`, `low`
- `entity_type`
- `entity_id`
- `title`
- `message`
- `channel`: `dashboard`, `whatsapp`, `email`
- `status`: `pending`, `sent`, `read`, `dismissed`
- `sent_at`
- `read_at`
- `dismissed_at`
- `created_at`

Tipos MVP:

- `document_expiry`
- `checklist_overdue`
- `checklist_failed`
- `fuel_anomaly`
- `trip_delayed`
- `load_permit_missing`
- `load_permit_expired`
- `cargo_manifest_missing`
- `sync_conflict`

#### audit_logs

Campos:

- `id`
- `tenant_id`
- `user_id`
- `driver_id`
- `action`
- `entity_type`
- `entity_id`
- `old_values`
- `new_values`
- `ip_address`
- `user_agent`
- `created_at`

#### idempotency_keys

Campos:

- `id`
- `tenant_id`
- `driver_id`
- `device_id`
- `idempotency_key`
- `operation`
- `entity_type`
- `entity_id`
- `request_hash`
- `response_body`
- `status_code`
- `created_at`
- `expires_at`

Constraints:

- `UNIQUE(tenant_id, idempotency_key)`

#### sync_events

Campos:

- `id`
- `tenant_id`
- `driver_id`
- `device_id`
- `idempotency_key`
- `operation`
- `entity_type`
- `local_id`
- `server_id`
- `payload`
- `status`: `received`, `processed`, `conflict`, `failed`
- `error_code`
- `error_message`
- `created_at`
- `processed_at`

## 6. Endpoints do MVP

### 6.1 Auth Dashboard

`POST /api/v1/auth/login`

Request:

```json
{
  "email": "admin@demo.co.mz",
  "password": "secret"
}
```

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "...",
    "tenant_id": "...",
    "role": "owner",
    "full_name": "Admin"
  }
}
```

`POST /api/v1/auth/refresh`

`POST /api/v1/auth/logout`

### 6.2 Auth Motorista

`POST /api/v1/driver-auth/pair`

Uso: activar dispositivo do motorista com codigo emitido pelo gestor.

Request:

```json
{
  "pairing_code": "123456",
  "device_id": "android-web-abc123",
  "device_name": "Samsung A03"
}
```

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "driver": {
    "id": "...",
    "full_name": "Joao Manuel"
  }
}
```

### 6.3 Files

`POST /api/v1/files/presign`

Request:

```json
{
  "entity_type": "fuel_log",
  "entity_id": null,
  "file_type": "receipt",
  "original_name": "recibo.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 612000,
  "sha256_hash": "..."
}
```

Response:

```json
{
  "file_id": "...",
  "upload_url": "https://...",
  "storage_key": "tenant/.../recibo.jpg",
  "expires_in": 900
}
```

`POST /api/v1/files/confirm`

Confirma que upload para R2 foi concluido e liga ficheiro a entidade.

### 6.4 Carga e Documentos de Transporte

`POST /api/v1/trips/{id}/load-permits`

Cria Autorizacao de Carregamento / Load Permit ligado a viagem ou trecho.

`POST /api/v1/trips/{id}/cargo-manifest`

Cria Manifesto de Carga quando o transportador deve emitir documento para produtos manufaturados ou outra carga aplicavel.

`POST /api/v1/trips/{id}/costs`

Regista custo variavel de transporte: portagem, barcaca, diaria, refeicao, carregamento, descarregamento, espera, escolta, reparacao ou outro.

`GET /api/v1/trips/{id}/costs`

Lista custos da viagem e totais aprovados/declarados.

`POST /api/v1/trips/{id}/transport-documents`

Anexa guia de transporte, carta de porte, ordem do cliente ou outro documento de carga.

`POST /api/v1/trips/{id}/delivery-proof`

Anexa documento de descarga/entrega recebido no destino.

### 6.5 Billing Contratual

`GET /api/v1/billing/billable-trips`

Lista viagens descarregadas, validadas e ainda nao cobradas.

Filtros:

- `client_name`
- `contract_reference`
- `period_start`
- `period_end`
- `status`

`POST /api/v1/billing/documents`

Gera documento de cobranca para cliente/contrato/periodo.

Regra central:

- periodo usa `delivery_proofs.delivered_at`;
- nao usa a data de carregamento como competencia de cobranca.

`GET /api/v1/billing/documents/{id}`

Detalha documento de cobranca, itens, totais e viagens associadas.

`POST /api/v1/billing/documents/{id}/issue`

Emite cobranca e marca viagens/itens como `billed`.

### 6.6 Sync Batch

`POST /api/v1/sync/batch`

Request:

```json
{
  "device_id": "android-web-abc123",
  "operations": [
    {
      "local_id": "local-checklist-1",
      "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
      "operation": "create",
      "entity_type": "checklist",
      "payload": {}
    }
  ]
}
```

Response:

```json
{
  "results": [
    {
      "local_id": "local-checklist-1",
      "server_id": "...",
      "status": "processed",
      "entity_type": "checklist"
    }
  ]
}
```

Conflict response inside result:

```json
{
  "local_id": "local-fuel-1",
  "server_id": "...",
  "status": "conflict",
  "error_code": "fuel_already_verified",
  "message": "Este abastecimento ja foi verificado pelo gestor."
}
```

### 6.5 Bootstrap PWA

`GET /api/v1/sync/bootstrap`

Retorna dados para cache local:

- perfil do motorista;
- viaturas autorizadas;
- templates activos;
- destinos frequentes;
- viagem activa;
- configuracoes do tenant relevantes para motorista.

## 7. Fluxos Criticos

### 7.1 Checklist Pre-Partida Offline

1. Motorista abre PWA.
2. PWA carrega viaturas autorizadas de IndexedDB.
3. Motorista escolhe viatura ou escaneia QR.
4. PWA carrega template.
5. Motorista responde itens.
6. Itens com foto guardam blob em `photoQueue`.
7. Checklist fica em `pendingChecklists`.
8. Operacao entra em `syncQueue`.
9. Quando online, fotos sobem primeiro.
10. Backend cria checklist.
11. PWA recebe `server_id`.
12. Estado vira `synced`.

Bloqueio:

- Se item bloqueante falhar, checklist pode sincronizar, mas viatura fica `blocked` ou gera alerta conforme configuracao.

### 7.2 Abastecimento

1. Motorista informa km, litros, custo e posto.
2. Foto do recibo e odometro sao obrigatorias por configuracao padrao.
3. PWA calcula dados preliminares localmente.
4. Backend valida km crescente.
5. Backend calcula `km_since_last` e `consumption_l_per_100km`.
6. Se consumo exceder limite, cria alerta `fuel_anomaly`.
7. Gestor pode verificar ou rejeitar.

### 7.3 Viagem

1. Motorista abre viagem.
2. Sistema valida:
   - viatura activa;
   - motorista activo;
   - sem viagem activa para a viatura;
   - sem viagem activa para o motorista.
3. Sistema identifica se a viagem exige Load Permit.
4. Se exigir Load Permit, deve existir Autorizacao de Carregamento valida para o distrito/local e trecho.
5. Sistema regista estado de carga: carregado/vazio, vazio/carregado, carregado/carregado, vazio/vazio ou one-way.
6. Se a carga for produto manufaturado e exigir documento do transportador, marcar `requires_cargo_manifest`.
7. Km inicial e foto do odometro sao obrigatorios.
8. Durante a viagem, motorista regista paragens e custos variaveis.
9. Ao descarregar, motorista anexa documento de descarga/entrega.
10. No fecho, km final e foto sao obrigatorios.
11. Se `requires_cargo_manifest = true`, manifesto emitido e obrigatorio para fechar.
12. Sistema calcula km total e custos.
13. Se documento de descarga for validado, viagem fica `billable`.
14. Se nao houver documento de descarga, viagem fica `pending_delivery_proof`.

### 7.4 Documentos de Carga

Load Permit:

1. Cliente emite Autorizacao de Carregamento para distrito/local.
2. Gestor ou motorista anexa o documento a viagem.
3. Sistema valida validade, local e trecho.
4. Documento usado fica associado a viagem.

Manifesto de Carga:

1. Transportador identifica necessidade do manifesto.
2. Gestor cria manifesto com cliente, remetente, destinatario, carga, volumes e peso.
3. Sistema liga manifesto a viagem.
4. Viagem que exige manifesto nao fecha sem manifesto emitido.

Documento de descarga:

1. Motorista recebe documento ao descarregar mercadoria.
2. Motorista fotografa/anexa documento no PWA.
3. Gestor valida documento.
4. Validacao muda a viagem para `billable`.
5. Data de descarga define o mes de cobranca.

### 7.5 Custos Variaveis de Transporte

Custos aceites no MVP:

- combustivel;
- portagens;
- barcacas;
- refeicoes;
- estadias;
- diaria/ajuda de custo do motorista;
- taxa de carregamento;
- taxa de descarregamento;
- tempo de espera;
- escolta;
- pequenas reparacoes;
- outros custos com justificacao.

Custos podem ser:

- declarados pelo motorista;
- lancados pelo gestor;
- pagos pelo cliente, empresa ou motorista;
- com ou sem recibo, conforme configuracao.

### 7.6 Cobranca Mensal por Contrato

1. Gestor filtra cliente/contrato e periodo.
2. Sistema lista viagens com descarga validada no periodo.
3. Sistema exclui viagens ja cobradas.
4. Sistema calcula valor a cobrar por contrato, rota, carga, quantidade ou regra configurada.
5. Gestor reve itens.
6. Sistema gera documento de cobranca.
7. Ao emitir, viagens associadas ficam `billed`.

Regra de competencia:

- A cobranca pertence ao mes da descarga (`delivered_at`).
- Se carregamento aconteceu em Abril e descarga em Maio, a viagem entra na cobranca de Maio.

## 8. Alertas MVP

Alertas sao internos no dashboard.

### 8.1 Gatilhos

- Documento de viatura vencido ou proximo de vencer.
- Checklist em atraso.
- Checklist falhou por item bloqueante.
- Consumo anormal.
- Viagem atrasada.
- Load Permit ausente, expirado ou inconsistente com distrito/local.
- Manifesto de Carga ausente quando obrigatorio.
- Documento de descarga ausente.
- Viagem descarregada ainda nao cobrada.
- Conflito de sync.

### 8.2 Prioridades

- `critical`: bloqueia operacao ou risco financeiro alto.
- `high`: exige accao em breve.
- `medium`: acompanhamento normal.
- `low`: informativo.

## 9. Criterios de Aceite por Modulo

### Auth e Tenants

- User de tenant A nao ve dados de tenant B.
- Login falhado nao revela se email existe.
- Refresh token revogado nao gera access token.
- Tenant inactivo bloqueia login.

### Viaturas

- Matricula duplicada no mesmo tenant retorna 409.
- Matricula igual em tenant diferente e permitida.
- Viatura arquivada nao aparece por defeito em listas operacionais.
- QR code aponta para rota valida do PWA.

### Motoristas

- Motorista inactivo nao consegue criar checklist, abastecimento ou viagem.
- Documento vencido gera alerta.
- Dispositivo revogado perde acesso ao PWA.

### Checklists

- Checklist offline sincroniza sem duplicar.
- Item bloqueante falhado gera estado `failed` e alerta.
- Foto obrigatoria sem file confirmado impede conclusao.
- Correccao de checklist gera audit log.

### Fuel

- Litros <= 0 retorna erro.
- Km menor que ultimo km conhecido retorna erro ou conflito.
- Abastecimento ja verificado nao e sobrescrito por sync tardio.
- Consumo anormal cria alerta.

### Trips

- Nao permite duas viagens activas para mesma viatura.
- Nao permite duas viagens activas para mesmo motorista.
- Fecho sem km final retorna erro.
- Km final menor que km inicial retorna erro.
- Viagem que exige Load Permit nao inicia sem documento valido, salvo override autorizado.
- Load Permit deve estar associado ao distrito/local e trecho correcto.
- Viagem que exige Manifesto de Carga nao fecha sem manifesto emitido.
- Estado carregado/vazio deve ser obrigatorio para viagem de carga.
- Custos variaveis devem ficar associados a viagem.
- Viagem contratual descarregada sem documento de descarga fica `pending_delivery_proof`.
- Documento de descarga validado torna viagem `billable`.
- Viagem `billed` nao entra em nova cobranca.
- Competencia de cobranca usa data de descarga, nao data de carregamento.

### Billing

- Lista de cobranca mensal deve mostrar viagens billable e nao cobradas.
- Documento de cobranca deve agrupar por cliente/contrato/periodo.
- Cada item de cobranca deve apontar para viagem e documento de descarga.
- Sistema deve mostrar o que falta cobrar.
- Transporte carregado num mes e descarregado no mes seguinte deve ser cobrado no mes seguinte.

### Files

- Upload sem confirmacao nao e considerado prova valida.
- MIME type nao permitido retorna erro.
- Hash e tamanho ficam gravados.

### Sync

- Mesma `idempotency_key` nao cria duplicado.
- Falha de rede nao apaga item local.
- Conflito fica visivel para gestor.
- Batch retorna resultado por operacao.

## 10. Testes Minimos

### Backend

- Auth login/refresh/logout.
- Isolamento multi-tenant.
- CRUD de viaturas.
- Matricula duplicada.
- Criacao de checklist.
- Sync idempotente.
- Criacao de fuel log e anomalia.
- Criacao/fecho de trip.
- Load Permit obrigatorio bloqueia inicio quando ausente.
- Manifesto obrigatorio bloqueia fecho quando ausente.
- Documento de descarga validado torna viagem cobravel.
- Billing mensal usa data de descarga.
- Custos variaveis somam no total da viagem.
- Upload presign/confirm.

### Frontend Gestor

- Login.
- Listagem de viaturas.
- Criar viatura.
- Ver alertas.
- Ver detalhe de checklist/fuel/trip.

### PWA Motorista

- Bootstrap offline.
- Criar checklist offline.
- Guardar foto local.
- Sincronizar quando online.
- Resolver erro de sync.
- Abrir e fechar viagem.
- Anexar Load Permit offline.
- Registar Manifesto/Custos pendentes quando offline.

## 11. Backlog Tecnico Inicial

### Semana 1

1. Criar repo e estrutura.
2. Registar ADRs.
3. Configurar FastAPI.
4. Configurar SQLAlchemy/Alembic.
5. Criar modelos base.
6. Criar migration inicial.
7. Criar `/health` e `/version`.
8. Criar auth dashboard.
9. Criar seed demo.
10. Criar apps frontend e PWA.

### Semana 2

1. CRUD vehicles.
2. CRUD drivers.
3. Files presign/confirm.
4. Audit logs basicos.
5. Layout dashboard.
6. Bootstrap PWA.

### Semana 3

1. Checklist templates.
2. Execucao checklist online.
3. IndexedDB minimo.
4. `syncQueue`.
5. `photoQueue`.
6. Sync batch backend.

### Semana 4

1. Checklist offline completo.
2. Idempotencia.
3. Alertas de checklist.
4. Testes de offline.

### Semana 5

1. Fuel logs.
2. Upload recibo/odometro.
3. Calculo de consumo.
4. Alertas de anomalia.

### Semana 6

1. Trips.
2. Trip stops.
3. Fecho de viagem.
4. Load Permit.
5. Manifesto de Carga.
6. Guia/documentos de transporte.
7. Documento de descarga.
8. Custos variaveis.

### Semana 7

1. Dashboard operacional.
2. Alert center.
3. Lista de viagens cobraveis/nao cobradas.
4. Documento de cobranca mensal simples.
5. Relatorio mensal simples.
6. Hardening de permissoes.

### Semana 8

1. Dados demo.
2. Testes ponta-a-ponta.
3. Piloto controlado.
4. Guia de onboarding.
5. Lista de incidentes conhecidos.

## 12. Decisoes Ainda Pendentes

- Provedor final de hosting.
- Supabase vs PostgreSQL gerido noutro provedor.
- Cloudflare R2 confirmado ou storage alternativo.
- Politica juridica de retencao.
- Forma exacta de pairing do motorista.
- Se QR code abre PWA por URL normal ou deep link futuro.

Nenhuma destas pendencias deve bloquear a criacao do esqueleto tecnico.
