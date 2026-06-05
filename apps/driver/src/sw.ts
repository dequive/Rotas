// Service Worker for ROTAS Motorista PWA
// Strategy: injectManifest — vite-plugin-pwa compiles this file and injects precache manifest
//
// PWA-01: Handles background sync queue for POST /api/v1/sync/batch
// PWA-03: Network-first for all API calls, cache-first for static assets
//
// CRITICAL: SW is served with Cache-Control: no-store (enforced in vite.config.mjs dev server
// and vercel.json production headers). A cached broken SW is unrecoverable on low-cost Android.

import { precacheAndRoute, cleanupOutdatedCaches } from "workbox-precaching";
import { registerRoute } from "workbox-routing";
import { NetworkFirst, CacheFirst } from "workbox-strategies";
import { BackgroundSyncPlugin } from "workbox-background-sync";
import { clientsClaim } from "workbox-core";

declare let self: ServiceWorkerGlobalScope;

// Prompt-for-update pattern: only skip waiting when the driver explicitly taps
// "Verificar atualizações" in the SyncStatusBanner. NEVER call skipWaiting unconditionally —
// it would reload the app mid-trip (e.g., while driver is recording delivery proof).
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// Take control of all pages immediately after activation (without requiring reload)
clientsClaim();

// Remove precache entries for outdated SW versions
cleanupOutdatedCaches();

// Precache all static assets (manifest injected by vite-plugin-pwa at build time)
// The __WB_MANIFEST placeholder is replaced with the actual hashed asset list during build
precacheAndRoute(self.__WB_MANIFEST);

// Background sync plugin for POST /api/v1/sync/batch
// IMPORTANT: BackgroundSyncPlugin only retries on network exceptions (fetch throws).
// It does NOT retry 4xx/5xx HTTP responses. The Dexie syncQueue is the primary retry
// layer for those cases. This plugin handles the "device is fully offline" scenario.
const bgSyncPlugin = new BackgroundSyncPlugin("rotas-sync-queue", {
  maxRetentionTime: 24 * 60, // 24 hours in minutes — covers extended offline scenarios
});

// Network-first for POST /api/v1/sync/batch with background sync fallback
registerRoute(
  ({ url }) => url.pathname === "/api/v1/sync/batch",
  new NetworkFirst({
    cacheName: "sync-api",
    plugins: [bgSyncPlugin],
  }),
  "POST"
);

// Network-first for all GET /api/v1/* calls
// Rationale: stale financial data is worse than no data in fleet management context
registerRoute(
  ({ url }) => url.pathname.startsWith("/api/v1/"),
  new NetworkFirst({
    cacheName: "api-cache",
    networkTimeoutSeconds: 10,
  }),
  "GET"
);

// Cache-first for static assets (JS bundles, CSS, images)
// These are content-hashed at build time — cache forever, never stale
registerRoute(
  ({ request }) =>
    request.destination === "script" ||
    request.destination === "style" ||
    request.destination === "image",
  new CacheFirst({ cacheName: "static-assets" })
);
