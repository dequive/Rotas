import assert from "node:assert/strict";
import test from "node:test";

import {
  findGenericViolations,
  verifyAccessibility,
} from "./verify-accessibility.mjs";

test("generic gate rejects missing image text alternatives and positive tabindex", () => {
  const violations = findGenericViolations({
    "bad.tsx":
      '<img src="/proof.jpg" /><button tabIndex={3}>Abrir</button><div className="table-wrap">',
  });
  assert.deepEqual(violations, [
    "bad.tsx: img without alt",
    "bad.tsx: positive tabIndex changes the natural focus order",
    "bad.tsx: scrollable table region needs tabIndex={0} and aria-label",
  ]);
});

test("canonical Manager and Driver accessibility contracts pass", () => {
  const result = verifyAccessibility();
  assert.equal(result.managerOfficeNestedMain, 0);
  assert.equal(result.genericViolations, 0);
  assert.ok(result.scannedTsx > 100);
});
