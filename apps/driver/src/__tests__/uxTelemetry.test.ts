import { beforeEach, describe, expect, it, vi } from "vitest";

const sentry = vi.hoisted(() => ({
  initialized: false,
  startSpan: vi.fn(),
}));

vi.mock("@sentry/browser", () => ({
  isInitialized: () => sentry.initialized,
  startSpan: sentry.startSpan,
}));

import { recordDriverUxMetric } from "../uxTelemetry";

describe("Driver UX telemetry", () => {
  beforeEach(() => {
    sentry.initialized = false;
    sentry.startSpan.mockReset();
    vi.spyOn(performance, "now").mockReturnValue(1250);
    vi.stubEnv("VITE_SENTRY_DSN_DRIVER", "");
  });

  it("stays silent when Sentry is disabled", () => {
    recordDriverUxMetric("driver.bootstrap.duration", "bootstrap", "success", 1000);
    expect(sentry.startSpan).not.toHaveBeenCalled();
  });

  it("records a bounded operational span without identity data", async () => {
    sentry.initialized = true;
    vi.stubEnv("VITE_SENTRY_DSN_DRIVER", "https://public@example.invalid/1");
    recordDriverUxMetric("driver.sync.duration", "sync", "error", 1000);
    await vi.waitFor(() => expect(sentry.startSpan).toHaveBeenCalledOnce());

    const options = sentry.startSpan.mock.calls[0]?.[0];
    expect(options).toEqual({
      name: "Driver sync",
      op: "ui.async.sync",
      attributes: {
        "ux.app": "driver",
        "ux.operation": "sync",
        "ux.outcome": "error",
        "ux.value": 250,
        "ux.unit": "millisecond",
      },
    });
    expect(JSON.stringify(options)).not.toMatch(/tenant|driver_id|email|token|user|url|payload/i);
  });

  it("never lets an SDK failure interrupt an offline-first operation", async () => {
    sentry.initialized = true;
    vi.stubEnv("VITE_SENTRY_DSN_DRIVER", "https://public@example.invalid/1");
    sentry.startSpan.mockImplementationOnce(() => { throw new Error("sdk unavailable"); });

    expect(() => recordDriverUxMetric(
      "driver.sync.duration",
      "sync",
      "error",
      1000,
    )).not.toThrow();
    await vi.waitFor(() => expect(sentry.startSpan).toHaveBeenCalledOnce());
  });
});
