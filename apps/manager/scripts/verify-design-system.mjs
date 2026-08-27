import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(scriptDir, "../../..");

const componentTargets = [
  "apps/manager/app",
];

const mutationFiles = [
  "apps/manager/app/manutencao/components/WorkOrderFormModal.tsx",
  "apps/manager/app/oficina/components/PhotoEvidenceUploader.tsx",
  "apps/manager/app/oficina/components/QuoteFormModal.tsx",
  "apps/manager/app/oficina/components/QuoteMasterDetailClient.tsx",
  "apps/manager/app/oficina/components/SignatureCanvas.tsx",
  "apps/manager/app/oficina/recepcao/nova/page.tsx",
];

const componentPatterns = [
  ["hardcoded hexadecimal colour", /(?<!&)#[0-9a-f]{3,8}\b/i],
  [
    "legacy focus colour",
    /(?:focus|focus-visible):(?:ring|border)-(?:rotas-500|amber(?:-500)?)(?:\/\d+)?/,
  ],
  ["legacy amber KPI semantic", /semantic\s*=\s*["']amber["']/],
  ["forbidden fallback data source", /source\s*=\s*["']fallback["']/],
  [
    "direct badge class",
    /className\s*=\s*["'][^"'\r\n]*(?:^|\s)badge(?:\s|$)[^"'\r\n]*["']/m,
  ],
];

async function listFiles(target) {
  const { stat } = await import("node:fs/promises");
  const targetStat = await stat(target);
  if (targetStat.isFile()) return [target];

  const entries = await readdir(target, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (
      ["__tests__", "e2e", "generated", "node_modules", ".next"].includes(
        entry.name,
      )
    ) {
      continue;
    }
    const absolute = path.join(target, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listFiles(absolute)));
    } else if (/\.(?:ts|tsx)$/.test(entry.name)) {
      files.push(absolute);
    }
  }
  return files;
}

function lineFor(source, index) {
  return source.slice(0, index).split(/\r?\n/).length;
}

export function findComponentViolations(source, file = "<source>") {
  const violations = [];
  for (const [label, pattern] of componentPatterns) {
    const match = pattern.exec(source);
    if (!match) continue;
    violations.push({
      file,
      line: lineFor(source, match.index),
      label,
      match: match[0],
    });
  }
  return violations;
}

export function findGlobalHexViolations(source, file = "apps/manager/app/globals.css") {
  const lines = source.split(/\r?\n/);
  const rootStart = lines.findIndex((line) => /^\s*:root\s*\{/.test(line));
  const rootEnd = lines.findIndex(
    (line, index) => index > rootStart && /^\s{2}\}\s*$/.test(line),
  );
  const darkStart = lines.findIndex((line) => /^\s*\.dark,\s*$/.test(line));
  const darkEnd = lines.findIndex(
    (line, index) => index > darkStart && /^\s{2}\}\s*$/.test(line),
  );

  const violations = [];
  lines.forEach((line, index) => {
    const inTokenBlock =
      (index >= rootStart && index <= rootEnd) ||
      (index >= darkStart && index <= darkEnd);
    const match = /#[0-9a-f]{3,8}\b/i.exec(line);
    if (match && !inTokenBlock) {
      violations.push({
        file,
        line: index + 1,
        label: "hexadecimal outside token blocks",
        match: match[0],
      });
    }
  });
  return violations;
}

export async function verifyDesignSystem() {
  const violations = [];
  const files = (
    await Promise.all(
      componentTargets.map((target) =>
        listFiles(path.join(workspaceRoot, target)),
      ),
    )
  ).flat();

  for (const file of files) {
    const source = await readFile(file, "utf8");
    violations.push(
      ...findComponentViolations(
        source,
        path.relative(workspaceRoot, file).replaceAll("\\", "/"),
      ),
    );
  }

  const globalsPath = path.join(
    workspaceRoot,
    "apps/manager/app/globals.css",
  );
  const globals = await readFile(globalsPath, "utf8");
  violations.push(...findGlobalHexViolations(globals));
  if (/\.data-source\.fallback\b/.test(globals)) {
    violations.push({
      file: "apps/manager/app/globals.css",
      line: lineFor(globals, globals.indexOf(".data-source.fallback")),
      label: "forbidden fallback data source selector",
      match: ".data-source.fallback",
    });
  }

  const design = await readFile(path.join(workspaceRoot, "DESIGN.md"), "utf8");
  for (const [label, required] of [
    ["canonical design-system version", "Versão 1.3.1"],
    ["canonical modal radius token", "var(--r-xl)"],
    ["focus-ring contract", "--focus-ring"],
  ]) {
    if (!design.includes(required)) {
      violations.push({
        file: "DESIGN.md",
        line: 1,
        label: `missing ${label}`,
        match: required,
      });
    }
  }
  if (design.includes("var(--radius-xl)")) {
    violations.push({
      file: "DESIGN.md",
      line: lineFor(design, design.indexOf("var(--radius-xl)")),
      label: "invalid modal radius token",
      match: "var(--radius-xl)",
    });
  }

  for (const relative of mutationFiles) {
    const source = await readFile(path.join(workspaceRoot, relative), "utf8");
    if (!source.includes('"Idempotency-Key"')) {
      violations.push({
        file: relative,
        line: 1,
        label: "mutable Oficina flow lacks Idempotency-Key",
        match: relative,
      });
    }
  }

  return violations;
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const violations = await verifyDesignSystem();
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(
        `${violation.file}:${violation.line} ${violation.label}: ${violation.match}`,
      );
    }
    process.exitCode = 1;
  } else {
    console.log("ROTAS Design System v1.3.1 gate passed.");
  }
}
