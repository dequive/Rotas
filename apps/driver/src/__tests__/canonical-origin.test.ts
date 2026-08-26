// @vitest-environment node

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const playwrightConfig = readFileSync(
  new URL("../../playwright.config.ts", import.meta.url),
  "utf8",
);
const viteConfig = readFileSync(
  new URL("../../vite.config.ts", import.meta.url),
  "utf8",
);
const packageConfig = readFileSync(
  new URL("../../package.json", import.meta.url),
  "utf8",
);

describe("origem canónica da PWA instalada", () => {
  it("usa exclusivamente localhost:4173 como origem no preview e no E2E", () => {
    expect(playwrightConfig).toContain('baseURL: "http://localhost:4173"');
    expect(playwrightConfig).toContain('command: "npm run preview"');
    expect(playwrightConfig).toContain('url: "http://localhost:4173"');
    expect(playwrightConfig).not.toContain("127.0.0.1:4173");
    expect(playwrightConfig).not.toContain("4174");

    expect(viteConfig).toMatch(/preview:\s*\{[\s\S]*port:\s*4173/);
    expect(viteConfig).toMatch(/preview:\s*\{[\s\S]*host:\s*"0\.0\.0\.0"/);
    expect(viteConfig).toMatch(/preview:\s*\{[\s\S]*strictPort:\s*true/);
    expect(packageConfig).toContain(
      "vite preview --config vite.config.ts --configLoader native",
    );
    expect(packageConfig).toContain(
      "vite build --config vite.config.ts --configLoader native",
    );
  });
});
