# Phase 3: Manager Dashboard + Reporting Layer — Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Transformar o ROTAS de ferramenta de recolha de dados em plataforma de gestão operacional. Esta fase entrega:
1. Control Tower queries otimizadas com Redis cache (CT-01, CT-02, CT-03)
2. Exportação de faturas em PDF (UTF-8) e XLSX (BILL-01, BILL-02)
3. Workflow de waiver para margens negativas (BILL-03)
4. Dashboard de KPIs de frota na página /analytics (RPT-01)
5. Painel de alertas proativos de vencimento de documentos (RPT-02)
6. Migração completa do manager para Tailwind CSS + shadcn/ui

Não inclui: notificações por email/WhatsApp (v2), resolução de conflitos de sync, scorecard de motoristas (Fase 4), RLS PostgreSQL.

</domain>

<decisions>
## Implementation Decisions

### UI Framework — Migração Tailwind + shadcn/ui
- **D-01:** Introduzir Tailwind CSS no `apps/manager/`. Instalar `tailwind.config.ts`, `postcss.config.js` e configurar `globals.css` para directivas Tailwind.
- **D-02:** Instalar shadcn/ui como biblioteca de componentes base. Usar `Button`, `Dialog`, `Table`, `Badge`, `Card`, `Select`, `DatePicker` nos novos componentes de KPI, export e waiver.
- **D-03:** Migrar TODOS os componentes existentes do manager para Tailwind — `ControlTowerOverview`, `CostMarginBoard`, `FleetComplianceBoard`, `FuelControlBoard`, `FleetHistoryBoard`, `BillingTripActions`, `TransportCargoActions`, `TransportCargoBoard`, `DriverDespachoTableAdmin`, `SidebarLayout`, e páginas existentes. Classes CSS custom (`tower-metric`, `worklist`, `fleet-fact`, etc.) substituídas por Tailwind.
- **D-04:** CSS custom do `globals.css` existente mantém as variáveis CSS (`:root { --nav, --soft, --ink, ... }`) mas as classes de componente são migradas para Tailwind. As variáveis ficam disponíveis como `bg-[var(--nav)]` etc.

### KPI Dashboard (RPT-01)
- **D-05:** Nova página `/analytics` na sidebar do manager. Rota separada do Control Tower — CT é vista operacional diária, /analytics é vista estratégica de frota.
- **D-06:** Filtros interativos: dropdown de período (este mês, últimos 3 meses, range custom) + filtro de viatura ou motorista. Backend precisa de queries parametrizadas por `period_start`, `period_end`, `vehicle_id?`, `driver_id?`.
- **D-07:** KPIs a mostrar: custo-por-km por viatura (fuel cost + stop costs / total km), utilização de frota % (active trips / total vehicles), consumo de combustível L/100km rolling 30 dias, resumo de viagens por motorista. Todos filtrados por `tenant_id` — obrigatório.

### Export PDF/XLSX (BILL-01, BILL-02)
- **D-08:** Exports são jobs assíncronos via ARQ. Fluxo: manager clica "Exportar PDF/XLSX" → frontend chama endpoint que enfileira job ARQ e retorna `job_id` → frontend faz polling a `GET /api/v1/jobs/{job_id}/status` → quando status é `done`, mostra botão "Descarregar".
- **D-09:** Formato de entrega do ficheiro: à discrição do Claude. Dado que `LOCAL_UPLOAD_DIR` já existe e não há S3/R2, o método mais adequado é guardar o ficheiro no `LOCAL_UPLOAD_DIR` e servir via endpoint autenticado `GET /api/v1/jobs/{job_id}/download`. URL com tenant_id no path para isolamento. Sem URL pública.
- **D-10:** PDF usa `fpdf2 >= 2.8.7` com `DejaVuSans.ttf` embebido (fixado no ROADMAP). XLSX usa `openpyxl`. Ambos gerados no ARQ worker, nunca bloqueando a HTTP response.

### Waiver de Margem Negativa (BILL-03)
- **D-11:** Fluxo de waiver inline na fila de billing: viagens com `margin < 0` mostram badge "Margem negativa" e botão "Solicitar waiver" (disponível a qualquer gestor com role manager, admin ou owner).
- **D-12:** Clicar "Solicitar waiver" abre modal (shadcn/ui `Dialog`) com: detalhe da margem, campo de justificativa (obrigatório), e botão "Submeter pedido". Cria registo de waiver com status `pending_approval`.
- **D-13:** Modal de aprovação separado (visível apenas a owner/admin): mostra justificativa do gestor + detalhe financeiro da viagem + botões "Aprovar" / "Rejeitar". Ao aprovar, `waiver_id` fica associado à viagem e ela pode entrar no ciclo de billing.
- **D-14:** RBAC: `manager` pode solicitar. `owner` e `admin` podem aprovar ou rejeitar. `viewer` não pode fazer nada. Alinha com RBAC existente.

### Redis Cache (CT-02)
- **D-15:** Instalar `redis[asyncio]` no `backend/pyproject.toml`. Cache-aside com chave `ct:kpis:{tenant_id}`, TTL 60s. Chaves de alertas de documentos com TTL 30s.
- **D-16:** ARQ worker deployado como processo separado no Railway (já decidido no ROADMAP). Worker faz refresh assíncrono de KPIs em background.
- **D-17:** Lock de cache stampede via `NX + EX` para prevenir múltiplos workers a recalcular simultaneamente.

### Control Tower (CT-01, CT-03)
- **D-18:** Substituir ~38 queries sequenciais por `joinedload` (many-to-one: trip → vehicle/driver), `selectinload` (one-to-many: trip → stops), `func.count()` SQL-level para KPI scalars. Alvo: 4-6 queries para o payload completo.
- **D-19:** Set `lazy="raise"` nos relationships SQLAlchemy em config de desenvolvimento para detectar lazy loads acidentais.
- **D-20:** Paginação em todas as filas do Control Tower: `page` e `page_size` com cap de 50 por defeito. Sem queries sem LIMIT.
- **D-21 (herdada da Fase 1):** Cada batch de rewrites de queries deve passar pelos cross-tenant regression tests. Este é o ponto de maior risco de fuga de dados entre tenants.

### Alertas de Documentos (RPT-02)
- **D-22:** Painel de alertas proativos mostra viaturas e motoristas com documentos a vencer nos próximos 30 dias. Exibido no Control Tower (já tem `vehicleDocumentsExpiring` e `driverDocumentsExpiring` na API) e também como secção destacada na página /analytics.
- **D-23:** Threshold em 3 níveis: 30 dias (laranja), 15 dias (vermelho claro), 7 dias (vermelho). Display only nesta fase — notificações push/email são v2.

### Claude's Discretion
- Estrutura exata do schema da base de dados para waivers (`waivers` table vs campo em `billing_items`)
- Número de workers ARQ e configuração de retry
- Método de entrega de ficheiro (guia D-09 como orientação)
- Animações/transições shadcn/ui
- Estrutura de pastas para novos componentes Tailwind vs componentes existentes migrados
- Design do polling de jobs (intervalo, número máximo de tentativas, mensagem de erro se timeout)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos da fase
- `.planning/REQUIREMENTS.md` — CT-01, CT-02, CT-03, BILL-01, BILL-02, BILL-03, RPT-01, RPT-02 (definições completas)
- `.planning/ROADMAP.md` — Phase 3 implementation notes (especificações técnicas: `joinedload`, ARQ, `fpdf2`, `openpyxl`, Redis stampede lock)
- `.planning/STATE.md` — Key decisions e accumulated context

### Código existente do manager (a migrar para Tailwind)
- `apps/manager/app/components/ControlTowerOverview.tsx` — componente principal da CT (CSS custom a migrar)
- `apps/manager/app/components/CostMarginBoard.tsx` — painel de margens (CSS custom a migrar)
- `apps/manager/app/components/FleetComplianceBoard.tsx` — painel de compliance (CSS custom a migrar)
- `apps/manager/app/components/BillingTripActions.tsx` — ações de billing (onde waiver entra)
- `apps/manager/app/components/SidebarLayout.tsx` — layout com sidebar (adicionar rota /analytics)
- `apps/manager/app/lib/control-tower-api.ts` — tipos e fetch da CT (referência para CT-01 backend)
- `apps/manager/app/lib/billing-api.ts` — tipos e fetch de billing (referência para BILL-01/02/03)
- `apps/manager/app/globals.css` — CSS vars existentes (preservar :root vars ao migrar para Tailwind)
- `apps/manager/next.config.mjs` — configuração Next.js (referência antes de adicionar Tailwind)
- `apps/manager/package.json` — dependências (adicionar tailwindcss, shadcn/ui, redis)

### Backend relevante
- `backend/app/modules/control_tower/` — router e service do CT (CT-01 rewrite aqui)
- `backend/app/modules/billing/` — domínio de billing + `domain.py` com regras de billing status
- `backend/app/modules/billing/domain.py` — `BillableTripCandidate`, `billing_status_for_candidate` (BILL-03 waiver integra aqui)
- `backend/app/database.py` — session management (padrão para novas queries parametrizadas)
- `backend/pyproject.toml` — adicionar `redis[asyncio]`, `fpdf2`, `openpyxl`, `arq`
- `backend/alembic/versions/` — referência para novas migrations (waiver table, job tracking table)

### Contexto de fases anteriores
- `.planning/phases/01-security-hardening-deploy-foundation/01-CONTEXT.md` — D-21: cross-tenant tests obrigatórios após cada batch de query rewrites
- `.planning/phases/02-pwa-offline-first-completion/02-CONTEXT.md` — padrões UI/UX estabelecidos (não aplicável ao manager)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ControlTowerOverview.tsx` — estrutura de `TowerMetric`, `Worklist`, `FleetFact` reutilizáveis após migração para Tailwind
- `control-tower-api.ts` — tipos TypeScript completos (ControlTower, ControlTowerSummary, etc.) — reutilizar para novos endpoints de KPI
- `billing-api.ts` — `BillingTrip`, `BillingStatus` — estender para waiver fields
- `SidebarLayout.tsx` — adicionar item de nav "/analytics" aqui
- `apiFetch()` em `apps/manager/app/lib/api.ts` — fetch wrapper existente para novos endpoints de jobs/analytics

### Established Patterns
- CSS vars no `:root` (`--nav: #102033`, `--soft: #f5f7fa`, `--ink`, `--orange`, `--green`) — preservar como custom Tailwind tokens ou usar `bg-[var(--nav)]`
- `apiFetch<T>()` com `revalidate` para cache de server components — seguir padrão para `/analytics` data fetching
- Mapeamento snake_case API → camelCase TypeScript (padrão em todos os `*-api.ts`) — seguir para novos endpoints
- RBAC via `get_current_principal` com role check — reutilizar para endpoints de waiver (owner/admin only)
- `billing/domain.py` pattern — regras de domínio separadas de service — seguir para lógica de waiver validation

### Integration Points
- `SidebarLayout.tsx` — adicionar link "/analytics" na navegação
- `apps/manager/app/` — criar `app/analytics/page.tsx` como nova rota Next.js App Router
- `backend/app/modules/billing/router.py` — adicionar endpoints de waiver e export jobs
- `backend/app/modules/control_tower/service.py` — CT-01 rewrite das queries
- `backend/pyproject.toml` — adicionar dependências: `redis[asyncio]`, `arq`, `fpdf2>=2.8.7`, `openpyxl`
- `apps/manager/package.json` — adicionar `tailwindcss`, `@tailwindcss/postcss`, `shadcn/ui`

</code_context>

<specifics>
## Specific Ideas

- Migração Tailwind é total — não há coexistência de dois sistemas de styling. Todos os componentes existentes do manager são migrados na mesma fase.
- A página `/analytics` tem a mesma sidebar que as outras páginas (SidebarLayout) mas conteúdo dedicado a KPIs com filtros.
- O polling de export jobs deve ter feedback visual claro: spinner enquanto aguarda, botão "Descarregar" ao concluir, mensagem de erro se job falhar.
- Waivers seguem o RBAC existente: manager solicita, owner/admin aprova. A modal de aprovação é visível apenas a owner/admin.
- Cross-tenant safety é mandatória em cada nova query (CT-01 rewrite e queries de KPI analytics) — sempre `WHERE tenant_id = ?`.

</specifics>

<deferred>
## Deferred Ideas

- Notificações por email/WhatsApp quando documentos ficam a menos de X dias — v2, já em REQUIREMENTS.md v2
- Scorecard de motoristas (composição de score) — Fase 4
- URL pública com signed URL para exports (S3/R2) — quando R2 for configurado em produção
- WebSocket para atualizações em tempo real da Control Tower — arquitetura atual é polling, WS seria nova infra
- RLS PostgreSQL como segunda camada de isolamento — Fase 4

</deferred>

---

*Phase: 03-manager-dashboard-reporting-layer*
*Context gathered: 2026-06-05*
