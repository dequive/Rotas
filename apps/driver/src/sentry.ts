/**
 * Sentry runtime initialization for the driver PWA.
 * Uses VITE_SENTRY_DSN_DRIVER (inlined at build time by Vite).
 * Silent when env var is absent — dev environment is never tracked (D-02).
 *
 * NOTE: VITE_ prefix is required for Vite to inline the value at build time.
 * The build-time guard in vite.config.mjs uses SENTRY_AUTH_TOKEN (no VITE_ prefix)
 * to control source map upload separately from runtime error capture.
 */
import * as Sentry from "@sentry/browser";

const dsn = (import.meta.env.VITE_SENTRY_DSN_DRIVER as string) || "";

if (dsn) {
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.05,
    sendDefaultPii: false,
    integrations: [],
  });
}

export { Sentry };
