import assert from "node:assert/strict";
import test from "node:test";

import { auditDemoFallbacks, findDemoFallbackViolations, frozenBillingPaths } from "./verify-no-demo-fallback.mjs";

test("rejects flags, fabricated sources, datasets and entity ids", () => {
  const source = `
    const fallbackTrips = [];
    const DEMO_BOARD = [];
    const id = "veh-demo-1";
    return { source: "fallback" };
    process.env.ROTAS_ALLOW_DEMO_FALLBACK;
  `;
  const labels = findDemoFallbackViolations(source).map((item) => item.label);
  for (const label of ["demo fallback env", "fallback data source", "known fabricated dataset", "named demo dataset", "fabricated entity id"]) {
    assert.ok(labels.includes(label), label);
  }
});

test("accepts real empty and unavailable states", () => {
  assert.deepEqual(findDemoFallbackViolations('return { items: [], source: "api", message: "Sem registos." };'), []);
  assert.deepEqual(findDemoFallbackViolations('return { items: [], source: "unavailable" };'), []);
});

test("current non-billing production surface contains no demo fallback", async () => {
  const audit = await auditDemoFallbacks();
  assert.deepEqual(audit.active, []);
  assert.ok(audit.frozenBilling.length > 0);
  for (const violation of audit.frozenBilling) assert.ok(frozenBillingPaths.has(violation.file));
});

test("full release gate remains fail-closed while frozen billing violations exist", async () => {
  const audit = await auditDemoFallbacks();
  assert.ok(audit.all.length > 0);
  assert.equal(audit.all.length, audit.frozenBilling.length);
});
