# Phase 2: PWA Offline-First Completion - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Esta fase torna o driver PWA instalável em Android e funcional sem conexão. Entrega:
1. Service Worker com Workbox (PWA-01) — fila de sync em background + cache de assets
2. Web App Manifest instalável (PWA-02) — ícones, display standalone, tema ROTAS
3. Estratégia de cache network-first/cache-first (PWA-03)
4. Token refresh silencioso no manager Next.js (AUTH-01) e driver PWA (AUTH-02)
5. Sync `update` para todos os entity types no backend (AUTH-04)
6. UX de feedback offline/sync para o motorista

Não inclui: resolução de conflitos com UI (v2), app nativa iOS/Android, GPS streaming.

</domain>

<decisions>
## Implementation Decisions

### Offline Feedback UI
- **D-01:** Banner persistente no topo da app quando offline. Cor laranja (usa `--orange: #b45309` existente). Texto: "Sem ligação — a gravar localmente". Fica visível enquanto offline.
- **D-02:** Quando a conexão volta e a sync automática começa, o banner muda para verde (`--green: #16794c`) com "A sincronizar..." e desaparece após a sync completar com sucesso.
- **D-03:** O botão "Verificar atualizações" (obrigatório pelo `Cache-Control: no-store` do SW) aparece no banner quando a app deteta uma nova versão disponível — não é sempre visível. Contextual apenas.

### Estado de Contagem no Banner
- **D-04:** O banner de estado (offline ou sync) inclui contador de itens pendentes: "X registos pendentes". Reutiliza o mesmo componente de banner.
- **D-05:** Quando itens falham repetidamente (após limite de retries do Workbox), o banner muda para vermelho com "X registos com erro". O motorista sabe que há falhas sem ser interrompido por modais.

### Expiração de Sessão do Motorista (AUTH-02 edge case)
- **D-06:** Se o refresh token expirar (TTL 30 dias), a sync fica bloqueada. A app mostra: "Sessão expirada — contacta o teu gestor para re-parear o dispositivo." App continua totalmente funcional offline — motorista continua a registar viagens, abastecimentos e paradas. Dados ficam em Dexie. Sync só reativa após novo pareamento.
- **D-07:** App totalmente funcional offline mesmo com sessão expirada — apenas a sync fica bloqueada. Motorista não perde acesso às funcionalidades de escrita.

### Revogação de Acesso (novo — não estava em REQUIREMENTS)
- **D-08:** Quando o gestor desativa um motorista no dashboard, a `driver_session` é invalidada no backend. Na próxima sync, o backend retorna 401 com código de erro específico (`driver_access_revoked`). A app distingue este 401 do refresh expirado.
- **D-09:** Dados locais não sincronizados são preservados após revogação. App mostra: "Acesso revogado. Os teus registos locais foram preservados — contacta o teu gestor." Não apaga Dexie.

### Branding do Manifest (PWA-02)
- **D-10:** `name`: "ROTAS Motorista" | `short_name`: "Motorista"
- **D-11:** `theme_color`: `#102033` (alinha com `--nav` do CSS existente — azul-marinho profissional). `background_color`: `#f5f7fa` (alinha com `--soft` do CSS existente).
- **D-12:** Ícones 192x192 e 512x512 gerados como placeholder com letra "R" em fundo `#102033` texto branco. Podem ser substituídos por ícones de produção sem replanear.

### Decisões já fixadas (não re-perguntadas)
- SW servido com `Cache-Control: no-store` (STATE.md)
- Field testing em dispositivo Android real obrigatório para fechar a fase (STATE.md)
- `vite-plugin-pwa` com estratégia `injectManifest` (ROADMAP)
- Network-first para `/api/v1/` calls, cache-first para assets estáticos (ROADMAP)
- In-memory refresh lock para prevenir corridas paralelas de refresh (ROADMAP)
- `client_timestamp` + `server_timestamp` em sync items para clock skew (ROADMAP)
- Resposta de sync com per-item status — falha parcial não marca todos como sincronizados (ROADMAP)

### Claude's Discretion
- Paleta exata de cores do banner (dentro dos CSS vars existentes: `--orange`, `--green`, vermelho a definir)
- Animação/transição do banner (fade vs slide)
- Estrutura interna do componente de banner (hook `useNetworkStatus` + componente `SyncStatusBanner`)
- Estratégia de retry do Workbox (exponential backoff, máximo de tentativas)
- Formato exato do SVG placeholder dos ícones

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos da fase
- `.planning/REQUIREMENTS.md` — PWA-01, PWA-02, PWA-03, AUTH-01, AUTH-02, AUTH-04 (definições completas)
- `.planning/ROADMAP.md` — Phase 2 implementation notes (especificações técnicas detalhadas, gotchas)
- `.planning/STATE.md` — Key decisions: SW Cache-Control, field testing requirement

### Código existente do driver PWA
- `apps/driver/src/sync.ts` — implementação atual do queue de sync (processSyncQueue, uploadQueuedPhotos)
- `apps/driver/src/db.ts` — schema Dexie.js 4 existente (syncQueue, photoQueue, etc.)
- `apps/driver/src/api.ts` — gestão de auth state (getAuth, localStorage tokens)
- `apps/driver/src/App.tsx` — estrutura de views atual (dashboard, checklist, fuel, trip_stop, etc.)
- `apps/driver/src/styles.css` — CSS vars existentes (--nav, --soft, --orange, --green, --ink)
- `apps/driver/vite.config.mjs` — config Vite atual (precisa de vite-plugin-pwa)

### Código existente do manager
- `apps/manager/app/lib/auth.ts` — auth server action atual (sem refresh logic, só cookies)
- `apps/manager/app/lib/api.ts` — fetch wrapper do manager

### Backend relevante
- `backend/app/modules/sync/` — processamento de sync no servidor (entity_type handlers)
- `backend/app/modules/drivers/` — driver auth, driver_sessions table (para revogação)
- `backend/app/modules/auth/` — refresh token endpoint

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `db.ts` — Dexie.js 4 já configurado com `syncQueue`, `photoQueue`, `pendingFuelLogs` — não recriar, apenas estender
- `sync.ts` — `processSyncQueue()` já funcional para operações `create` — AUTH-04 estende para `update`
- `api.ts` — `getAuth()` lê tokens de localStorage — AUTH-02 adiciona refresh antes de expirar
- CSS vars `--orange`, `--green` — usar diretamente no banner de estado

### Established Patterns
- Tokens guardados em `localStorage` (não cookies) no driver — refresh deve seguir o mesmo padrão
- `processSyncQueue()` é chamado em `App.tsx` — o SW Workbox será uma segunda camada, não substituição
- Manager usa cookies HttpOnly via server actions — AUTH-01 deve adicionar refresh no server action layer

### Integration Points
- `vite.config.mjs` — adicionar `vite-plugin-pwa` como plugin
- `main.tsx` — registar o SW
- `App.tsx` — adicionar `SyncStatusBanner` e `useNetworkStatus` hook
- `apps/driver/public/` — adicionar `manifest.webmanifest` e ícones PNG
- `backend/app/modules/sync/router.py` — AUTH-04 estende handlers de entity_type
- `backend/app/modules/drivers/service.py` — D-08 revogação de sessão

</code_context>

<specifics>
## Specific Ideas

- Banner de estado é um componente único que cobre 3 estados: offline (laranja), sincronizando (verde), erro (vermelho). Não são 3 componentes separados.
- O contador "X registos pendentes" vem do `db.syncQueue.where('status').anyOf(['local_only','retrying']).count()`
- O botão "Verificar atualizações" aparece apenas quando o SW deteta um `waiting` worker (evento `updatefound` + `waiting` state)
- Revogação (D-08) requer que o backend distinga 401 por token expirado vs 401 por sessão revogada — usar response body `{"error": "driver_access_revoked"}` para o cliente distinguir

</specifics>

<deferred>
## Deferred Ideas

- Interface de resolução de conflitos para o motorista (quando `base_version` diverge) — v2, já em REQUIREMENTS.md v2
- Scorecard de motoristas baseado em dados de sync — v2
- Notificações push quando sync falha — fora do escopo desta fase

</deferred>

---

*Phase: 02-pwa-offline-first-completion*
*Context gathered: 2026-06-05*
