import { describe, expect, it } from "vitest";

import { createUxMetric } from "./index";

describe("UX telemetry privacy contract", () => {
  it("accepts canonical low-cardinality Web Vital dimensions", () => {
    expect(createUxMetric({
      name: "LCP",
      value: 1234.567,
      unit: "millisecond",
      attributes: { app: "manager", rating: "good" },
    })).toEqual({
      name: "LCP",
      value: 1234.57,
      unit: "millisecond",
      attributes: { app: "manager", rating: "good" },
    });
  });

  it.each(["tenant_id", "email", "token", "url", "user_id", "route_id"])(
    "rejects sensitive or high-cardinality attribute %s",
    (attribute) => {
      expect(() => createUxMetric({
        name: "CLS",
        value: 0.02,
        unit: "none",
        attributes: { app: "manager", [attribute]: "forbidden" },
      })).toThrow(/attribute is not allowed/i);
    },
  );

  it("rejects arbitrary metric names and non-finite values", () => {
    expect(() => createUxMetric({
      name: "customer.email.latency",
      value: 10,
      unit: "millisecond",
      attributes: { app: "manager" },
    })).toThrow(/metric is not allowed/i);
    expect(() => createUxMetric({
      name: "INP",
      value: Number.NaN,
      unit: "millisecond",
      attributes: { app: "manager" },
    })).toThrow(/finite/i);
  });

  it("rejects high-cardinality values even on allowed attributes", () => {
    expect(() => createUxMetric({
      name: "driver.sync.duration",
      value: 250,
      unit: "millisecond",
      attributes: { app: "driver", operation: "sync:tenant-123" },
    })).toThrow(/attribute value is not allowed/i);
  });
});
