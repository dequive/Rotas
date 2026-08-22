import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const managerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(managerRoot, "../..");

function walk(root) {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(root, entry.name);
    if (entry.isDirectory()) {
      if (["__tests__", "generated", "node_modules", ".next", "dist"].includes(entry.name)) {
        return [];
      }
      return walk(absolute);
    }
    return entry.name.endsWith(".tsx") ? [absolute] : [];
  });
}

export function findGenericViolations(sources) {
  const violations = [];
  for (const [file, source] of Object.entries(sources)) {
    for (const image of source.match(/<img\b[\s\S]*?>/g) ?? []) {
      if (!/\balt=/.test(image)) violations.push(`${file}: img without alt`);
    }
    if (/tabIndex=\{[1-9]\d*\}/.test(source)) {
      violations.push(`${file}: positive tabIndex changes the natural focus order`);
    }
    for (const region of source.match(/<div\b[\s\S]*?className="table-wrap"[\s\S]*?>/g) ?? []) {
      if (!/tabIndex=\{0\}/.test(region) || !/\baria-label=/.test(region)) {
        violations.push(`${file}: scrollable table region needs tabIndex={0} and aria-label`);
      }
    }
  }
  return violations;
}

function requireFragments(file, source, fragments, violations) {
  for (const fragment of fragments) {
    if (!source.includes(fragment)) violations.push(`${file}: missing ${fragment}`);
  }
}

export function verifyAccessibility(root = repoRoot) {
  const managerApp = path.join(root, "apps", "manager", "app");
  const sources = Object.fromEntries(
    [
      ...walk(managerApp),
      ...walk(path.join(root, "apps", "driver", "src")),
    ].map((file) => [path.relative(root, file).replaceAll("\\", "/"), fs.readFileSync(file, "utf8")]),
  );
  const violations = findGenericViolations(sources);

  const layout = sources["apps/manager/app/layout.tsx"] ?? "";
  requireFragments("layout.tsx", layout, ['<html lang="pt-MZ">'], violations);

  const sidebar = sources["apps/manager/app/components/SidebarLayout.tsx"] ?? "";
  requireFragments(
    "SidebarLayout.tsx",
    sidebar,
    [
      'href="#main-content"',
      'className="skip-link"',
      'id="main-content"',
      "tabIndex={-1}",
      'aria-label="Navegação principal"',
    ],
    violations,
  );

  const globals = fs.readFileSync(path.join(managerApp, "globals.css"), "utf8");
  requireFragments(
    "globals.css",
    globals,
    [":focus-visible", ".skip-link:focus-visible", "prefers-reduced-motion: reduce"],
    violations,
  );

  const workOrder =
    sources["apps/manager/app/oficina/components/WorkOrderDetailClient.tsx"] ?? "";
  requireFragments(
    "WorkOrderDetailClient.tsx",
    workOrder,
    [
      'role="tablist"',
      'role="tab"',
      'role="tabpanel"',
      "aria-controls=",
      "aria-labelledby=",
      "tabIndex={tab === item ? 0 : -1}",
      'event.key === "ArrowRight"',
      'event.key === "ArrowLeft"',
      'event.key === "Home"',
      'event.key === "End"',
    ],
    violations,
  );

  const vehicleTabs =
    sources["apps/manager/app/viaturas/[id]/VehicleTabsClient.tsx"] ?? "";
  requireFragments(
    "VehicleTabsClient.tsx",
    vehicleTabs,
    [
      'role="tablist"',
      'role="tab"',
      'role="tabpanel"',
      "aria-controls=",
      "aria-labelledby=",
      "tabIndex={isActive ? 0 : -1}",
      'event.key === "ArrowRight"',
      'event.key === "ArrowLeft"',
      'event.key === "Home"',
      'event.key === "End"',
    ],
    violations,
  );

  const pairing = sources["apps/driver/src/views/PairingView.tsx"] ?? "";
  requireFragments(
    "PairingView.tsx",
    pairing,
    [
      'htmlFor="pairing-code"',
      'id="pairing-code"',
      "aria-describedby=",
      "aria-invalid=",
      'role="alert"',
    ],
    violations,
  );

  for (const [file, source] of Object.entries(sources)) {
    if (file.startsWith("apps/manager/app/oficina/") && file.endsWith("/page.tsx") && /<main\b/.test(source)) {
      violations.push(`${file}: nested main inside SidebarLayout`);
    }
  }

  if (violations.length) {
    throw new Error(`Accessibility source gate failed:\n- ${violations.join("\n- ")}`);
  }
  return {
    scannedTsx: Object.keys(sources).length,
    managerOfficeNestedMain: 0,
    genericViolations: 0,
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    console.log(JSON.stringify({ status: "ok", ...verifyAccessibility() }, null, 2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}
