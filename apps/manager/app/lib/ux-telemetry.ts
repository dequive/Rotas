import { createUxMetric } from "@rotas/ux-telemetry";

interface WebVitalInput {
  name: string;
  value: number;
  rating: string;
}

let sentryInitialized = false;

export async function recordManagerWebVital(vital: WebVitalInput) {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN_MANAGER ?? "";
  if (!dsn) return;

  try {
    const metric = createUxMetric({
      name: vital.name,
      value: vital.value,
      unit: vital.name === "CLS" ? "none" : "millisecond",
      attributes: { app: "manager", metric: vital.name, rating: vital.rating },
    });
    const Sentry = await import("@sentry/nextjs");
    if (!sentryInitialized) {
      Sentry.init({
        dsn,
        environment: process.env.NODE_ENV ?? "development",
        tracesSampleRate: 0.05,
        sendDefaultPii: false,
      });
      sentryInitialized = true;
    }
    Sentry.startSpan({
      name: `Web Vital ${metric.name}`,
      op: "ui.web-vital",
      attributes: {
        "ux.app": metric.attributes.app,
        "ux.metric": metric.attributes.metric,
        "ux.rating": metric.attributes.rating,
        "ux.value": metric.value,
        "ux.unit": metric.unit,
      },
    }, () => undefined);
  } catch {
    // Telemetry must never affect the user journey.
  }
}
