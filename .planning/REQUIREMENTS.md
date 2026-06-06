# ROTAS — Requirements
_Last updated: 2026-06-06_

## v2.0 Requirements — Plataforma Operacional Completa

### Cadastro de Clientes (CLI)

- [ ] **CLI-01**: Gestor pode criar, editar e desactivar um cliente com NUIT, nome comercial, morada, cidade, telefone e email — dentro do contexto do seu tenant
- [ ] **CLI-02**: Cliente tem prazo de pagamento padrão configurável (30/45/60/90 dias) e limite de crédito com aviso visual quando o saldo em aberto o ultrapassa
- [ ] **CLI-03**: Sistema migra os registos `client_name` existentes em Contratos e Faturas para referências `client_id` sem perda de dados históricos — `client_name` mantido como cache desnormalizado
- [ ] **CLI-04**: Contrato referencia `client_id`; gestor selecciona cliente ao criar ou editar um contrato
- [ ] **CLI-05**: Faturas emitidas têm número sequencial por tenant sem gaps (formato `AAAA/NNNN`) gerado por PostgreSQL SEQUENCE

### Pagamentos (PAY)

- [ ] **PAY-01**: Gestor pode registar um pagamento total ou parcial contra uma fatura com data valor e método de pagamento (transferência bancária, cheque, numerário)
- [ ] **PAY-02**: Sistema suporta adiantamentos de cliente aplicáveis a faturas futuras do mesmo cliente
- [ ] **PAY-03**: Após registo de pagamento, o saldo em aberto da fatura e o saldo do cliente são actualizados imediatamente

### Contas a Receber (AR)

- [ ] **AR-01**: Extrato do cliente lista todas as faturas de um período com data de emissão, data de vencimento, valor total, valor pago e saldo em aberto
- [ ] **AR-02**: Aging do cliente agrupa o saldo em aberto em buckets: corrente / 1–30 dias / 31–60 dias / 61–90 dias / +90 dias
- [ ] **AR-03**: Dashboard de contas a receber apresenta totais do tenant: valor emitido, recebido, em aberto, e os 5 clientes com maior saldo em aberto
- [ ] **AR-04**: Extrato do cliente exportável em PDF com branding da empresa emissora (nome do tenant)

### Infraestrutura de Produção (INFRA)

- [ ] **INFRA-01**: Erros de produção visíveis no Sentry — SDK integrado no FastAPI backend, ARQ worker, Next.js manager e driver PWA; `before_send` PII scrubber activo para remover dados de motoristas e carga
- [ ] **INFRA-02**: Ficheiros (provas de entrega, PDFs de fatura, documentos de despacho) armazenados em R2/S3 — ficheiros locais existentes migrados antes de activar switch de provider; zero registos `storage_provider=local` após migração
- [ ] **INFRA-03**: Tenant com limite atingido recebe HTTP 403 com `upgrade_url` — `max_vehicles`, `max_drivers` e `max_users` verificados no service layer antes de qualquer inserção; aviso visual a 80% do limite no manager dashboard

### Row Level Security (RLS)

- [x] **RLS-01**: Todas as tabelas com `tenant_id` (47+) protegidas por PostgreSQL RLS — `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + `CREATE POLICY` usando `current_setting('app.tenant_id')`
- [x] **RLS-02**: Roles `rotas_app` (aplica RLS, usado por FastAPI) e `rotas_admin` (BYPASSRLS, usado por Alembic e ARQ worker) criados e configurados no Railway e docker-compose
- [x] **RLS-03**: Test suite de cross-tenant isolation passa sob role `rotas_app` — dados de tenant A inacessíveis quando autenticado como tenant B, mesmo sem filtro explícito na aplicação

### Notificações (NOTIF)

- [ ] **NOTIF-01**: Alertas WhatsApp enviados a gestores quando documentos de viatura/motorista vencem em 30/15/7 dias — 7 templates aprovados pelo Meta, dispatch via ARQ com retry 3 tentativas (30s/5min/30min)
- [ ] **NOTIF-02**: Email enviado como fallback quando contacto não tem WhatsApp opt-in confirmado — SMTP assíncrono via `aiosmtplib`, template em português
- [ ] **NOTIF-03**: Motorista e contacto de cliente só recebem mensagens WhatsApp após `whatsapp_opt_in_confirmed` explicitamente activo no modelo — dispatch guard rejeita envio para não confirmados

### Onboarding Self-Service (ONBRD)

- [ ] **ONBRD-01**: Qualquer transportadora moçambicana pode criar conta ROTAS publicamente — formulário com NUIT, verificação de email por link, criação atómica de tenant + owner numa única transacção; tenant inactivo até verificação concluída

### Despacho Financeiro (DESP)

- [ ] **DESP-01**: Gestor emite adiantamento em dinheiro ao motorista antes da partida — registo com valor, método de pagamento e estado (pending → disbursed → cancelled); vinculado à viagem
- [ ] **DESP-02**: Após encerramento de viagem, sistema calcula liquidação — adiantamento − despesas `paid_by=driver` aprovadas = saldo; saldo positivo significa empresa deve ao motorista, negativo significa motorista deve à empresa
- [ ] **DESP-03**: Gestor aprova ou recusa liquidação com justificação — notificação WhatsApp enviada ao motorista; liquidação só finalizada após aprovação; estado de disputa registado em auditoria
- [ ] **DESP-04**: Documento PDF de liquidação gerado por ARQ task — lista de despesas detalhadas, adiantamento, saldo final e data; disponível para download no manager dashboard
- [ ] **DESP-05**: Viagens transfronteiriças suportam despesas em ZAR com taxa de câmbio MZN/ZAR inserida manualmente pelo gestor no momento da reconciliação

### Integração GPS (GPS)

- [ ] **GPS-01**: Dispositivos GPS de clientes (Teltonika, Coban em modo HTTP POST) enviam posições via `POST /api/v1/gps/webhook/{imei}` autenticado por HMAC-SHA256 por dispositivo — sem JWT; `gps_devices` table valida IMEI antes de resolver `tenant_id` e `vehicle_id`
- [ ] **GPS-02**: Manager dashboard exibe mapa de frota com última posição conhecida de cada viatura — React Query com `refetchInterval` de 10 segundos; indicador de staleness quando posição tem mais de 5 minutos
- [ ] **GPS-03**: ETA estimado exibido no Control Tower para viagens ativas — calculado com base na distância restante em `known_routes` e velocidade actual reportada pelo GPS

### Portal do Cliente / Rastreamento (TRK)

- [ ] **TRK-01**: Gestor gera link de rastreamento partilhável por viagem — cliente acede à página `/track/[token]` sem login, vê estado da entrega, última posição em texto e foto de entrega; token de 256 bits com rate limit de 30 req/min por IP
- [ ] **TRK-02**: Página de rastreamento actualiza automaticamente de 5 em 5 minutos e exibe indicador visual quando dados de posição têm mais de 5 minutos (dado stale)

---

## v1 Requirements

### Segurança e Infraestrutura (SEC)

- [x] **SEC-01**: JWT_SECRET_KEY lido de variável de ambiente obrigatória no startup — eliminar default `"change-me-in-env"`
- [x] **SEC-02**: CORS configurado para domínios explícitos de produção (Vercel manager + origem mobile) — desativado em `ENVIRONMENT=production` sem env var
- [x] **SEC-03**: Rate limiting nos endpoints `/auth/login`, `/auth/refresh` e `/driver-auth/pair` — prevenir brute-force e credential stuffing
- [x] **SEC-04**: Cookies de sessão com flag `Secure` em produção (não apenas `HttpOnly`)
- [x] **SEC-05**: Migração `python-jose` → `PyJWT >= 2.8` — corrigir CVE-2025-61152

### PWA Offline-First (PWA)

- [x] **PWA-01**: Service Worker implementado com `vite-plugin-pwa` (estratégia `injectManifest`) e `workbox-background-sync`
- [x] **PWA-02**: Web App Manifest com ícones, `display: standalone`, tema e nome da app — PWA instalável em Android
- [x] **PWA-03**: Estratégia de cache network-first para chamadas API e offline fallback para assets estáticos

### Autenticação Completa (AUTH)

- [x] **AUTH-01**: Token refresh no manager Next.js — renovação silenciosa do access token antes de expirar
- [x] **AUTH-02**: Token refresh no driver PWA — renovação automática de token expirado via refresh token
- [x] **AUTH-03**: Endpoint `/api/v1/sync/batch` validado com `get_driver_principal`
- [x] **AUTH-04**: Sync `update` implementado para todos os entity types

### Billing e Faturamento (BILL)

- [ ] **BILL-01**: Exportação de faturas em PDF com suporte completo a UTF-8 — nomes moçambicanos com diacríticos renderizados corretamente (fpdf2 + DejaVuSans.ttf)
- [ ] **BILL-02**: Exportação de faturas em XLSX formatado — colunas de valor, data, descrição e totais
- [ ] **BILL-03**: Validação de margem negativa com workflow de waiver de supervisor funcional end-to-end

### Control Tower e Performance (CT)

- [x] **CT-01**: Queries do Control Tower otimizadas — substituir ~38 queries sequenciais por queries agregadas
- [x] **CT-02**: Redis utilizado para cache de KPIs do Control Tower
- [x] **CT-03**: Paginação nas filas do Control Tower

### Deploy e Produção (DEPLOY)

- [x] **DEPLOY-01**: Variáveis de ambiente críticas validadas no startup com `Pydantic Settings`
- [x] **DEPLOY-02**: Deploy do backend FastAPI no Railway com CI/CD
- [x] **DEPLOY-03**: Deploy do manager Next.js no Vercel
- [x] **DEPLOY-04**: Migrações Alembic executadas automaticamente no deploy

### Reporting e Analytics (RPT)

- [x] **RPT-01**: Dashboard de KPIs de gestão com custo-por-km, utilização de frota, tendências de combustível
- [x] **RPT-02**: Alertas proativos de vencimento de documentos (30/15/7 dias)

### Manutenção (MAINT)

- [x] **MAINT-01**: Manutenção preventiva programada por odômetro/calendário com geração automática de work orders

---

## Out of Scope

- **App nativa iOS/Android** — PWA cobre o caso de uso; distribuição via app stores desnecessária
- **GPS streaming via servidor TCP** — dispositivos configurados para HTTP POST; TCP socket não viável em Railway
- **Marketplace B2C** — produto é B2B SaaS para transportadoras
- **Otimização de rotas por IA** — foco é gestão operacional e conformidade
- **Integração com ERP de terceiros** — API própria cobre exportação; integrações são futuro
- **Integração com cartão de combustível** — mercado moçambicano não tem rede de fuel cards
- **Módulo de folha de pagamento de motoristas** — fora do domínio de gestão de frota
- **Cadeia de frio / monitorização de temperatura** — nicho, adiar para v3
- **Geofencing** — requer PostGIS não confirmado no Railway; bounding-box é v2.1
- **Stripe pagamento activado** — webhook wired mas checkout desactivado; pagamento automático é v2.1
- **Trial de 14 dias** — onboarding self-service entra directamente com plano; trial é v2.1
- **Fatura multi-contrato** — uma fatura agrega um único contrato; consolidação é v2.1
- **Nota de crédito / débito** — requer journal entry completo; pós-v2.0
- **Multi-moeda em faturamento cliente** — operações em MZN; FX em faturas é v2.1
- **SAFT-MZ / AT certification** — geração de documentos correcta; certificação formal é iniciativa legal separada

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Complete |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| SEC-05 | Phase 1 | Complete |
| AUTH-03 | Phase 1 | Complete |
| DEPLOY-01 | Phase 1 | Complete |
| DEPLOY-02 | Phase 1 | Complete |
| DEPLOY-03 | Phase 1 | Complete |
| DEPLOY-04 | Phase 1 | Complete |
| PWA-01 | Phase 2 | Complete |
| PWA-02 | Phase 2 | Complete |
| PWA-03 | Phase 2 | Complete |
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-04 | Phase 2 | Complete |
| CT-01 | Phase 3 | Complete |
| CT-02 | Phase 3 | Complete |
| CT-03 | Phase 3 | Complete |
| BILL-01 | Phase 3 | Pending |
| BILL-02 | Phase 3 | Pending |
| BILL-03 | Phase 3 | Pending |
| RPT-01 | Phase 3 | Complete |
| RPT-02 | Phase 3 | Complete |
| MAINT-01 | Phase 4 | Complete |
| CLI-01 | Phase 5 | Pending |
| CLI-02 | Phase 5 | Pending |
| CLI-03 | Phase 5 | Pending |
| CLI-04 | Phase 5 | Pending |
| CLI-05 | Phase 5 | Pending |
| PAY-01 | Phase 6 | Pending |
| PAY-02 | Phase 6 | Pending |
| PAY-03 | Phase 6 | Pending |
| AR-01 | Phase 7 | Pending |
| AR-02 | Phase 7 | Pending |
| AR-03 | Phase 7 | Pending |
| AR-04 | Phase 7 | Pending |
| INFRA-01 | Phase 8 | Pending |
| INFRA-02 | Phase 8 | Pending |
| INFRA-03 | Phase 8 | Pending |
| RLS-01 | Phase 9 | Complete |
| RLS-02 | Phase 9 | Complete |
| RLS-03 | Phase 9 | Complete |
| NOTIF-01 | Phase 10 | Pending |
| NOTIF-02 | Phase 10 | Pending |
| NOTIF-03 | Phase 10 | Pending |
| ONBRD-01 | Phase 10 | Pending |
| DESP-01 | Phase 11 | Pending |
| DESP-02 | Phase 11 | Pending |
| DESP-03 | Phase 11 | Pending |
| DESP-04 | Phase 11 | Pending |
| DESP-05 | Phase 11 | Pending |
| GPS-01 | Phase 12 | Pending |
| GPS-02 | Phase 12 | Pending |
| GPS-03 | Phase 12 | Pending |
| TRK-01 | Phase 12 | Pending |
| TRK-02 | Phase 12 | Pending |
