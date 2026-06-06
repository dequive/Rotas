# Phase 8: Infrastructure Hardening — Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Tornar o ROTAS production-grade em três dimensões independentes: (1) visibilidade de erros em produção via Sentry com scrubbing de PII, (2) armazenamento durável de ficheiros via R2/S3 para sobreviver a deploys Railway, (3) limites de plano enforced na API com banner de aviso no dashboard.

Esta fase NÃO cobre: RLS PostgreSQL (Phase 9), notificações WhatsApp (Phase 10), onboarding self-service (Phase 10), GPS (Phase 12), nem qualquer feature de produto nova.

</domain>

<decisions>
## Implementation Decisions

### Sentry: Observabilidade

- **D-01:** Um único projecto Sentry chamado `rotas` com três DSNs separados: `SENTRY_DSN_BACKEND` (FastAPI + ARQ worker), `SENTRY_DSN_MANAGER` (Next.js manager), `SENTRY_DSN_DRIVER` (Vite driver PWA). Painel único mas erros identificados por source.
- **D-02:** Sentry desactivado em dev — `sentry_sdk.init()` só corre quando `SENTRY_DSN_BACKEND` está definido e não vazio. Em dev local, variável ausente = Sentry silencioso.
- **D-03:** `before_send` hook strips os seguintes campos de extras e request data: `["driver_name", "cargo_description", "phone", "nuit", "email", "plate_number", "receiver_name", "receiver_contact"]`. Breadcrumbs de SQL também passam pelo scrubber (remover valores de parâmetros que possam conter nomes).
- **D-04:** `traces_sample_rate=0.05` em produção (5%). ARQ worker inicializa Sentry no arranque do worker loop, antes de processar qualquer job.
- **D-05:** `environment` tag do Sentry usa `settings.environment` (`"production"` / `"staging"` / `"development"`).

### R2/S3: Armazenamento de Ficheiros

- **D-06:** Substituir `boto3>=1.43` por `aiobotocore[boto3]>=3.7.0` em `pyproject.toml`. Os dois não podem coexistir — conflito na camada `botocore`.
- **D-07:** Implementar `backend/app/storage.py` com `StorageProvider` enum (`LOCAL`, `R2`) e funções `upload_file()` e `generate_presigned_url()` que despacham com base em `settings.storage_provider`. `files/service.py` passa a usar `storage.py` em vez de lógica inline.
- **D-08:** Novos env vars em `Settings`: `STORAGE_PROVIDER` (default `"local"`), `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`. Todos opcionais se `STORAGE_PROVIDER=local`.
- **D-09:** Script de migração one-shot: `backend/scripts/migrate_files_to_r2.py`. Corre manualmente via CLI antes de mudar `STORAGE_PROVIDER` para `R2`. App continua online durante a migração.
- **D-10:** O script trata `storage_provider IN ('local', 'local_stub')` — o modelo actual usa `default="local_stub"` (não `"local"` como assumido no roadmap). Ambos os valores devem ser incluídos na query de migração.
- **D-11:** Comportamento de falha do script: skip e continua. No final, lista todos os ficheiros que falharam com motivo (ficheiro não encontrado no disco, timeout R2, etc.). Operador decide manualmente. Script termina com exit code 1 se houver falhas, 0 se migração 100% limpa.
- **D-12:** Gate de verificação pós-migração: `SELECT count(*) FROM files WHERE storage_provider IN ('local', 'local_stub')` deve retornar 0 antes de mudar `STORAGE_PROVIDER=R2` no Railway.

### Tenant Limits: Enforcement

- **D-13:** `null` em `max_vehicles`, `max_drivers`, `max_users` significa ilimitado (plano enterprise). Guards fazem skip da verificação quando o campo é `None`. Sem banner, sem 403 para tenants com null.
- **D-14:** Guards `_check_vehicle_limit()`, `_check_driver_limit()`, `_check_user_limit()` adicionados no topo de cada `create_vehicle()`, `create_driver()`, `create_user()` nos respectivos services. Retornam `ApiError("plan_limit_reached", ..., 403)` com body `{"upgrade_url": settings.upgrade_url}`.
- **D-15:** Redis cache de contagens com TTL 30s: chave `tenant:limits:{tenant_id}` com campos `vehicle_count`, `driver_count`, `user_count`. Evita query de COUNT por request. Invalida automaticamente após TTL; sem invalidação manual por agora.
- **D-16:** Novo env var `UPGRADE_URL` em `Settings` (default `""`). Aparece no HTTP 403 body e no banner do dashboard. Permite apontar para página de preços, WhatsApp, email, etc. sem re-deploy.
- **D-17:** Banner `<LimitWarningBanner>` no topo de todas as páginas do manager (dentro do layout principal, acima do conteúdo). Aparece quando qualquer dimensão (veículos, motoristas, utilizadores) está ≥ 80% do limite. Não é dismissível — persiste até utilização baixar ou upgrade. Texto: "Limite de [X]: Y/Z utilizados. [Fazer upgrade →]".
- **D-18:** Endpoint `GET /api/v1/tenant/limits` retorna `{vehicle_count, vehicle_max, driver_count, driver_max, user_count, user_max, upgrade_url}`. `max = null` indica ilimitado. Next.js `layout.tsx` chama este endpoint e renderiza o banner condicionalmente.

### Claude's Discretion

- Estratégia exacta de cache Redis (hash vs múltiplas chaves por dimensão) — planner decide a abordagem mais simples.
- Design visual exacto do `<LimitWarningBanner>` (cor amber/orange, ícone, CTA) — seguir o DESIGN.md do projecto.
- Formato exacto do log de progresso do script de migração (bar de progresso, print por linha, etc.) — Claude decide.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Ficheiros existentes relevantes
- `backend/app/config.py` — Settings model; adicionar R2_*, STORAGE_PROVIDER, SENTRY_DSN_*, UPGRADE_URL
- `backend/app/modules/files/service.py` — Lógica de upload local existente a ser refactorizada para usar storage.py
- `backend/app/modules/files/models.py` — `File.storage_provider` usa `default="local_stub"` (não "local")
- `backend/app/modules/tenants/models.py` — `Tenant.max_vehicles`, `max_drivers`, `max_users` já existem com defaults 5/5/3
- `backend/app/modules/vehicles/service.py` — Adicionar `_check_vehicle_limit()` aqui
- `backend/app/modules/drivers/service.py` — Adicionar `_check_driver_limit()` aqui
- `backend/app/modules/users/service.py` — Adicionar `_check_user_limit()` aqui
- `backend/app/main.py` — Ponto de init do Sentry (lifespan handler)
- `apps/manager/next.config.mjs` — Ponto de init do `@sentry/nextjs`
- `apps/driver/vite.config.mjs` — Ponto de init do `@sentry/vite-plugin`

### Requirements
- `INFRA-01` — Sentry SDK + PII scrubber
- `INFRA-02` — R2/S3 migration + dual-provider
- `INFRA-03` — Tenant limits + dashboard banner

### ROADMAP.md Architecture Constraints (Phase 8)
- `.planning/ROADMAP.md` §Phase 8 — Architecture constraints completas (aiobotocore, storage.py pattern, Redis TTL, LimitWarningBanner)

### Research
- `.planning/research/STACK.md` — Versões confirmadas: `sentry-sdk[fastapi]>=2.61.1`, `aiobotocore[boto3]>=3.7.0`
- `.planning/research/PITFALLS.md` — PITFALL-14 (R2 migration antes de deploy obrigatório), PITFALL-13 (Sentry PII scrubber no init)
- `.planning/research/SUMMARY.md` §Phase 5-A — Visão geral da fase com pitfalls cross-referenciados

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/modules/files/service.py:_tenant_upload_dir()` — path builder para local storage; será movido para `storage.py`
- `backend/app/modules/files/service.py:LOCAL_UPLOAD_PROVIDER` — constante a substituir por enum `StorageProvider`
- `backend/app/database.py:get_session_raw()` — para o script de migração aceder à DB sem RLS
- `backend/app/core/errors.py:ApiError` — padrão de erro já estabelecido; usar para `plan_limit_reached`
- `apps/manager/app/lib/api.ts` — `apiFetch()` existente para chamar `GET /api/v1/tenant/limits` do layout

### Established Patterns
- `ApiError("slug", "message", status_code=N)` — padrão de erro em todos os services
- `settings.environment == "production"` — guard de ambiente existente em `config.py`
- Redis cache já em uso para CT-02 KPIs (chave `ct:kpis:{tenant_id}`) — reutilizar padrão
- `@lru_cache` em `get_settings()` — settings são singleton

### Integration Points
- `apps/manager/app/layout.tsx` — inserir `<LimitWarningBanner>` aqui (Server Component que lê cookie de sessão)
- `backend/app/main.py` lifespan — init Sentry aqui, antes de qualquer request handler
- `pyproject.toml` — substituir `boto3>=1.43` por `aiobotocore[boto3]>=3.7.0`

### Critical Bug Found
- `File.storage_provider` usa `default="local_stub"` no modelo mas a service usa `LOCAL_UPLOAD_PROVIDER = "local"`. O script de migração deve filtrar `storage_provider IN ('local', 'local_stub')` para capturar todos os ficheiros locais.

</code_context>

<specifics>
## Specific Ideas

- O script de migração deve terminar com um resumo claro: "247 uploaded, 0 failed, 0 local records remaining ✓" ou "247 uploaded, 3 FAILED — see list above. Run again or fix manually."
- Banner não dismissível mas pequeno — uma linha de texto amber com link de upgrade. Não modal, não intrusivo. Ver DESIGN.md para tokens de cor (amber: #f59e0b).

</specifics>

<deferred>
## Deferred Ideas

- Dashboard de utilização por tenant para o owner/admin (histórico de crescimento de frota/motoristas) — Phase futuro
- Alertas automáticos de limite por email/WhatsApp ("está a 90% do limite") — Phase 10 (após infra de notificações existir)
- Geofencing de limites de upload por ficheiro individual — fora de escopo

</deferred>

---

*Phase: 08-infrastructure-hardening*
*Context gathered: 2026-06-06*
