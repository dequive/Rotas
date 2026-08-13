import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const read = (relativePath: string) =>
  readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");

describe("Manager motion contract", () => {
  it("provides a global reduced-motion fallback", () => {
    const css = read("../globals.css");

    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("animation-iteration-count: 1");
    expect(css).toContain("transition-duration: 0.01ms");
    expect(css).toContain(".rotas-motion-surface[data-state=\"closed\"]");
    expect(css).toContain("animation-duration: 120ms");
  });

  it("keeps shared overlay motion short and explicitly reducible", () => {
    const primitives = [
      "../../components/ui/dialog.tsx",
      "../../components/ui/sheet.tsx",
      "../../components/ui/popover.tsx",
      "../../components/ui/dropdown-menu.tsx",
      "../../components/ui/select.tsx",
    ].map(read);

    for (const source of primitives) {
      expect(source).toContain("motion-reduce:animate-none");
      expect(source).not.toMatch(/duration-(?:300|500)/);
    }
  });

  it("only pulses skeletons when motion is allowed", () => {
    const skeleton = read("../../components/ui/skeleton.tsx");

    expect(skeleton).toContain("motion-safe:animate-pulse");
    expect(skeleton).not.toContain('"animate-pulse ');
  });
});
