# ROTAS - Analise de Absorcao da Consolidacao Kimi

Fonte analisada: `C:\Users\Quive\Downloads\ROTAS_Plano_Mestre_Especificacao_Tecnica_v1.0.docx`  
Data: 2026-05-28  
Objectivo: decidir o que deve entrar na linha de base do ROTAS e o que precisa de ajuste antes de virar especificacao oficial.

## 1. Diagnostico Geral

O documento do Kimi e mais forte que a versao anterior. Ja se aproxima de uma especificacao tecnica executavel porque inclui:

- ADRs de arquitectura.
- Endpoints por modulo.
- Modelo minimo de dados.
- Protocolo offline com IndexedDB.
- Idempotencia.
- Anexo SQL.
- Queries analiticas.
- Template de checklist.
- Diagramas de estado.
- Glossario.
- Checklist da primeira semana.

Veredicto: devemos absorver bastante, mas nao de forma cega. Ha inconsistencias e lacunas que precisam ser corrigidas antes de isto virar base oficial de implementacao.

## 2. Absorver Directamente

### 2.1 ADRs

Absorver:

- ADR-001: Monolito modular.
- ADR-002: PWA + IndexedDB, nao SQLite.
- ADR-003: Multi-tenancy com tenant_id + RLS.
- ADR-004: Alertas internos primeiro, WhatsApp depois.

Motivo: estas decisoes estao alinhadas com a nossa linha de base e evitam complexidade prematura.

### 2.2 Escopo MVP e P0/P1/P2/P3

Absorver a matriz de prioridade porque ajuda a travar escopo inchado.

P0 deve continuar:

- Auth.
- Tenants.
- Viaturas.
- Motoristas.
- Checklists.
- Offline sync.
- Combustivel.
- Viagens.
- Upload de ficheiros.
- Alertas internos.
- Audit logs.

### 2.3 Sync Offline

Absorver:

- IndexedDB com Dexie.js.
- `syncQueue`.
- `photoQueue`.
- Estados de sync: `local_only`, `syncing`, `synced`, `retrying`, `conflict`, `failed`.
- Upload de fotos antes de sincronizar entidades dependentes.
- Backoff exponencial.
- Idempotency key por operacao.
- `POST /api/v1/sync/batch`.

Motivo: isto e uma das pecas mais importantes do produto.

### 2.4 Correcao Legal

Absorver a nota critica:

- Remover a afirmacao antiga sobre "Lei n.o 3/2022".
- Tratar proteccao de dados como "proactive compliance".
- Validar juridicamente antes de vender como conformidade oficial.

### 2.5 Checklist da Primeira Semana

Absorver como plano operacional inicial, mas converter para issues pequenas quando criarmos o repositorio.

## 3. Absorver com Ajustes

### 3.1 Schema SQL

O anexo SQL e uma boa base, mas precisa de ajustes antes de virar migration.

Corrigir:

- Falta tabela `idempotency_keys`, apesar de o texto dizer que o servidor a usa.
- `users.role` nao inclui `driver`, mas a secao RBAC lista `driver`.
- Se motoristas tambem autenticarem, decidir se `drivers` sao tambem `users` ou se terao credencial propria.
- `vehicles.documents JSONB DEFAULT '{...}'` nao e SQL valido para migration.
- `files.entity_type/entity_id` e polimorfico; precisa validacao no service layer e indices por tenant.
- `trip_stops` precisa incluir `resumed_at`, `photo_url` e talvez `expense_category`.
- `trips` precisa `planned_departure`, `actual_departure`, `planned_arrival`, `actual_arrival`, fotos de odometro e estado de entrega.
- `alerts.alert_type` esta restrito demais; faltam `maintenance_due`, `incident_reported`, `driver_document_expiry`.
- `audit_logs.action VARCHAR(50)` pode ficar curto; usar `VARCHAR(100)`.
- `RLS` so mostra policy para `vehicles`; precisamos policy para todas as tabelas com tenant_id.
- Falta tabela `vehicle_accessories` ou `accessories`, mesmo que o modulo fique para pos-MVP.
- Falta tabela `payments/subscriptions`, se billing entrar depois.

### 3.2 Endpoints

A estrutura de endpoints e boa, mas deve ser refinada.

Adicionar:

- Paginacao padrao: `limit`, `offset` ou cursor.
- Filtros consistentes por data, status, vehicle_id, driver_id.
- Endpoint de presigned upload com callback/confirmacao de upload.
- Endpoint de sync deve devolver mapeamento `localId -> serverId`.
- Endpoints de auditoria apenas para roles autorizados.
- Endpoint `/health` e `/version`.

### 3.3 Regras de Conflito Offline

O documento simplifica conflito como "last-write-wins".

Aceitar para:

- Checklists criados offline.
- Paragens de viagem.
- Dados locais que so um motorista edita.

Nao aceitar para:

- Abastecimentos ja verificados pelo gestor.
- Viagens ja fechadas.
- Custos financeiros.
- Alteracoes feitas por gestor no dashboard.

Nesses casos, usar estado `conflict` e revisao manual.

### 3.4 Seguranca

Absorver:

- Access token 15 min.
- Refresh token 7 dias.
- Password com bcrypt.
- Rate limit.
- Hash SHA-256 para fotos.
- RLS como fallback.

Ajustar:

- "GPS e timestamp gerados no servidor" nao e totalmente correcto. GPS nasce no dispositivo; servidor deve gravar `client_captured_at`, `server_received_at`, precisao e origem.
- "AES-256 em repouso" precisa decisao real de implementacao. Pode ser storage/database managed encryption no MVP e field-level encryption depois para INSS/carta.
- Refresh tokens em Redis sao bons, mas se Redis nao entrar no MVP, usar tabela `refresh_tokens`.

## 4. Nao Absorver Ainda

### 4.1 WhatsApp completo no MVP

Manter fora do MVP. Absorver apenas preparacao de alertas internos.

Razao: WhatsApp Cloud API exige conta Meta Business, templates aprovados e gestao de custos. Activar depois de validar eventos realmente uteis.

### 4.2 Retencao legal fixa de 7 anos / 2 anos

Nao tornar oficial sem validacao juridica local.

Pode ficar como hipotese operacional:

- Dados operacionais: manter enquanto necessario para auditoria/contrato.
- Dados pessoais: minimizar, restringir acesso e anonimizar quando possivel.

### 4.3 RLS como unica garantia

Nao depender apenas de RLS.

Base correcta:

- Filtro por tenant no service layer.
- RLS no banco como defesa adicional.
- Testes de isolamento por tenant.

### 4.4 Schema como migration pronta

Nao usar o SQL do anexo directamente sem revisao. Ele e blueprint, nao migration final.

## 5. Lacunas que Ainda Precisamos Fechar

### Produto

- Fluxo exacto do motorista no PWA.
- Fluxo exacto do gestor no dashboard.
- Estados vazios, erros e operacao offline.
- Politica de quem pode aprovar/rejeitar abastecimentos.
- O que bloqueia uma viatura automaticamente.

### Dados

- Modelo final de `users` vs `drivers`.
- Tabela `idempotency_keys`.
- Tabela `refresh_tokens` ou uso de Redis.
- Tabela `vehicle_accessories`.
- Campos de fotos por entidade.
- Tabela ou estrategia para `subscriptions/billing`.

### Engenharia

- Estrutura real do repositorio.
- Convencoes de nomes.
- Padrao de resposta da API.
- Padrao de erros.
- Padrao de permissoes.
- Politica de migrations.
- Testes minimos por modulo.

### Compliance

- Confirmar estado real da lei de proteccao de dados em Mocambique.
- Confirmar requisitos INATTER por tipo de transporte.
- Confirmar regras de armazenamento de documentos pessoais.

## 6. Decisoes a Incorporar no Plano Mestre

Actualizar a linha de base com:

1. Criar secao formal de ADRs.
2. Adicionar especificacao offline detalhada.
3. Adicionar tabela `idempotency_keys` ao modelo minimo.
4. Corrigir `users.role` para incluir ou separar `driver`.
5. Adicionar decisao: GPS tem `client_captured_at` e `server_received_at`.
6. Adicionar decisao: WhatsApp e P1, nao MVP.
7. Adicionar decisao: SQL anexo e blueprint, migrations serao criadas com Alembic.
8. Adicionar decisao: conflitos financeiros exigem revisao manual.

## 7. Veredicto Final

Devemos absorver cerca de 70% da consolidacao do Kimi.

Absorver principalmente:

- ADRs.
- Sync offline.
- Idempotencia.
- Endpoints por modulo.
- Checklist da primeira semana.
- Correcao legal.
- Anexos como ponto de partida.

Revisar antes de oficializar:

- Schema SQL.
- RBAC users/drivers.
- Regras de conflito.
- Retencao legal.
- RLS.
- WhatsApp.

O documento e util, mas a nossa linha de base deve continuar mais rigorosa: MVP pequeno, offline robusto, dados confiaveis e nada de promessas legais ou tecnicas que ainda nao foram validadas.
