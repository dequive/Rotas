import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDir, "../../..");

const bannedPatterns = [
  ["demo fallback env", /ROTAS_(?:ALLOW|DISABLE)_DEMO_FALLBACK/],
  ["demo runtime guard", /(?:demoFallbackAllowed|throwWhenDemoFallbackDisabled)/],
  ["fallback data source", /source\s*(?::|=)\s*["']fallback["']/],
  [
    "known fabricated dataset",
    /\b(?:fallbackTrips|fallbackDocuments|fallbackTower|fallbackVehicleHistory|fallbackDriverHistory|fallbackTanks|fallbackBoard|fallbackTable)\b/,
  ],
  ["fabricated entity id", /(?:vehicle|driver)-demo-/],
];

const scanTargets = [
  "apps/manager/app",
  "apps/manager/components",
  "apps/manager/playwright.config.ts",
  ".github/workflows",
  ".env.example",
];

async function listFiles(target) {
  const stat = await import("node:fs/promises").then(({ stat }) => stat(target));
  if (stat.isFile()) return [target];
  const entries = await readdir(target, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (
      entry.name === "__tests__" ||
      entry.name === "e2e" ||
      entry.name === "node_modules" ||
      entry.name === ".next"
    ) {
      continue;
    }
    const absolute = path.join(target, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listFiles(absolute)));
    } else if (/\.(?:ts|tsx|mjs|yml|yaml|env|example)$/.test(entry.name)) {
      files.push(absolute);
    }
  }
  return files;
}

export function findDemoFallbackViolations(source, file = "<source>") {
  const violations = [];
  for (const [label, pattern] of bannedPatterns) {
    const match = pattern.exec(source);
    if (!match) continue;
    const line = source.slice(0, match.index).split(/\r?\n/).length;
    violations.push({ file, line, label, match: match[0] });
  }
  return violations;
}

export async function verifyNoDemoFallback() {
  const files = (
    await Promise.all(
      scanTargets.map((target) => listFiles(path.join(workspaceRoot, target))),
    )
  ).flat();
  const violations = [];
  for (const file of files) {
    const source = await readFile(file, "utf8");
    violations.push(
      ...findDemoFallbackViolations(
        source,
        path.relative(workspaceRoot, file).replaceAll("\\", "/"),
      ),
    );
  }
  return violations;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const violations = await verifyNoDemoFallback();
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(
        `${violation.file}:${violation.line} ${violation.label}: ${violation.match}`,
      );
    }
    process.exitCode = 1;
  } else {
    console.log("Production demo-fallback gate passed.");
  }
}
