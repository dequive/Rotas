import assert from "node:assert/strict";
import test from "node:test";

import {
  findDemoFallbackViolations,
  verifyNoDemoFallback,
} from "./verify-no-demo-fallback.mjs";

test("rejects demo flags, fabricated sources and known datasets", () => {
  const source = `
    const fallbackTrips = [];
    return { source: "fallback" };
    process.env.ROTAS_ALLOW_DEMO_FALLBACK;
  `;
  const labels = findDemoFallbackViolations(source).map(
    (violation) => violation.label,
  );
  assert.deepEqual(labels, [
    "demo fallback env",
    "fallback data source",
    "known fabricated dataset",
  ]);
});

test("accepts explicit empty API state without fabricated records", () => {
  assert.deepEqual(
    findDemoFallbackViolations(
      'return { trips: [], source: "api", message: "Sem registos." };',
    ),
    [],
  );
});

test("current production surface contains no demo fallback", async () => {
  assert.deepEqual(await verifyNoDemoFallback(), []);
});
