# Phase 4: Production Hardening + Scale Preparation — Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Tornar o ROTAS production-grade para SaaS multitenant: scheduler de manutenção preventiva (MAINT-01), scorecard de motoristas, hardening de escalabilidade (Gunicorn, ARQ worker separado, composite indexes), e PostgreSQL RLS como segunda camada de isolamento.

Esta fase NÃO cobre: novas features de UI para motoristas (Phase 2), billing/reporting (Phase 3), ou integrações com canais de notificação (v2).

</domain>

<decisions>
## Implementation Decisions

### MAINT-01: Preventive Maintenance Scheduler

- **D-01:** Trigger combinado — evento de odómetro (imediato, quando FuelLog ou TripStop actualiza odómetro) + cron diário ARQ (safety net para planos por calendário com interval_days). Não usar um mecanismo só.
- **D-02:** Quando o scheduler deteta `odometro_actual >= next_due_km` OR `hoje >= next_due_at`, criar um WorkOrder automaticamente e marcar o `MaintenanceSchedule` actual com `status='triggered'`.
- **D-03:** Criar uma nova entrada `MaintenanceSchedule` para o próximo ciclo: `next_due_km = odometro_trigger + interval_km`, `next_due_at = today + interval_days`. Não fazer reset in-place — manter histórico como entradas separadas.
- **D-04:** Se já existir um WorkOrder aberto (status diferente de 'closed'/'cancelled') para o mesmo `plan_id` + `vehicle_id`, o scheduler faz skip silencioso e regista no log. Sem duplicados.
- **D-05:** Fechar o WorkOrder não tem side effects no scheduler — o próximo MaintenanceSchedule já foi criado no momento do trigger.
- **D-06:** Alertas proactivos no dashboard: viaturas com `due_at <= hoje + 30 dias` OR `due_km <= odometro_actual + 500 km` aparecem num painel de "Manutenção Iminente" antes de vencer.
- **D-07:** O scheduler corre como nova task no mesmo ARQ worker já deployed para CT-02 (não criar worker separado). Cron diário + handler de evento de odómetro.

### Driver Scorecard

- **D-08:** Métricas que compõem o scorecard (todas derivadas de dados já existentes no sistema):
  1. **Distância percorrida** (km) — total de km por viagem e acumulado
  2. **Taxa de entrega comprovada** — % de viagens com delivery proof submetido vs viagens completadas
  3. **Pontualidade de sync** — número de batches de sync submetidos por viagem (proxy de disciplina offline)
  4. **Duração de paradas** — tempo médio de parada relativo à distância da viagem (proxy de eficiência)
- **D-09:** Score composto 0–100 com código de cor: verde ≥ 80, amarelo 60–79, vermelho < 60.
- **D-10:** Período de cálculo: rolling 30 dias (janela móvel — reflecte desempenho recente).
- **D-11:** Scorecard visível apenas ao gestor no manager dashboard. Sem alterações ao driver PWA nesta fase.

### Escalabilidade: Gunicorn + Workers

- **D-12:** Backend FastAPI usa `gunicorn -k uvicorn.workers.UvicornWorker` com 4 workers por instância Railway. `startCommand` em `railway.toml` actualizado.
- **D-13:** ARQ worker (CT-02 + MAINT-01) corre como serviço Railway separado do backend HTTP. Comando: `arq app.jobs.worker.WorkerSettings`. Isolamento de falhas — worker crash não afecta respostas HTTP.
- **D-14:** Composite index audit: identificar as 10 queries de maior volume (trips list, fuel logs, control tower), correr `EXPLAIN ANALYZE` em ambiente de staging, adicionar `CREATE INDEX CONCURRENTLY` onde houver Seq Scan em tabelas > 1 000 rows. Resultado codificado como migration Alembic.

### Numeric/Float Migration

- **D-15 (NOTA DO SCOUT):** Todas as colunas monetárias já usam `Numeric(12,2)` ou `Numeric(14,2)` no DB — não há colunas `Float` reais. O que existe são type hints Python `Mapped[float]` que podem ser actualizados para `Mapped[Decimal]` para rigor de tipo. Esta é uma mudança cosmética de tipos Python, não uma migration de schema. O researcher deve confirmar se existem colunas Float não descobertas.

### PostgreSQL RLS (Row Level Security)

- **D-16:** RLS incluído na Phase 4 como segunda camada de isolamento multitenant (defense-in-depth). O isolamento a nível de código já existe e está testado (Phase 1) — RLS adiciona garantia a nível de base de dados.
- **D-17:** Mecanismo: `SET LOCAL app.tenant_id = '<uuid>'` executado via SQLAlchemy event listener no início de cada transacção/sessão. A policy verifica `current_setting('app.tenant_id')`. Não requer alterações nos queries existentes.
- **D-18:** Dois roles PostgreSQL: `rotas_app` (RLS activo — todas as ligações normais da FastAPI app), `rotas_admin` (BYPASSRLS — ligações de admin e ARQ worker). O `DATABASE_URL` da app usa `rotas_app`; o ARQ worker usa URL separada com `rotas_admin`.
- **D-19:** Alembic migration cria as policies RLS em todas as tabelas com `tenant_id`. Os testes de isolamento cross-tenant escritos na Phase 1 continuam a ser o gate de verificação.

### Claude's Discretion

- Ponderação exacta de cada métrica no score composto do motorista (ex: 40% delivery proof, 30% km, 20% sync, 10% paradas) — o planner/researcher pode propor uma fórmula razoável.
- Quais tabelas específicas precisam de RLS policies vs apenas as principais (trips, vehicles, drivers, fuel) — researcher determina via análise do schema.
- Número exacto de workers Gunicorn pode ser ajustado pelo planner com base no tier Railway e RAM disponível (baseline: 4 workers / 2 GB RAM).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workshop Module (MAINT-01)
- `backend/app/modules/workshop/models.py` — MaintenancePlan (interval_km, interval_days, next_due_km, next_due_at, status) e MaintenanceSchedule (due_km, due_at, status) já existem — não criar novos modelos
- `backend/app/modules/workshop/service.py` — padrões de service layer existentes para WorkOrder creation
- `backend/app/modules/workshop/router.py` — endpoints existentes para referência

### ARQ Worker (CT-02 integração)
- `.planning/phases/03-manager-dashboard-reporting-layer/03-CONTEXT.md` — decisões sobre ARQ worker e Redis para CT-02 (MAINT-01 scheduler partilha o mesmo worker)
- `backend/app/modules/control_tower/service.py` — usa MaintenanceSchedule (linha 145) — verificar antes de alterar

### Vehicles / Odometer (trigger de evento)
- `backend/app/modules/vehicles/service.py` — actualiza odómetro a partir de fuel logs (linha 403-416) — ponto de integração para o evento de trigger

### Database / Index Audit
- `backend/alembic/versions/` — migration history para seguir padrões existentes
- `backend/app/modules/trips/models.py` — tabela de alto volume para composite index
- `backend/app/modules/fuel/models.py` — tabela de alto volume

### RLS
- `backend/app/database.py` — AsyncSession setup e engine config — ponto de integração para SQLAlchemy event listener
- `backend/app/core/auth.py` — get_current_principal extrai tenant_id do JWT — fonte do tenant_id para SET LOCAL

### Roadmap
- `.planning/ROADMAP.md` §Phase 4 — Implementation Notes completas (Gunicorn, MAINT-01, Numeric, RLS, Driver Scorecard)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MaintenancePlan` + `MaintenanceSchedule` (workshop/models.py): modelos já completos com interval_km, interval_days, next_due_km, next_due_at — MAINT-01 só precisa de scheduler logic
- `WorkOrder` model (workshop/models.py): já existe para receber os work orders gerados automaticamente
- `get_driver_principal` / `get_current_principal` (core/auth.py): extrai tenant_id do JWT — reutilizar para SET LOCAL no event listener RLS
- Testes cross-tenant (Phase 1): `backend/tests/test_cross_tenant_isolation.py` — gate de verificação para RLS

### Established Patterns
- Service layer retorna `dict` (não ORM objects) — manter em scorecard service
- ARQ worker pattern: será estabelecido na Phase 3 (CT-02) — MAINT-01 scheduler segue o mesmo padrão
- Alembic migration pattern: `backend/alembic/versions/` — seguir convenções existentes de nomenclatura e estrutura
- `tenant_id` index=True em todas as tabelas — composite indexes adicionam colunas de filtro frequente como segunda coluna

### Integration Points
- Odómetro event trigger: `backend/app/modules/vehicles/service.py` linhas 403-416 (MaintenanceSchedule check existente) — expandir este ponto para disparar ARQ task
- Control Tower dashboard: já agrega MaintenanceSchedule overdue count (linha 145-147) — expandir para alertas iminentes (30 dias/500 km)
- `backend/app/database.py`: ponto para SQLAlchemy event listener RLS

</code_context>

<specifics>
## Specific Ideas

- Scorecard: score 0-100 com verde/amarelo/vermelho (≥80 / 60-79 / <60), rolling 30 dias, só visível ao gestor
- MAINT-01: trigger duplo — imediato via evento de odómetro + safety net cron diário
- RLS: duas roles DB (`rotas_app` com RLS, `rotas_admin` com BYPASSRLS para ARQ worker)
- Gunicorn: 4 workers baseline para Railway 2 GB RAM

</specifics>

<deferred>
## Deferred Ideas

- RLS foi considerado para v2 mas o utilizador decidiu incluir na Phase 4
- Scorecard visível ao motorista no PWA — adiado (apenas gestor no dashboard Phase 4)
- Integrações com canais de notificação (email/WhatsApp) para alertas de manutenção — v2
- Resolução de conflitos de sync com UI — v2

</deferred>

---

*Phase: 04-production-hardening-scale-preparation*
*Context gathered: 2026-06-05*
