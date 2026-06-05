import React from "react";
import ReactDOM from "react-dom/client";
import { Workbox } from "workbox-window";
import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// PWA-01: Register service worker via workbox-window
// Using Workbox class (not navigator.serviceWorker directly) for lifecycle event support.
// The 'waiting' event fires when a new SW version is ready but waiting to activate.
// We dispatch a custom event that useSyncStatus hook listens to, enabling the
// "Verificar atualizações" button in SyncStatusBanner (per D-03 in CONTEXT.md).
if ("serviceWorker" in navigator) {
  const wb = new Workbox("/sw.js");

  wb.addEventListener("waiting", () => {
    // New SW version detected and waiting. Dispatch custom event — SyncStatusBanner
    // useSyncStatus hook listens for 'sw-update-available' to show update button.
    window.dispatchEvent(new CustomEvent("sw-update-available", { detail: { wb } }));
  });

  void wb.register();
}
