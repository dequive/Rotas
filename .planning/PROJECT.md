# ROTAS

## Current Milestone: v3.0 — TMS Enterprise Completo

**Goal:** Completar as funcionalidades e integrações avançadas do sistema de gestão de transportes (TMS), incluindo gestão aduaneira e otimização de rotas para rotas transfronteiriças.

**Target features:**
- Gestão aduaneira e desalfandegamento em rotas transfronteiriças (BORDER-01 a BORDER-03)
- Otimização de rotas com múltiplos waypoints e alertas de desvio de rota (OPTIM-01 a OPTIM-03)

---

## What This Is

ROTAS é uma plataforma SaaS multitenant de gestão de frotas construída para operadores logísticos e transportadoras em Moçambique. O produto resolve dois problemas simultaneamente: motoristas precisam registar viagens, abastecimentos e descargas sem conexão confiável (PWA offline-first com Dexie.js + sync independente), e gestores precisam de controle financeiro rigoroso sobre custos de frota, cumprimento documental e faturamento de clientes. É distribuído como SaaS público — qualquer transportadora moçambicana pode contratar e começar a operar.

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
- ✓ **MAINT-01 Scheduler**: `evaluate_maintenance_schedule()` cria WorkOrders e avança próximo ciclo; ARQ worker com cron diário + trigger de odómetro — Validated in Phase 4
- ✓ **Driver Scorecard**: `GET /api/v1/drivers/{id}/scorecard` — score composto 0-100 de 4 dimensões; protegido por RBAC — Validated in Phase 4
- ✓ **Decimal Types**: Todas as colunas `Numeric(x,y)` anotadas com `Mapped[Decimal]`; zero drift no schema — Validated in Phase 4
- ✓ **Composite Indexes**: 10 índices compostos com `tenant_id` como coluna líder em tabelas de alto tráfego — Validated in Phase 4
- ✓ **Railway Deployment**: `railway.toml` com Gunicorn 4-worker + `alembic upgrade head` pre-deploy; pool tuning para produção — Validated in Phase 4
- ✓ **PostgreSQL RLS**: Políticas de isolamento em 47 tabelas; `SET LOCAL app.tenant_id` por transacção; role `rotas_admin` com BYPASSRLS — Validated in Phase 4
- ✓ **UI Panels**: `DriverScorecardPanel` em `/motoristas` e `MaintenanceImminentPanel` no Control Tower — Validated in Phase 4
- ✓ **Cadastro de Clientes (CLI-01 a CLI-05)** — v2.0
- ✓ **Pagamentos (PAY-01 a PAY-03)** — v2.0
- ✓ **Contas a Receber (AR-01 a AR-04)** — v2.0
- ✓ **Infraestrutura de Produção (INFRA-01 a INFRA-03)** — v2.0
- ✓ **Row Level Security (RLS-01 a RLS-03)** — v2.0
- ✓ **Notificações (NOTIF-01 a NOTIF-03)** — v2.0
- ✓ **Onboarding Self-Service (ONBRD-01)** — v2.0
- ✓ **Despacho Financeiro (DESP-01 a DESP-05)** — v2.0
- ✓ **Integração GPS (GPS-01 a GPS-03)** — v2.0
- ✓ **Portal do Cliente / Rastreamento (TRK-01 a TRK-02)** — v2.0

### Active

_Gaps críticos e funcionalidades pendentes de completar para o atual milestone:_

- [ ] **BORDER-01/02/03**: Gestão aduaneira e desalfandegamento em viagens transfronteiriças.
- [ ] **OPTIM-01/02/03**: Otimização de rotas com múltiplos waypoints e alertas de desvio.

### Out of Scope

- **App nativa iOS/Android** — PWA cobre o caso de uso; distribuição via app stores desnecessária
- **GPS streaming via servidor TCP** — dispositivos configurados para HTTP POST; TCP socket não viável em Railway
- **Marketplace B2C** — produto é B2B SaaS para transportadoras
- **Integração com ERP de terceiros** — API própria cobre exportação; integrações são futuro
- **SAFT-MZ / AT certification** — geração de documentos correcta; certificação formal é iniciativa legal separada
- **Carbon/Emissions tracking** — cálculo de CO₂ é v4 (regulação Moçambique não exige ainda)

---

## Key Decisions

| Decision | Phase | Rationale | Outcome |
|----------|-------|-----------|---------|
| Monolito modular (FastAPI) | Complexidade baixa para MVP, fácil de extrair depois | ✓ Good |
| IndexedDB + Dexie.js para offline | Suporte nativo no browser, sem WASM overhead | ✓ Good |
| Row Level Security (RLS) | Segunda camada de isolamento robusta no DB | ✓ Good |
| Redis-Backed Rate Limiting | slowapi + Redis storage compartilha limites entre workers Gunicorn | ✓ Good |
| Flutterwave Mozambique Fallback | Flutterwave MZN mobile money indisponível; fallback para transferência bancária manual | ✓ Good |

---
*Last updated: 2026-06-26 after v2.0 milestone completion*
