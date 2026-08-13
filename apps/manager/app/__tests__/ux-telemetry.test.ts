import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sentry = vi.hoisted(() => ({ init: vi.fn(), startSpan: vi.fn() }));
vi.mock("@sentry/nextjs", () => sentry);

import { recordManagerWebVital } from "@/app/lib/ux-telemetry";

describe("Manager UX telemetry", () => {
  beforeEach(() => {
    sentry.init.mockReset();
    sentry.startSpan.mockReset();
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN_MANAGER", "");
  });

  afterEach(() => vi.unstubAllEnvs());

  it("stays silent when client telemetry is disabled", async () => {
    await recordManagerWebVital({ name: "LCP", value: 1200, rating: "good" });
    expect(sentry.startSpan).not.toHaveBeenCalled();
  });

  it("emits only allowlisted low-cardinality attributes", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN_MANAGER", "https://public@example.invalid/1");
    await recordManagerWebVital({ name: "CLS", value: 0.01234, rating: "good" });

    const options = sentry.startSpan.mock.calls[0]?.[0];
    expect(options).toEqual({
      name: "Web Vital CLS",
      op: "ui.web-vital",
      attributes: {
        "ux.app": "manager",
        "ux.metric": "CLS",
        "ux.rating": "good",
        "ux.value": 0.01,
        "ux.unit": "none",
      },
    });
    expect(JSON.stringify(options)).not.toMatch(/tenant|email|token|user|url|route/i);
  });

  it("contains SDK failures and ignores unknown metrics", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN_MANAGER", "https://public@example.invalid/1");
    sentry.startSpan.mockImplementationOnce(() => { throw new Error("sdk unavailable"); });

    await expect(recordManagerWebVital({ name: "LCP", value: 1200, rating: "good" })).resolves.toBeUndefined();
    await expect(recordManagerWebVital({ name: "CUSTOM", value: 1, rating: "good" })).resolves.toBeUndefined();
  });
});
