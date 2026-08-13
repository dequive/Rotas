import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const styles = readFileSync(
  resolve(process.cwd(), "src/styles.css"),
  "utf8",
);

describe("Driver motion contract", () => {
  it("stops continuous and transitional motion when the user requests it", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(styles).toContain("animation-iteration-count: 1");
    expect(styles).toContain("transition-duration: 0.01ms");
  });
});
