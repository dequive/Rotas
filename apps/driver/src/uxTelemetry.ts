import { createUxMetric, type UxMetricName } from "@rotas/ux-telemetry";

type DriverOperation = "bootstrap" | "sync";
type DriverOutcome = "success" | "cache" | "unavailable" | "error" | "offline";

export function recordDriverUxMetric(
  name: UxMetricName,
  operation: DriverOperation,
  outcome: DriverOutcome,
  startedAt: number,
) {
  if (!import.meta.env.VITE_SENTRY_DSN_DRIVER) return;

  try {
    const metric = createUxMetric({
      name,
      value: performance.now() - startedAt,
      unit: "millisecond",
      attributes: { app: "driver", operation, outcome },
    });

    void import("@sentry/browser").then((Sentry) => {
      if (!Sentry.isInitialized()) return;
      Sentry.startSpan(
        {
          name: `Driver ${operation}`,
          op: `ui.async.${operation}`,
          attributes: {
            "ux.app": metric.attributes.app,
            "ux.operation": metric.attributes.operation,
            "ux.outcome": metric.attributes.outcome,
            "ux.value": metric.value,
            "ux.unit": metric.unit,
          },
        },
        () => undefined,
      );
    }).catch(() => undefined);
  } catch {
    // Telemetry must never block offline-first operations.
  }
}
