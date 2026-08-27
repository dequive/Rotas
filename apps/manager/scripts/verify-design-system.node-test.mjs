import test from "node:test";
import assert from "node:assert/strict";

import {
  findComponentViolations,
  findGlobalHexViolations,
  verifyDesignSystem,
} from "./verify-design-system.mjs";

test("component gate detects hardcoded colours and legacy focus", () => {
  const violations = findComponentViolations(`
    <div className="text-[#fff] focus:ring-rotas-500" />
  `);
  assert.deepEqual(
    violations.map(({ label }) => label),
    ["hardcoded hexadecimal colour", "legacy focus colour"],
  );
});

test("global hex gate permits token blocks and rejects utilities", () => {
  const violations = findGlobalHexViolations(`
  :root {
    --ink: #111111;
  }
  .dark,
  [data-theme="dark"] {
    --ink: #eeeeee;
  }
  .invalid { color: #123456; }
  `);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].line, 9);
});

test("current ROTAS surface satisfies the v1.3.1 contract", async () => {
  assert.deepEqual(await verifyDesignSystem(), []);
});
