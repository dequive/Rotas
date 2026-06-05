# Phase 2: PWA Offline-First Completion — Research

**Researched:** 2026-06-05
**Domain:** Service Workers / Workbox / vite-plugin-pwa / Token Refresh / Sync Backend Extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Banner persistente no topo da app quando offline. Cor laranja (`--orange: #b45309`). Texto: "Sem ligação — a gravar localmente".
- **D-02:** Quando a conexão volta e a sync automática começa, o banner muda para verde (`--green: #16794c`) com "A sincronizar..." e desaparece após a sync completar.
- **D-03:** Botão "Verificar atualizações" aparece no banner apenas quando SW deteta nova versão disponível (SW `waiting` state). Contextual, não sempre visível.
- **D-04:** Banner inclui contador "X registos pendentes". Mesmo componente de banner.
- **D-05:** Itens que falham repetidamente mudam banner para vermelho com "X registos com erro".
- **D-06:** Se refresh token expirar (TTL 30 dias), sync fica bloqueada. App mostra "Sessão expirada — contacta o teu gestor para re-parear o dispositivo." App continua funcional offline.
- **D-07:** App totalmente funcional offline mesmo com sessão expirada — apenas a sync fica bloqueada.
- **D-08:** Gestor desativa motorista → `driver_session` invalidada → próxima sync retorna 401 com `driver_access_revoked` no body.
- **D-09:** Dados locais não sincronizados preservados após revogação. App mostra mensagem específica. Não apaga Dexie.
- **D-10:** `name`: "ROTAS Motorista" | `short_name`: "Motorista"
- **D-11:** `theme_color`: `#102033` | `background_color`: `#f5f7fa`
- **D-12:** Ícones 192×192 e 512×512 PNG placeholder com letra "R" em fundo `#102033` texto branco.
- SW servido com `Cache-Control: no-store` (STATE.md)
- Field testing em dispositivo Android real obrigatório para fechar a fase (STATE.md)
- `vite-plugin-pwa` com estratégia `injectManifest` (ROADMAP)
- Network-first para `/api/v1/` calls, cache-first para assets estáticos (ROADMAP)
- In-memory refresh lock para prevenir corridas paralelas de refresh (ROADMAP)
- `client_timestamp` + `server_timestamp` em sync items para clock skew (ROADMAP)
- Resposta de sync com per-item status (ROADMAP)

### Claude's Discretion
- Paleta exata de cores do banner (dentro dos CSS vars existentes: `--orange`, `--green`, vermelho a definir)
- Animação/transição do banner (fade vs slide)
- Estrutura interna do componente de banner (hook `useNetworkStatus` + componente `SyncStatusBanner`)
- Estratégia de retry do Workbox (exponential backoff, máximo de tentativas)
- Formato exato do SVG placeholder dos ícones

### Deferred Ideas (OUT OF SCOPE)
- Interface de resolução de conflitos para o motorista (quando `base_version` diverge) — v2
- Scorecard de motoristas baseado em dados de sync — v2
- Notificações push quando sync falha — fora do escopo desta fase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PWA-01 | Service Worker com `vite-plugin-pwa` (estratégia `injectManifest`) e `workbox-background-sync` — fila de sync em background para `POST /api/v1/sync/batch` | vite-plugin-pwa 1.3.0 config, workbox-background-sync 7.4.1 BackgroundSyncPlugin, sw.ts structure documented |
| PWA-02 | Web App Manifest com ícones, `display: standalone`, tema e nome da app — PWA instalável em Android | manifest.webmanifest contract fully specified in UI-SPEC.md |
| PWA-03 | Estratégia de cache network-first para chamadas API e offline fallback para assets estáticos | workbox-routing + workbox-strategies NetworkFirst/CacheFirst patterns documented |
| AUTH-01 | Token refresh no manager Next.js — renovação silenciosa do access token antes de expirar | `POST /api/v1/auth/refresh` endpoint exists, handles both user and driver tokens; refresh token stored in cookie |
| AUTH-02 | Token refresh no driver PWA — renovação automática de token expirado via refresh token emitido no pareamento | `POST /api/v1/auth/refresh` accepts `{"refresh_token": "..."}`, driver refresh token must be stored in localStorage; in-memory lock pattern documented |
| AUTH-04 | Sync `update` implementado para todos os entity types (viagens, abastecimentos, paradas, delivery_proof) | `_dispatch_update` in sync/service.py currently only handles `checklist`; extension pattern clear |
</phase_requirements>

---

## Summary

Phase 2 makes the driver PWA installable on Android and fully functional offline. The codebase already has Dexie.js 4 managing domain persistence (syncQueue, photoQueue) and a working `processSyncQueue()` that handles `create` operations for all entity types. What is missing is: (1) the Service Worker layer (vite-plugin-pwa + Workbox), (2) the web app manifest and icons, (3) silent token refresh in both apps, and (4) `update` operation support in the backend sync service.

The architecture is dual-layer by design: Dexie handles domain persistence (entities survive device restarts, network is irrelevant), while Workbox background sync handles the network transport queue. Both layers are required and complementary — they solve different problems.

The key gotcha for this phase is `Cache-Control: no-store` on the service worker file itself. A cached broken SW is unrecoverable on low-cost Android without clearing site data. This must be set at the server/hosting layer (Vite dev server headers config + Vercel headers config for production). A visible "Verificar atualizações" button gives the manager a recovery path.

**Primary recommendation:** Implement vite-plugin-pwa with `registerType: 'prompt'` + manual `workbox-window` registration in `main.tsx`, not `autoUpdate`, so the app controls when to skip waiting and can surface the update banner to the driver.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite-plugin-pwa | 1.3.0 (latest) | Vite integration for SW generation, manifest injection | Official Vite PWA plugin, maintained by antfu; wraps workbox-build |
| workbox-precaching | 7.4.1 | Precache and serve static assets from SW | Part of the Workbox suite; handles cache versioning automatically |
| workbox-routing | 7.4.1 | Route matching inside SW (API vs assets) | Required for NetworkFirst/CacheFirst strategy routing |
| workbox-strategies | 7.4.1 | NetworkFirst, CacheFirst strategy implementations | Official Workbox strategies |
| workbox-background-sync | 7.4.1 | Background sync queue for failed HTTP requests | Survives browser restarts; uses BackgroundSync API with fallback |
| workbox-core | 7.4.1 | clientsClaim, skipWaiting, core utilities | Required companion to precaching |
| workbox-build | 7.4.1 | Peer dependency of vite-plugin-pwa; compiles sw.ts | Must match workbox-* version |
| workbox-window | 7.4.1 | Client-side SW registration and lifecycle events | Required by vite-plugin-pwa for useRegisterSW; detects waiting worker |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @vite-pwa/assets-generator | 1.0.2 (latest) | Optional icon generation CLI | Use if generating icons from SVG source; optional for placeholder PNGs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| vite-plugin-pwa | Manual SW with importScripts | More control but loses manifest injection automation; 10x more boilerplate |
| BackgroundSyncPlugin | Custom SW fetch queue | BackgroundSyncPlugin only retries on network exceptions, not 4xx/5xx; custom queue (Dexie syncQueue) already exists for that case |

**Installation:**
```bash
# From apps/driver/
npm install --save-dev vite-plugin-pwa workbox-build workbox-window
npm install workbox-precaching workbox-routing workbox-strategies workbox-background-sync workbox-core
```

**Version verification (confirmed against npm registry 2026-06-05):**
- `vite-plugin-pwa`: 1.3.0
- `workbox-background-sync`, `workbox-build`, `workbox-precaching`, `workbox-routing`, `workbox-strategies`, `workbox-core`, `workbox-window`: all 7.4.1

---

## Architecture Patterns

### Recommended Project Structure (changes only)
```
apps/driver/
├── public/
│   ├── manifest.webmanifest   # NEW — web app manifest (PWA-02)
│   ├── icon-192.png            # NEW — 192×192 PNG placeholder icon
│   └── icon-512.png            # NEW — 512×512 PNG placeholder icon
├── src/
│   ├── sw.ts                   # NEW — custom service worker (PWA-01, PWA-03)
│   ├── hooks/
│   │   ├── useNetworkStatus.ts # NEW — navigator.onLine + online/offline events
│   │   └── useSyncStatus.ts    # NEW — aggregates banner state machine
│   ├── components/
│   │   └── SyncStatusBanner.tsx # NEW — replaces .offline-bar footer
│   ├── api.ts                  # MODIFY — add refreshToken(), withTokenRefresh()
│   ├── App.tsx                 # MODIFY — add SyncStatusBanner, remove .offline-bar
│   ├── main.tsx                # MODIFY — register SW via workbox-window
│   └── ...
├── tsconfig.json               # MODIFY — add "WebWorker" to lib
└── vite.config.mjs             # MODIFY — add VitePWA plugin
```

### Pattern 1: vite-plugin-pwa injectManifest configuration

**What:** Configure vite-plugin-pwa with `strategies: 'injectManifest'` to compile `src/sw.ts` as the custom service worker. The plugin injects the precache manifest into the SW at build time.

**When to use:** Always for this project — injectManifest gives full control over the SW code, required to add background sync routing on top of standard precaching.

**Example (vite.config.mjs):**
```typescript
// Source: https://vite-pwa-org.netlify.app/guide/inject-manifest.html
import { VitePWA } from 'vite-plugin-pwa';
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  cacheDir: "../../node_modules/.vite/driver",
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'prompt',   // driver controls SKIP_WAITING via banner button
      injectRegister: false,    // manual registration in main.tsx for full control
      manifest: {
        name: 'ROTAS Motorista',
        short_name: 'Motorista',
        display: 'standalone',
        start_url: '/',
        theme_color: '#102033',
        background_color: '#f5f7fa',
        lang: 'pt',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      devOptions: {
        enabled: true,          // enable SW in dev mode for testing
        type: 'module',
      },
    }),
  ],
  server: {
    port: 5174,
    strictPort: false,
    headers: {
      // CRITICAL: prevent SW from being cached — broken cached SW is unrecoverable
      'Cache-Control': 'no-store',
    },
  },
});
```

**NOTE on server.headers:** The `headers` option in `server` config applies to ALL dev server responses. For production (Vercel), `Cache-Control: no-store` must be set specifically for `/sw.js` via `vercel.json` headers config — not globally. In dev, applying it globally is acceptable.

### Pattern 2: sw.ts service worker implementation

**What:** Custom SW using Workbox that handles precaching, network-first API routing, and background sync queue.

**Example (src/sw.ts):**
```typescript
// Source: https://vite-pwa-org.netlify.app/guide/inject-manifest.html
//         https://developer.chrome.com/docs/workbox/modules/workbox-background-sync
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, CacheFirst } from 'workbox-strategies';
import { BackgroundSyncPlugin } from 'workbox-background-sync';
import { clientsClaim } from 'workbox-core';

declare let self: ServiceWorkerGlobalScope;

// Prompt-for-update pattern: only skip waiting on explicit message
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

clientsClaim();
cleanupOutdatedCaches();

// Precache static assets (manifest injected by vite-plugin-pwa at build time)
precacheAndRoute(self.__WB_MANIFEST);

// Background sync queue for batch sync — retries on reconnect
// IMPORTANT: BackgroundSyncPlugin only triggers on network exceptions (fetch throws),
// NOT on 4xx/5xx HTTP responses. The Dexie syncQueue handles those cases.
const bgSyncPlugin = new BackgroundSyncPlugin('rotas-sync-queue', {
  maxRetentionTime: 24 * 60, // 24 hours in minutes
});

// Network-first for all API calls
// Rationale: stale financial data is worse than no data
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [bgSyncPlugin],
    networkTimeoutSeconds: 10,
  }),
  'POST'
);

registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 10,
  }),
  'GET'
);

// Cache-first for static assets (JS, CSS, images)
registerRoute(
  ({ request }) => request.destination === 'script' ||
                   request.destination === 'style' ||
                   request.destination === 'image',
  new CacheFirst({ cacheName: 'static-assets' }),
);
```

**CRITICAL GOTCHA — BackgroundSyncPlugin scope:** The BackgroundSyncPlugin with NetworkFirst strategy provides a SECOND sync layer for network failures (offline device). The Dexie `syncQueue` is the PRIMARY layer (handles app logic, 4xx/5xx, idempotency). Do not remove the Dexie layer — the Workbox layer only handles true network outages.

### Pattern 3: SW registration in main.tsx with workbox-window

**What:** Manual SW registration using `workbox-window`'s `Workbox` class to detect waiting workers and expose SW lifecycle to the banner.

**Example (src/main.tsx addition):**
```typescript
// Source: https://vite-pwa-org.netlify.app/guide/inject-manifest.html
import { Workbox } from 'workbox-window';

if ('serviceWorker' in navigator) {
  const wb = new Workbox('/sw.js');

  wb.addEventListener('waiting', () => {
    // Dispatch custom event — useSyncStatus hook listens for this
    window.dispatchEvent(new CustomEvent('sw-update-available', { detail: { wb } }));
  });

  wb.register();
}
```

### Pattern 4: In-memory refresh lock for token refresh (AUTH-02 driver PWA)

**What:** Prevents parallel token refresh races when multiple API calls fire simultaneously with an expired token.

**When to use:** Any time the driver PWA makes an API call. The lock ensures only one refresh runs at a time; concurrent callers wait for the same promise.

**Example (addition to src/api.ts):**
```typescript
// In-memory refresh lock — module-level singleton
let refreshPromise: Promise<string | null> | null = null;

async function ensureFreshToken(): Promise<string | null> {
  const auth = getAuth();
  if (!auth) return null;

  // Check if token is close to expiry (within 60s of 15-min TTL)
  // Since driver tokens don't embed expiry in localStorage, we use
  // token creation time tracking OR attempt refresh on 401 response
  // The simplest approach: refresh on 401, with lock to prevent races
  return auth.accessToken;
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise; // return existing in-flight promise

  const refreshToken = localStorage.getItem('rotas_refresh_token');
  if (!refreshToken) return null;

  refreshPromise = fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        // Distinguish expired TTL from access revocation
        if (body.detail === 'driver_access_revoked' || body.error === 'driver_access_revoked') {
          window.dispatchEvent(new CustomEvent('driver-access-revoked'));
        } else {
          window.dispatchEvent(new CustomEvent('session-expired'));
        }
        return null;
      }
      const data = await res.json();
      localStorage.setItem('rotas_access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('rotas_refresh_token', data.refresh_token);
      }
      return data.access_token as string;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}
```

**CRITICAL FINDING — refresh_token storage:** The driver PWA currently stores `access_token` in localStorage but does NOT store the `refresh_token`. The `pair_driver_device` endpoint returns both `access_token` and `refresh_token`. The `pairDevice()` function in `api.ts` only stores `access_token`. This is a gap that must be fixed as part of AUTH-02: store `rotas_refresh_token` in localStorage during pairing.

### Pattern 5: Manager token refresh (AUTH-01 — Next.js server action)

**What:** The manager uses HttpOnly cookies managed by Next.js server actions. The refresh token is already issued at login (the login endpoint returns `refresh_token`), but `auth.ts` currently does NOT store it.

**Gap found:** `auth.ts` `login()` function stores `access_token` cookie but does NOT store the `refresh_token` cookie. To implement AUTH-01, the login action must store the `refresh_token` in an HttpOnly cookie, and `apiFetch()` in `api.ts` must handle 401 responses by calling `/auth/refresh` and retrying.

**Refresh endpoint (confirmed):**
- `POST /api/v1/auth/refresh` with body `{"refresh_token": "<opaque_token>"}`
- Returns `{"access_token": "...", "refresh_token": "...", ...}`
- Refresh is a token-rotation scheme: old `refresh_token` is revoked on use

### Pattern 6: Backend AUTH-04 — sync update extension

**What:** Extend `_dispatch_update()` in `backend/app/modules/sync/service.py` to handle `trip`, `fuel_log`, `trip_stop`, and `delivery_proof` update operations.

**Current state:** `_dispatch_update` only handles `checklist`. Returns `unsupported_entity_type_for_update` for all other types.

**Pattern to follow:** The `_dispatch_create` function is the reference implementation — each entity type follows the same `if entity_type == "X"` branching pattern.

**Schemas that must exist for update (to verify or create):**
- `trip`: Check if `TripPatch` schema exists in `trips/schemas.py` (not observed — may need creation or use of `start_trip`/`complete_trip` action schemas)
- `fuel_log`: Check `FuelLogPatch` in `fuel/schemas.py`
- `trip_stop`: Likely uses a partial update
- `delivery_proof`: Likely uses a partial update

**CRITICAL:** Update operations require `server_id` in the payload (already enforced by `_dispatch_update`). The client must include the server-assigned ID when recording an update operation in Dexie.

### Anti-Patterns to Avoid

- **Never use `registerType: 'autoUpdate'`** for this app: `autoUpdate` calls `self.skipWaiting()` unconditionally, which can reload the app mid-operation for a driver recording a delivery. Always use `'prompt'` and let the driver choose when to update.
- **Never cache POST responses via NetworkFirst with background sync for non-idempotent writes:** The Workbox background sync queue will retry failed POST requests. Since our sync endpoint is idempotent (idempotency_key enforced), this is safe. But never add background sync to non-idempotent endpoints.
- **Never skip `Cache-Control: no-store` on sw.js in production:** If a broken SW is cached, the only fix is "Clear site data" — low-cost Android users cannot be expected to do this.
- **Never read refresh_token from localStorage after a successful refresh without updating Dexie-stored state:** The token rotation means the old refresh token is immediately invalid. Any stale copy will cause auth failure on next refresh.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Precache manifest generation | Custom build script | `vite-plugin-pwa` (injectManifest) | Cache busting via content hash is complex; plugin handles versioning |
| SW waiting detection | Custom navigator.serviceWorker polling | `workbox-window` `Workbox` class + `waiting` event | Handles edge cases: first install vs update, page reload races |
| Background sync queue | Custom fetch queue in SW | `workbox-background-sync` `BackgroundSyncPlugin` | Hooks into BackgroundSync API natively; falls back to SW startup replay |
| SW compilation from TypeScript | Custom Rollup config | `vite-plugin-pwa` `injectManifest` with `srcDir`/`filename` | Plugin handles TS compilation with correct SW globals (ServiceWorkerGlobalScope) |

**Key insight:** The SW compilation environment is not the same as the app environment — `window` is undefined, `self` is `ServiceWorkerGlobalScope`. Vite-plugin-pwa handles this compilation context correctly; hand-rolled solutions frequently fail to set the correct output format (`iife` is required for SW bundles compiled by vite-plugin-pwa's internal build).

---

## Common Pitfalls

### Pitfall 1: Cached broken Service Worker (the unrecoverable failure)
**What goes wrong:** SW file is served with default `Cache-Control` (which allows caching). A bug is deployed in the SW. Browser keeps serving the cached broken SW. `no-store` on sw.js is the only prevention.
**Why it happens:** HTTP caching defaults. Developers forget SW registration is a separate fetch.
**How to avoid:** Set `Cache-Control: no-store` in both Vite dev server config (`server.headers`) AND Vercel/production headers for the `/sw.js` path specifically.
**Warning signs:** Deployed fix doesn't take effect; users report old behavior persisting after hard refresh.

### Pitfall 2: BackgroundSyncPlugin doesn't retry 4xx/5xx responses
**What goes wrong:** Team expects Workbox to retry all failed sync attempts. But BackgroundSyncPlugin only triggers on network exceptions (fetch throws), not on HTTP error responses (401, 500).
**Why it happens:** Documentation is not prominently clear about this distinction.
**How to avoid:** The Dexie syncQueue already handles retry logic for 4xx/5xx responses (sets `status: 'retrying'`, increments `retryCount`). Keep the Dexie layer as primary. Workbox is the fallback for complete network outages only.
**Warning signs:** Items in `syncQueue` with `retryCount > 0` not being retried after connectivity restores.

### Pitfall 3: Parallel token refresh races
**What goes wrong:** Multiple API calls fire at once with an expired token. Each call independently tries to refresh, generating multiple refresh requests. The backend invalidates the first refresh token on rotation. Subsequent callers get 401 on the now-revoked refresh token.
**Why it happens:** Token rotation: each refresh_token can only be used once.
**How to avoid:** In-memory lock (Promise singleton pattern). All concurrent callers share the same refresh Promise. Only the first caller actually hits the network; others wait and reuse the result.
**Warning signs:** Intermittent 401s immediately after reconnecting; "invalid_refresh_token" errors in logs.

### Pitfall 4: SW TypeScript compilation fails with `self.__WB_MANIFEST`
**What goes wrong:** TypeScript complains that `self.__WB_MANIFEST` doesn't exist on `ServiceWorkerGlobalScope`.
**Why it happens:** `__WB_MANIFEST` is injected at build time by vite-plugin-pwa; it's not in the TypeScript type definitions.
**How to avoid:** Add a type declaration at the top of `sw.ts`:
```typescript
declare let self: ServiceWorkerGlobalScope;
// or
declare const __WB_MANIFEST: Array<{url: string; revision: string | null}>;
```
Also add `"WebWorker"` to the `lib` array in `tsconfig.json`.
**Warning signs:** `tsc --noEmit` fails with "Property '__WB_MANIFEST' does not exist on type 'ServiceWorkerGlobalScope'".

### Pitfall 5: Refresh token not stored during driver pairing
**What goes wrong:** `pairDevice()` in `api.ts` only stores `access_token` in localStorage. The `refresh_token` returned by the pairing endpoint is discarded. AUTH-02 token refresh is impossible without the refresh token.
**Why it happens:** Original implementation only needed access_token. Refresh was not planned.
**How to avoid:** Modify `pairDevice()` to also call `localStorage.setItem('rotas_refresh_token', data.refresh_token)`.
**Warning signs:** `refreshAccessToken()` always finds `rotas_refresh_token` as null; driver sessions expire after 15 minutes permanently.

### Pitfall 6: Manager login doesn't store refresh_token cookie
**What goes wrong:** AUTH-01 requires silent token refresh, but the `refresh_token` is never stored in a cookie by the current `login()` server action.
**Why it happens:** Original implementation only needed access_token for the 8-hour cookie session.
**How to avoid:** In `auth.ts` `login()`, add `jar.set('rotas_refresh_token', data.refresh_token, {...opts, maxAge: 60 * 60 * 24 * 30})`.
**Warning signs:** `apiFetch()` 401 handler finds no refresh_token cookie; every 15 minutes the manager gets a redirect to `/login`.

### Pitfall 7: SW module format — `exports` in output
**What goes wrong:** vite-plugin-pwa compiles `sw.ts` but the output contains `export {}` or `exports.X = ...`, which is invalid in a Service Worker context. The SW fails to install with a syntax error.
**Why it happens:** Vite's default module output format is `esm` which may include export statements.
**How to avoid:** vite-plugin-pwa uses its own internal build process for the SW file (separate from the main Vite build). If encountering this issue, add `rollupFormat: 'iife'` to the `injectManifest` options:
```typescript
VitePWA({
  strategies: 'injectManifest',
  injectManifest: {
    rollupFormat: 'iife',
  },
})
```
**Warning signs:** SW registration fails in Chrome DevTools Application tab with "Failed to execute 'importScripts'" or module parse errors.

### Pitfall 8: `driver_access_revoked` vs expired refresh token — indistinguishable 401s
**What goes wrong:** Both access revocation and token expiry return HTTP 401. The app cannot distinguish them and incorrectly treats a revoked driver as just having an expired session.
**Why it happens:** HTTP status codes alone are insufficient — both cases are 401.
**How to avoid:** The backend must return `{"error": "driver_access_revoked"}` in the response body when the DriverDevice is deactivated. The client reads the response body on 401 and branches:
- `body.error === 'driver_access_revoked'` → dispatch `driver-access-revoked` event → banner state: `access_revoked`
- Other 401 → treat as token expiry → attempt refresh
**Note:** Currently the backend does NOT implement this distinction. It must be added as part of this phase (relates to D-08 — requires checking `DriverDevice.is_active` in the auth validation path).

---

## Code Examples

### Complete sw.ts (verified pattern)
```typescript
// Source: https://vite-pwa-org.netlify.app/guide/inject-manifest.html
//         https://developer.chrome.com/docs/workbox/modules/workbox-background-sync
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, CacheFirst } from 'workbox-strategies';
import { BackgroundSyncPlugin } from 'workbox-background-sync';
import { clientsClaim } from 'workbox-core';

declare let self: ServiceWorkerGlobalScope;

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});

clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Background sync plugin for POST /api/v1/sync/batch
// maxRetentionTime: 24h (1440 min) — covers extended offline scenarios
const bgSyncPlugin = new BackgroundSyncPlugin('rotas-sync-queue', {
  maxRetentionTime: 24 * 60,
});

// POST /api/v1/sync/batch — network-first + background sync fallback
registerRoute(
  ({ url }) => url.pathname === '/api/v1/sync/batch',
  new NetworkFirst({ cacheName: 'sync-api', plugins: [bgSyncPlugin] }),
  'POST'
);

// GET /api/v1/* — network-first, 10s timeout
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/'),
  new NetworkFirst({ cacheName: 'api-cache', networkTimeoutSeconds: 10 }),
  'GET'
);

// Static assets — cache-first
registerRoute(
  ({ request }) =>
    request.destination === 'script' ||
    request.destination === 'style' ||
    request.destination === 'image',
  new CacheFirst({ cacheName: 'static-assets' })
);
```

### tsconfig.json lib update (required for sw.ts)
```json
{
  "compilerOptions": {
    "lib": ["DOM", "DOM.Iterable", "ES2022", "WebWorker"]
  }
}
```

### Workbox registration in main.tsx
```typescript
// Source: https://vite-pwa-org.netlify.app/guide/inject-manifest.html
import { Workbox } from 'workbox-window';

if ('serviceWorker' in navigator) {
  const wb = new Workbox('/sw.js');
  wb.addEventListener('waiting', () => {
    window.dispatchEvent(new CustomEvent('sw-update-available', { detail: { wb } }));
  });
  void wb.register();
}
```

### Backend _dispatch_update extension (AUTH-04)
```python
# Pattern: extend _dispatch_update in backend/app/modules/sync/service.py
# Source: existing _dispatch_create pattern in same file

async def _dispatch_update(
    db: AsyncSession,
    tenant_id: UUID,
    operation: SyncOperation,
) -> dict:
    payload = _normalize_payload(operation.payload)
    entity_type = operation.entity_type
    server_id = payload.pop("server_id", None) or payload.pop("id", None)

    if not server_id:
        return _result(operation, status="failed", error_code="server_id_required", ...)

    entity_uuid = UUID(str(server_id))

    if entity_type == "checklist":
        # ... existing implementation ...

    if entity_type == "trip":
        # Use a TripPatch schema (to create) or map to specific trip service calls
        # e.g., update origin/destination/cargo_type fields
        updated = await trip_service.patch_trip(db, tenant_id, entity_uuid, payload)
        return _result(operation, status="processed", server_id=updated["id"])

    if entity_type == "fuel_log":
        updated = await fuel_service.patch_fuel_log(db, tenant_id, entity_uuid, payload)
        return _result(operation, status="processed", server_id=updated["id"])

    if entity_type == "trip_stop":
        updated = await trip_service.patch_stop(db, tenant_id, entity_uuid, payload)
        return _result(operation, status="processed", server_id=updated["id"])

    if entity_type == "delivery_proof":
        updated = await cargo_service.patch_delivery_proof(db, tenant_id, entity_uuid, payload)
        return _result(operation, status="processed", server_id=updated["id"])
```

**NOTE:** Check whether `patch_trip`, `patch_fuel_log`, `patch_stop`, `patch_delivery_proof` service functions exist before implementing. If they don't exist, the plan must include creating them. From the `service.py` function list, none of these patch functions were observed — they must be created.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `workbox-webpack-plugin` | `vite-plugin-pwa` | 2022 (Vite ecosystem) | Different config format; webpack docs are outdated |
| `generateSW` strategy | `injectManifest` for custom SW logic | Always coexisted | injectManifest required for background sync routing |
| `self.skipWaiting()` unconditional | `message` listener + prompt pattern | Best practice since Workbox 5 | Prevents mid-operation SW swap |
| Store only `access_token` | Store both `access_token` + `refresh_token` | Required for AUTH-02 | Refresh token must be persisted |

**Deprecated/outdated:**
- `importScripts('workbox-sw.js')` CDN pattern: replaced by npm module imports in TypeScript SW files
- `workbox.precaching.precacheAndRoute([])` global namespace: replaced by ES module imports

---

## Open Questions

1. **Do patch service functions exist for trip, fuel_log, trip_stop, delivery_proof?**
   - What we know: `_dispatch_update` currently only handles `checklist` via `checklist_service.patch_checklist`. The `trips/service.py` function list shows no `patch_trip` or `patch_stop` function.
   - What's unclear: Whether partial update logic for these entities can reuse existing update endpoints or requires new service layer functions.
   - Recommendation: Wave 0 plan task must audit existing service functions for each entity type and create stubs or implement patch functions before wiring into `_dispatch_update`.

2. **Does `driver_access_revoked` error code need a backend change?**
   - What we know: Currently, when a driver is deactivated (`driver.status != "active"`), the refresh token endpoint raises `invalid_refresh_token` (401) — indistinguishable from expiry. Access revocation (D-08) requires a distinct error code.
   - What's unclear: Whether to check `DriverDevice.is_active` in the auth principal validation path or in the sync batch handler.
   - Recommendation: Check `DriverDevice.is_active` in `get_driver_principal` (core/auth.py) and raise `ApiError("driver_access_revoked", ..., 401)` when the device is inactive.

3. **`client_timestamp` and `server_timestamp` fields in sync schemas**
   - What we know: ROADMAP specifies these fields for clock skew handling. They're not currently in `SyncOperation` (schema) or `SyncBatchRequest`.
   - What's unclear: Whether timestamps are per-operation or per-batch.
   - Recommendation: Add `client_timestamp: datetime | None = None` to `SyncOperation` schema and record `server_timestamp` in the result. This is a schema-only change — no business logic needed.

4. **`bootstrap` endpoint in `sync/service.py` reports `supported_operations: ["create"]`**
   - What we know: After AUTH-04, `update` operations will be supported. The bootstrap response should be updated to reflect this.
   - Recommendation: Update `supported_operations` to `["create", "update"]` as part of the AUTH-04 plan.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | npm package install, Vite build | Yes | v24.16.0 | — |
| Python | Backend service functions | Yes | 3.13.13 | — |
| PostgreSQL | Backend tests | Must be running on port 55432 | — | Tests skip if unavailable |
| npm / vite | PWA build | Yes | via Node.js | — |

**Missing dependencies with no fallback:**
- None for this phase — all tools are available.

**Missing dependencies with fallback:**
- No `@vite-pwa/assets-generator` — needed for icon generation CLI. Fallback: generate icon PNGs manually from SVG (one-time task, no ongoing dependency).

---

## Validation Architecture

nyquist_validation is enabled (per `.planning/config.json`).

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.2+ with pytest-asyncio (asyncio_mode = "auto") |
| Backend config | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Backend quick run | `cd backend && python -m pytest tests/test_sync_auth.py tests/test_sync_idempotency.py -x -q` |
| Backend full suite | `cd backend && python -m pytest -x -q` |
| Frontend test framework | None — no Vitest/Jest configured in `apps/driver/` |
| Frontend tests | Manual + device testing only for this phase |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PWA-01 | SW registers and intercepts fetch | Manual/device | n/a | No — manual only |
| PWA-01 | Background sync queue retries failed POST | Manual/device | n/a | No — manual only |
| PWA-02 | PWA installable (Lighthouse installability) | Manual/Lighthouse | n/a | No — Lighthouse check |
| PWA-03 | Network-first for /api/v1/, cache-first for assets | Manual/DevTools | n/a | No — manual only |
| AUTH-01 | Manager token refresh — silent 401 recovery | Integration | `cd backend && python -m pytest tests/test_auth_api.py -x -q` | Partial ✅ (auth tests exist, refresh-specific test needed) |
| AUTH-02 | Driver token refresh — silent 401 recovery | Integration | `cd backend && python -m pytest tests/test_sync_auth.py -x -q` | Partial ✅ (sync auth test exists, refresh test needed) |
| AUTH-02 | Driver refresh token stored during pairing | Integration | New test needed | ❌ Wave 0 |
| AUTH-04 | sync `update` for trip returns processed | Integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ Wave 0 |
| AUTH-04 | sync `update` for fuel_log returns processed | Integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ Wave 0 |
| AUTH-04 | sync `update` for trip_stop returns processed | Integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ Wave 0 |
| AUTH-04 | sync `update` for delivery_proof returns processed | Integration | `cd backend && python -m pytest tests/test_sync_update.py -x -q` | ❌ Wave 0 |
| D-08 | Backend distinguishes driver_access_revoked from token expiry | Integration | `cd backend && python -m pytest tests/test_driver_revocation.py -x -q` | ❌ Wave 0 |

### Behaviors Requiring Manual / Device Testing Only

These cannot be automated with the current test stack (no Playwright, no browser integration test runner):

| Behavior | Why Manual Only | Device Requirement |
|----------|----------------|-------------------|
| Chrome "Add to Home Screen" prompt appears | Requires real browser installability check | Android Chrome |
| App launches in standalone mode (no browser chrome) | Requires installed PWA | Android device |
| App works in airplane mode (all views load) | Requires offline browser context | Any device |
| Offline-created records sync on reconnect within 60s | Requires real network transition | Android with data |
| Background sync triggers on reconnect without app open | Requires BackgroundSync API support check | Android Chrome only |
| SW `Cache-Control: no-store` confirmed in DevTools | Requires browser dev tools inspection | Any device |
| Lighthouse PWA score passes installability criteria | Requires Lighthouse CLI or Chrome audit | Desktop Chrome |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_sync_auth.py tests/test_sync_idempotency.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest -x -q`
- **Phase gate:** Full backend suite green + manual device test on real Android before `/gsd:verify-work`

### Wave 0 Gaps (test files that must be created before implementation)

- [ ] `backend/tests/test_sync_update.py` — covers AUTH-04 (update operations for trip, fuel_log, trip_stop, delivery_proof)
- [ ] `backend/tests/test_driver_revocation.py` — covers D-08 (driver_access_revoked error code)
- [ ] `backend/tests/test_token_refresh.py` — covers AUTH-01 (manager refresh) and AUTH-02 (driver refresh) token rotation behavior

*(No new frontend test infrastructure gaps — frontend testing is manual for this phase due to absence of a browser test framework)*

---

## Sources

### Primary (HIGH confidence)
- Official vite-plugin-pwa docs — https://vite-pwa-org.netlify.app/guide/inject-manifest.html — injectManifest strategy config
- Official vite-plugin-pwa workbox docs — https://vite-pwa-org.netlify.app/workbox/inject-manifest.html — injectManifest workbox options
- Workbox background-sync official docs — https://developer.chrome.com/docs/workbox/modules/workbox-background-sync — BackgroundSyncPlugin API, maxRetentionTime, fetch exception caveat
- npm registry — vite-plugin-pwa@1.3.0, workbox-*@7.4.1 — version confirmation

### Secondary (MEDIUM confidence)
- apps/driver/src/sync.ts, db.ts, api.ts — direct codebase inspection for gaps
- backend/app/modules/sync/service.py — direct codebase inspection for AUTH-04 extension points
- backend/app/modules/auth/service.py — direct codebase inspection for refresh endpoint behavior

### Tertiary (LOW confidence)
- None

---

## Project Constraints (from CLAUDE.md)

| Constraint | Impact on Phase 2 |
|------------|-------------------|
| Tech stack locked: FastAPI + Next.js + Vite/React + PostgreSQL | No new frameworks; all additions are libraries on top of existing stack |
| Dexie.js 4 already in use — maintain schema IndexedDB compatibility | Do NOT change existing Dexie schema version or store definitions without a Dexie `version()` migration |
| Multitenant safety: all queries must filter by `tenant_id` | Any new backend service functions for AUTH-04 patch operations must include `tenant_id` filter |
| Stack: vite ^5.4.0 | vite-plugin-pwa 1.3.0 supports `vite: ^3.1.0 || ^4.0.0 || ^5.0.0 || ^6.0.0 || ^7.0.0` — compatible |
| GSD workflow enforcement: no direct edits outside GSD | All implementation through `/gsd:execute-phase` |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry confirmed all versions; official docs confirmed vite-plugin-pwa 1.3.0 + Workbox 7.4.1 compatibility
- Architecture patterns: HIGH — based on direct codebase inspection + official documentation
- Pitfalls: HIGH — pitfalls derived from official documentation caveats + direct code gap analysis
- AUTH-04 service function existence: LOW — patch service functions for trip/fuel_log/trip_stop/delivery_proof not observed; must be confirmed in Wave 0 audit

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (30 days — stable libraries; vite-plugin-pwa has slow release cadence)
