import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDir, "../../..");

const bannedPatterns = [
  ["demo fallback env", /ROTAS_(?:ALLOW|DISABLE)_DEMO_FALLBACK/],
  ["demo runtime guard", /(?:demoFallbackAllowed|throwWhenDemoFallbackDisabled)/],
  ["fallback data source", /source\s*(?::|=)\s*["']fallback["']/],
  ["known fabricated dataset", /\b(?:fallbackTrips|fallbackDocuments|fallbackTower|fallbackVehicleHistory|fallbackDriverHistory|fallbackTanks|fallbackBoard|fallbackTable)\b/],
  ["named demo dataset", /\bDEMO_[A-Z0-9_]+\b/],
  ["fabricated entity id", /(?:vehicle|driver|veh|sig|client)-demo-/],
  ["documented static demo runtime", /(?:demo fallback|fallback demo|static demo data|dados demo)/i],
];

const scanTargets = [
  "apps/manager/app",
  "apps/manager/components",
  "apps/manager/playwright.config.ts",
  ".github/workflows",
  ".env.example",
];

export const frozenBillingPaths = new Set([
  ".env.example",
  "apps/manager/playwright.config.ts",
  "apps/manager/app/lib/billing-api.ts",
  "apps/manager/app/lib/runtime-guards.ts",
  "apps/manager/app/oficina/faturacao/page.tsx",
  "apps/manager/app/oficina/rentabilidade/page.tsx",
]);

async function listFiles(target) {
  const metadata = await stat(target);
  if (metadata.isFile()) return [target];
  const entries = await readdir(target, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (["__tests__", "e2e", "node_modules", ".next"].includes(entry.name)) continue;
    const absolute = path.join(target, entry.name);
    if (entry.isDirectory()) files.push(...(await listFiles(absolute)));
    else if (/\.(?:ts|tsx|mjs|yml|yaml|env|example)$/.test(entry.name)) files.push(absolute);
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

export async function auditDemoFallbacks() {
  const files = (await Promise.all(scanTargets.map((target) => listFiles(path.join(workspaceRoot, target))))).flat();
  const violations = [];
  for (const file of files) {
    const relative = path.relative(workspaceRoot, file).replaceAll("\\", "/");
    const source = await readFile(file, "utf8");
    violations.push(...findDemoFallbackViolations(source, relative));
  }
  return {
    active: violations.filter((item) => !frozenBillingPaths.has(item.file)),
    frozenBilling: violations.filter((item) => frozenBillingPaths.has(item.file)),
    all: violations,
  };
}

function printViolations(violations) {
  for (const violation of violations) {
    console.error(`${violation.file}:${violation.line} ${violation.label}: ${violation.match}`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const scoped = process.argv.includes("--scope=non-billing");
  const audit = await auditDemoFallbacks();
  const blocking = scoped ? audit.active : audit.all;
  if (blocking.length > 0) {
    printViolations(blocking);
    process.exitCode = 1;
  } else if (scoped) {
    console.log(`Non-billing demo-fallback gate passed; ${audit.frozenBilling.length} frozen billing violation(s) remain.`);
  } else {
    console.log("Production demo-fallback gate passed.");
  }
}
