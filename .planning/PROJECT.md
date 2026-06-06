# ROTAS

## Current Milestone: v2.0 — Plataforma Operacional Completa

**Goal:** Transformar ROTAS de ferramenta de recolha de dados numa plataforma operacional completa — com visibilidade da frota via GPS integrado, despacho financeiro de motoristas, portal de rastreamento para clientes, notificações proativas, e infraestrutura de produção robusta.

**Target features:**

- Integração GPS (Teltonika, Coban) — mapa de frota em tempo real, geofencing, ETA
- Despacho financeiro completo — adiantamento → despesas → saldo → aprovação → documento
- Manutenção expandida — gestão de pneus, warranty, TCO por viatura (sem IA)
- Portal do cliente — link de rastreamento partilhável + notificação de ETA
- Notificações — email + WhatsApp Business API para alertas e ETAs
- Onboarding self-service — registo autónomo de transportadoras
- Infraestrutura de produção — Sentry, R2/S3, limites de tenant aplicados
- RLS PostgreSQL — segunda camada de isolamento multitenant
- Resolução de conflitos de sync — UI para motorista

---

## What This Is

ROTAS é uma plataforma SaaS multitenant de gestão de frotas construída para operadores logísticos e transportadoras em Moçambique. O produto resolve dois problemas simultaneamente: motoristas precisam registar viagens, abastecimentos e descargas sem conexão confiável (PWA offline-first com Dexie.js + sync idempotente), e gestores precisam de controlo financeiro rigoroso sobre custos de frota, cumprimento documental e faturamento de clientes. É distribuído como SaaS público — qualquer transportadora moçambicana pode contratar e começar a operar.

## Core Value

Um motorista moçambicano consegue completar uma viagem inteira — partida, abastecimento, paradas e descarga — sem conexão, e todos os dados chegam intactos ao gestor quando o sinal reaparecer.

## Requirements

### Validated

_Funcionalidades já implementadas e operacionais no codebase:_

- ✓ **Frota e Pessoas**: Cadastro de viaturas com odômetros, cadastro de motoristas com documentação legal (INATTER, carta de condução), compliance documental com bloqueio de partida por vencimento, disponibilidade com travas de conflito de viagem — existing
- ✓ **Ordens e Viagens**: Trip orders, criação e encerramento de viagens, paradas com custos, diárias/allowance de motoristas — existing
- ✓ **Carga e Manifesto**: Load Permits, manifestos de carga, Guias de Transporte, comprovantes de descarga (delivery proof) como gatilho de faturamento — existing
- ✓ **Checklists dinâmicos**: Templates de inspeção pré e pós-viagem — existing
- ✓ **Combustível**: Registo de abastecimento com custo médio ponderado, tanques internos, conciliação de divergências — existing
- ✓ **Oficina e Manutenção**: Ordens de serviço, gestão de peças sobressalentes, ferramentas calibradas, bloqueio de viatura com OS ativa — existing
- ✓ **Multitenancy**: Isolamento por `tenant_id` em todas as tabelas, JWT com claims de tenant, validação via header `X-Tenant-Id` — existing
- ✓ **Autenticação base**: Login JWT manager (dashboard scope), pareamento de dispositivos driver (driver_app scope) via código temporário — existing
- ✓ **Sync offline base**: `POST /api/v1/sync/batch` com idempotência via `idempotency_keys`, processamento por entity_type — existing
- ✓ **Upload de ficheiros**: Pré-assinatura + upload com validação SHA-256, armazenamento local/R2 — existing
- ✓ **Auditoria**: Logs estruturados com correlation ID, before/after snapshots, UUID do ator — existing
- ✓ **Control Tower base**: Endpoint de KPIs e excepções, alertas vinculados a exceções operacionais — existing

### Active

_Gaps críticos e funcionalidades pendentes de completar para MVP em produção:_

**Segurança e Infraestrutura — Validado em Phase 1 (2026-06-05):**

- ✓ **SEC-01**: JWT_SECRET_KEY `SecretStr` obrigatório — app recusa startup sem a env var
- ✓ **SEC-02**: CORSMiddleware sempre anexado; produção bloqueia CORS_ORIGINS vazio/wildcard
- ✓ **SEC-03**: slowapi 10 req/min em `/auth/login`, `/auth/refresh`, `/driver-auth/pair`
- ✓ **SEC-04**: Cookies com `Secure=true` e `SameSite=lax` quando `NODE_ENV=production`
- ✓ **SEC-05**: CVE-2025-61152 fechado — python-jose substituído por PyJWT>=2.8; alg=none rejeitado
- ✓ **AUTH-03**: `/sync/batch` e `/sync/bootstrap` exigem `get_driver_principal` (scope=driver_app)
- ✓ **DEPLOY-01**: ENVIRONMENT, DATABASE_URL, JWT_SECRET_KEY obrigatórios no startup
- ✓ **DEPLOY-02/03/04**: railway.toml + vercel.json + NEXT_PUBLIC_API_URL prontos; deploy em produção adiado

**PWA Offline-First (Critical):**
- [ ] **PWA-01**: Service Worker implementado com Workbox — cache de assets, fila de sync em background
- [ ] **PWA-02**: Web App Manifest — ícones, display standalone, tema, instalabilidade
- [ ] **PWA-03**: Estratégia de cache network-first para API calls e offline fallback para assets

**Autenticação Completa:**
- [ ] **AUTH-01**: Token refresh no manager Next.js — renovação silenciosa antes de 401 com access token de 15 min
- [ ] **AUTH-02**: Token refresh no driver PWA — renovação automática de token expirado
- [ ] **AUTH-03**: Endpoint de sync (`/api/v1/sync/batch`) validado com `get_driver_principal` (não `get_current_principal`)
- [ ] **AUTH-04**: Sync `update` implementado para todos os entity types (hoje só checklists)

**Billing e Faturamento:**
- [ ] **BILL-01**: Exportação de faturas em PDF com suporte a caracteres moçambicanos (UTF-8 correto, nomes com acentos)
- [ ] **BILL-02**: Exportação de faturas em XLSX formatado
- [ ] **BILL-03**: Validação de margem negativa com waiver de supervisor funcional end-to-end

**Control Tower e Performance:**
- [ ] **CT-01**: Queries do Control Tower otimizadas — substituir ~38 queries sequenciais por queries agregadas
- [ ] **CT-02**: Redis utilizado para cache de KPIs do Control Tower (Redis já provisionado, não usado)
- [ ] **CT-03**: Paginação nas filas do Control Tower (sem limit = risco de memory)

**Deploy e Produção:**
- [ ] **DEPLOY-01**: Variáveis de ambiente documentadas e validadas no startup (Pydantic Settings com `required=True`)
- [ ] **DEPLOY-02**: Deploy do backend FastAPI no Railway ou Render com CI/CD
- [ ] **DEPLOY-03**: Deploy do manager Next.js no Vercel
- [ ] **DEPLOY-04**: Migrações Alembic executadas automaticamente no deploy

### Out of Scope

- **App nativa iOS/Android** — PWA cobre o caso de uso dos motoristas com custo zero de distribuição
- **Tracking GPS em tempo real via servidor** — driver registra GPS no payload de sync; não é streaming
- **Marketplace B2C** — produto é B2B SaaS para transportadoras, não para usuários finais
- **Otimização de rotas por IA** — fora do escopo do MVP; foco é gestão operacional e conformidade
- **Integração com ERP de terceiros** — API própria cobre exportação; integrações são futuro

## Context

- **Mercado-alvo**: Moçambique — dispositivos Android de baixo custo, conectividade intermitente ou ausente fora de Maputo
- **Compliance local**: INATTER (inspeção técnica de veículos), carta de condução válida, seguros e taxas de rádio — regras implementadas no `compliance_policy` JSONB do tenant
- **Multitenant desde o início**: arquitetura suporta N transportadoras; objetivo é SaaS público
- **Stack confirmada pelo codebase**: FastAPI 0.115 + Python 3.12 + SQLAlchemy 2.0 async + PostgreSQL 16 / Next.js 14 App Router + React 18 + Tailwind / Vite + Dexie.js 4
- **Deploy target**: Vercel (manager) + Railway ou Render (backend FastAPI) — infra atual é Docker Compose local
- **Codebase map**: `.planning/codebase/` — 7 documentos de análise gerados em 2026-06-04
- **Gap crítico oculto**: PWA do motorista não tem Service Worker — core do "offline-first" está ausente apesar de toda a lógica de sync já existir no backend

## Constraints

- **Tech stack**: FastAPI + Next.js + Vite/React + PostgreSQL — não mudar stack base
- **Compatibilidade**: Dexie.js 4 já em uso — manter schema IndexedDB compatível ao adicionar SW
- **Dados financeiros**: Colunas de valor monetário precisam migrar de `float` para `Numeric(10,2)` sem perder dados históricos
- **Caracteres locais**: Suporte a UTF-8 completo em todos os outputs (PDF, XLSX) — nomes moçambicanos com acentos e diacríticos
- **Multitenant safety**: Toda query deve filtrar por `tenant_id` — nunca remover esse filtro em otimizações

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Monolito modular (FastAPI) sobre microserviços | Complexidade baixa para MVP, fácil de extrair depois | — Pending validação em produção |
| IndexedDB + Dexie.js para offline (não SQLite WASM) | Suporte nativo no browser, sem WASM overhead | — Pending |
| Tenant isolation na aplicação (não RLS no Postgres) | Mais simples de implementar; risco: bug pode vazar dados entre tenants | ⚠️ Revisitar para v2 com RLS como segunda camada |
| Deploy Vercel + Railway/Render | Sem DevOps próprio para MVP; custo gerido por utilização | — Pending |
| Workbox para Service Worker | Biblioteca padrão para PWA offline com estratégias de cache prontas | — Pending |

## Evolution

Este documento evolui nas transições de fase e marcos de milestone.

**Após cada transição de fase** (via `/gsd:transition`):
1. Requirements invalidados? → Mover para Out of Scope com motivo
2. Requirements validados? → Mover para Validated com referência de fase
3. Novos requirements emergiram? → Adicionar em Active
4. Decisões a registar? → Adicionar em Key Decisions
5. "What This Is" ainda preciso? → Atualizar se derivou

**Após cada milestone** (via `/gsd:complete-milestone`):
1. Revisão completa de todas as secções
2. Core Value check — ainda a prioridade certa?
3. Auditoria de Out of Scope — motivos ainda válidos?
4. Atualizar Context com o estado atual

---
*Last updated: 2026-06-04 after initialization (brownfield, codebase mapped)*
