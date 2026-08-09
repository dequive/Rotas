import { clearAuth } from "./api";
import { clearAllDriverData } from "./db";

const AUTHENTICATED_CACHE_NAMES = ["api-cache", "sync-api"] as const;
const PURGE_TIMEOUT_MS = 5_000;

async function clearAuthenticatedCaches(): Promise<void> {
  if (!("caches" in globalThis)) return;
  await Promise.all(
    AUTHENTICATED_CACHE_NAMES.map((cacheName) => caches.delete(cacheName)),
  );
}

async function requestServiceWorkerPurge(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;

  const registration = await navigator.serviceWorker.ready;
  const worker =
    navigator.serviceWorker.controller ??
    registration.active ??
    registration.waiting ??
    registration.installing;
  if (!worker) throw new Error("service_worker_unavailable_for_identity_purge");

  await new Promise<void>((resolve, reject) => {
    const channel = new MessageChannel();
    const timeout = window.setTimeout(() => {
      reject(new Error("service_worker_identity_purge_timeout"));
    }, PURGE_TIMEOUT_MS);

    channel.port1.onmessage = (event) => {
      window.clearTimeout(timeout);
      if (event.data?.ok === true) {
        resolve();
      } else {
        reject(new Error(event.data?.error ?? "service_worker_identity_purge_failed"));
      }
    };
    worker.postMessage({ type: "PURGE_IDENTITY_DATA" }, [channel.port2]);
  });
}

export async function purgeDriverIdentity(): Promise<void> {
  clearAuth();
  await Promise.all([
    clearAllDriverData(),
    clearAuthenticatedCaches(),
    requestServiceWorkerPurge(),
  ]);
}
