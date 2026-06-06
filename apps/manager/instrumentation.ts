/**
 * Next.js instrumentation hook — auto-discovered at project root.
 * Initializes Sentry only when SENTRY_DSN_MANAGER is set (D-02: silent when DSN absent).
 * @see https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const Sentry = await import("@sentry/nextjs");
    if (process.env.SENTRY_DSN_MANAGER) {
      Sentry.init({
        dsn: process.env.SENTRY_DSN_MANAGER,
        environment: process.env.NODE_ENV ?? "development",
        tracesSampleRate: 0.05,
      });
    }
  }
}
