# ROTAS — Requirements
_Last updated: 2026-06-06_

## v2.0 Requirements — Gestão de Clientes e Contas a Receber

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

---

## v1 Requirements

### Segurança e Infraestrutura (SEC)

- [ ] **SEC-01**: JWT_SECRET_KEY lido de variável de ambiente obrigatória no startup — eliminar default `"change-me-in-env"`
- [ ] **SEC-02**: CORS configurado para domínios explícitos de produção (Vercel manager + origem mobile) — desativado em `ENVIRONMENT=production` sem env var
- [ ] **SEC-03**: Rate limiting nos endpoints `/auth/login`, `/auth/refresh` e `/driver-auth/pair` — prevenir brute-force e credential stuffing
- [ ] **SEC-04**: Cookies de sessão com flag `Secure` em produção (não apenas `HttpOnly`)
- [ ] **SEC-05**: Migração `python-jose` → `PyJWT >= 2.8` — corrigir CVE-2025-61152 (tokens `alg=none` aceites sem verificação de assinatura = auth bypass completo)

### PWA Offline-First (PWA)

- [x] **PWA-01**: Service Worker implementado com `vite-plugin-pwa` (estratégia `injectManifest`) e `workbox-background-sync` — fila de sync em background para `POST /api/v1/sync/batch`
- [x] **PWA-02**: Web App Manifest com ícones, `display: standalone`, tema e nome da app — PWA instalável em Android
- [x] **PWA-03**: Estratégia de cache network-first para chamadas API e offline fallback para assets estáticos — app carrega sem conexão

### Autenticação Completa (AUTH)

- [x] **AUTH-01**: Token refresh no manager Next.js — renovação silenciosa do access token antes de expirar (access token 15 min, sem 401 silencioso após 15 min)
- [x] **AUTH-02**: Token refresh no driver PWA — renovação automática de token expirado via refresh token emitido no pareamento
- [ ] **AUTH-03**: Endpoint `/api/v1/sync/batch` validado com `get_driver_principal` — apenas dispositivos de motorista autenticados podem submeter sincronizações
- [x] **AUTH-04**: Sync `update` implementado para todos os entity types (viagens, abastecimentos, paradas) — hoje apenas checklists suportados

### Billing e Faturamento (BILL)

- [ ] **BILL-01**: Exportação de faturas em PDF com suporte completo a UTF-8 — nomes moçambicanos com diacríticos renderizados corretamente (fpdf2 + DejaVuSans.ttf)
- [ ] **BILL-02**: Exportação de faturas em XLSX formatado — colunas de valor, data, descrição e totais
- [ ] **BILL-03**: Validação de margem negativa com workflow de waiver de supervisor funcional end-to-end — viagem não entra em fila de faturamento sem aprovação

### Control Tower e Performance (CT)

- [x] **CT-01**: Queries do Control Tower otimizadas — substituir ~38 queries sequenciais por queries agregadas com `selectinload`/`joinedload` e `func.count()` SQL-level (alvo: 4-6 queries)
- [x] **CT-02**: Redis utilizado para cache de KPIs do Control Tower — `redis[asyncio]` instalado, cache-aside com TTL 60s, chaves com namespace `ct:kpis:{tenant_id}`, ARQ worker para processamento assíncrono
- [x] **CT-03**: Paginação nas filas do Control Tower — sem queries sem LIMIT que retornam rows ilimitadas

### Deploy e Produção (DEPLOY)

- [ ] **DEPLOY-01**: Todas as variáveis de ambiente críticas validadas no startup com `Pydantic Settings` — app recusa iniciar sem `JWT_SECRET_KEY`, `DATABASE_URL`, `ENVIRONMENT`
- [ ] **DEPLOY-02**: Deploy do backend FastAPI no Railway ou Render com CI/CD — `railway.toml` com `preDeployCommand = "alembic upgrade head"` ou equivalente Render
- [ ] **DEPLOY-03**: Deploy do manager Next.js no Vercel — `vercel.json` configurado, env vars mapeadas, Node.js 20 LTS
- [ ] **DEPLOY-04**: Migrações Alembic executadas automaticamente no deploy — sem deploy que deixe o schema desatualizado

### Reporting e Analytics (RPT)

- [x] **RPT-01**: Dashboard de KPIs de gestão com custo-por-km por viatura, utilização de frota, tendências de consumo de combustível e resumo de viagens por motorista — gestor consegue tomar decisões operacionais baseadas em dados
- [x] **RPT-02**: Alertas proativos de vencimento de documentos (30/15/7 dias) — viaturas e motoristas com documentos prestes a vencer aparecem em painel antes do bloqueio reativo

---

## v2 Requirements (deferred)

- Manutenção preventiva programada por odômetro/calendário (MAINT-01) — agendador com geração automática de work orders ao atingir intervalos definidos _(Fase 4 MVP)_
- Scorecard de motoristas — pontuação composta a partir de dados de sync já recolhidos (GPS, quilômetros, tempo de paradas)
- RLS PostgreSQL como segunda camada de isolamento multitenant (defense-in-depth) — Alembic migration + `contextvars` + SQLAlchemy event listener
- Integração com canais de notificação (email / WhatsApp Business API) para alertas de vencimento
- Resolução de conflitos de sync com UI para motorista (mensagem explicativa quando `base_version` diverge)

---

## Out of Scope

- **App nativa iOS/Android** — PWA cobre o caso de uso; distribuição via app stores desnecessária para MVP
- **GPS streaming em tempo real via servidor** — driver regista GPS no payload de sync; não é streaming
- **Marketplace B2C** — produto é B2B SaaS para transportadoras
- **Otimização de rotas por IA** — foco do MVP é gestão operacional e conformidade, não roteamento
- **Integração com ERP de terceiros** — API própria cobre exportação; integrações são pós-MVP
- **Integração com cartão de combustível** — mercado moçambicano não tem rede de fuel cards estabelecida
- **Módulo de folha de pagamento de motoristas** — fora do domínio de gestão de frota

### v2.0 Out of Scope

- **Fatura multi-contrato** — uma fatura agrega um único contrato; consolidação por cliente é v2.1
- **Enforcement automático de limite de crédito** — CLI-02 implementa aviso visual apenas; bloqueio de despacho é v2.1
- **Nota de crédito / débito** — requer modelo de journal entry completo; pós-v2.0
- **Multi-moeda** — operações em MZN apenas; FX é pós-v2.0
- **Integração SAFT-MZ / AT certification** — geração de documentos está correta; certificação formal é iniciativa legal separada
- **Múltiplos contactos por cliente** — contacto único por enquanto; tabela `client_contacts` é v2.1

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| SEC-05 | Phase 1 | Pending |
| AUTH-03 | Phase 1 | Pending |
| DEPLOY-01 | Phase 1 | Pending |
| DEPLOY-02 | Phase 1 | Pending |
| DEPLOY-03 | Phase 1 | Pending |
| DEPLOY-04 | Phase 1 | Pending |
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
