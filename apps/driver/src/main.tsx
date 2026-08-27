import "./sentry"; // INFRA-01: Sentry init — must run before any other code
import React from "react";
import ReactDOM from "react-dom/client";
import { Workbox } from "workbox-window";
import { App } from "./App";
import {
  startPwaUpdateLifecycle,
  type PwaUpdateRuntime,
} from "./pwaUpdate";
import "./styles.css";

function renderApp() {
  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

const browserUpdateRuntime: PwaUpdateRuntime = {
  reload: () => window.location.reload(),
  hasController: () => Boolean(navigator.serviceWorker.controller),
  isOnline: () => navigator.onLine,
  isVisible: () => document.visibilityState === "visible",
  subscribe: (event, listener) => {
    const target = event === "visibilitychange" ? document : window;
    target.addEventListener(event, listener);
    return () => target.removeEventListener(event, listener);
  },
};

// PWA-01: Register service worker via workbox-window
// Using Workbox class (not navigator.serviceWorker directly) for lifecycle event support.
// The 'waiting' event fires when a new SW version is ready but waiting to activate.
// We dispatch a custom event that useSyncStatus hook listens to, enabling the
// "Verificar atualizações" button in SyncStatusBanner (per D-03 in CONTEXT.md).
async function bootstrap() {
  if (!("serviceWorker" in navigator)) {
    renderApp();
    return;
  }

  const wb = new Workbox("/sw.js");
  const lifecycle = await startPwaUpdateLifecycle(wb, browserUpdateRuntime);
  if (lifecycle.shouldRender) renderApp();
}

void bootstrap().catch(renderApp);
