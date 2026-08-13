import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const webVitals = vi.hoisted(() => ({
  callback: undefined as undefined | ((metric: {
    name: string;
    value: number;
    rating: string;
  }) => void),
}));
const telemetry = vi.hoisted(() => ({ record: vi.fn() }));

vi.mock("next/web-vitals", () => ({
  useReportWebVitals: (callback: typeof webVitals.callback) => {
    webVitals.callback = callback;
  },
}));
vi.mock("@/app/lib/ux-telemetry", () => ({
  recordManagerWebVital: telemetry.record,
}));

import { WebVitalsReporter } from "@/app/components/WebVitalsReporter";

describe("WebVitalsReporter", () => {
  beforeEach(() => {
    telemetry.record.mockReset();
    webVitals.callback = undefined;
  });

  it("forwards browser metrics to the privacy-safe adapter", () => {
    render(<WebVitalsReporter />);
    webVitals.callback?.({ name: "LCP", value: 1200, rating: "good" });

    expect(telemetry.record).toHaveBeenCalledWith({
      name: "LCP",
      value: 1200,
      rating: "good",
    });
  });
});
