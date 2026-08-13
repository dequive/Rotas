export const UX_METRIC_NAMES = [
  "CLS",
  "FCP",
  "FID",
  "INP",
  "LCP",
  "TTFB",
  "driver.bootstrap.duration",
  "driver.sync.duration",
] as const;

export type UxMetricName = (typeof UX_METRIC_NAMES)[number];
export type UxMetricUnit = "millisecond" | "none";
export type UxMetricAttribute =
  | "app"
  | "metric"
  | "operation"
  | "outcome"
  | "rating";

export interface UxMetricInput {
  name: string;
  value: number;
  unit: UxMetricUnit;
  attributes: Record<string, string>;
}

export interface UxMetric {
  name: UxMetricName;
  value: number;
  unit: UxMetricUnit;
  attributes: Partial<Record<UxMetricAttribute, string>>;
}

const metricNames = new Set<string>(UX_METRIC_NAMES);
const attributeNames = new Set<UxMetricAttribute>([
  "app",
  "metric",
  "operation",
  "outcome",
  "rating",
]);
const attributeValues: Record<UxMetricAttribute, ReadonlySet<string>> = {
  app: new Set(["manager", "driver"]),
  metric: new Set(["CLS", "FCP", "FID", "INP", "LCP", "TTFB"]),
  operation: new Set(["bootstrap", "sync"]),
  outcome: new Set(["success", "cache", "unavailable", "error", "offline"]),
  rating: new Set(["good", "needs-improvement", "poor"]),
};

export function createUxMetric(input: UxMetricInput): UxMetric {
  if (!metricNames.has(input.name)) {
    throw new Error("UX metric is not allowed");
  }
  if (!Number.isFinite(input.value)) {
    throw new Error("UX metric value must be finite");
  }

  const attributes: Partial<Record<UxMetricAttribute, string>> = {};
  for (const [key, value] of Object.entries(input.attributes)) {
    if (!attributeNames.has(key as UxMetricAttribute)) {
      throw new Error(`UX telemetry attribute is not allowed: ${key}`);
    }
    const attribute = key as UxMetricAttribute;
    if (!attributeValues[attribute].has(value)) {
      throw new Error(`UX telemetry attribute value is not allowed: ${key}`);
    }
    attributes[attribute] = value;
  }

  return {
    name: input.name as UxMetricName,
    value: Math.round(input.value * 100) / 100,
    unit: input.unit,
    attributes,
  };
}
