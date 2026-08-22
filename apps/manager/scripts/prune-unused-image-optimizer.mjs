import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const managerRoot = path.resolve(scriptDir, "..");
const standaloneRoot = path.resolve(managerRoot, ".next", "standalone");
const configPath = path.resolve(managerRoot, "next.config.mjs");
const importPattern = /(?:from\s+|require\(\s*)["']next\/image["']/;
const sourceExtensions = new Set([".js", ".mjs", ".ts", ".tsx"]);

function walk(directory, visitor) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === ".next" || entry.name === "node_modules") {
      continue;
    }
    const entryPath = path.resolve(directory, entry.name);
    if (entry.isDirectory()) {
      walk(entryPath, visitor);
    } else {
      visitor(entryPath);
    }
  }
}

function assertInsideStandalone(target) {
  const relative = path.relative(standaloneRoot, target);
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Refusing to prune path outside standalone: ${target}`);
  }
}

const config = fs.readFileSync(configPath, "utf8");
if (!/images\s*:\s*\{[\s\S]*?unoptimized\s*:\s*true/.test(config)) {
  throw new Error("Next image optimization must be disabled before pruning Sharp.");
}

const imports = [];
walk(path.resolve(managerRoot, "app"), (sourcePath) => {
  if (
    sourceExtensions.has(path.extname(sourcePath)) &&
    importPattern.test(fs.readFileSync(sourcePath, "utf8"))
  ) {
    imports.push(path.relative(managerRoot, sourcePath));
  }
});
walk(path.resolve(managerRoot, "components"), (sourcePath) => {
  if (
    sourceExtensions.has(path.extname(sourcePath)) &&
    importPattern.test(fs.readFileSync(sourcePath, "utf8"))
  ) {
    imports.push(path.relative(managerRoot, sourcePath));
  }
});
if (imports.length > 0) {
  throw new Error(`next/image imports prevent pruning: ${imports.join(", ")}`);
}
if (!fs.existsSync(standaloneRoot)) {
  throw new Error(`Standalone output does not exist: ${standaloneRoot}`);
}

const candidates = [
  path.resolve(standaloneRoot, "node_modules", "sharp"),
];
const imgRoot = path.resolve(standaloneRoot, "node_modules", "@img");
if (fs.existsSync(imgRoot)) {
  for (const entry of fs.readdirSync(imgRoot, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.startsWith("sharp-")) {
      candidates.push(path.resolve(imgRoot, entry.name));
    }
  }
}

const removed = [];
for (const target of candidates) {
  assertInsideStandalone(target);
  if (fs.existsSync(target)) {
    fs.rmSync(target, { recursive: true, force: false });
    removed.push(path.relative(standaloneRoot, target).replaceAll("\\", "/"));
  }
}

const remaining = candidates.filter((target) => fs.existsSync(target));
if (remaining.length > 0) {
  throw new Error(`Sharp runtime packages remain: ${remaining.join(", ")}`);
}

const report = {
  schema_version: 1,
  policy_id: "PR18-MANAGER-RUNTIME-SURFACE-V1",
  image_optimizer_disabled: true,
  next_image_imports: [],
  removed_packages: removed.sort(),
};
fs.writeFileSync(
  path.resolve(standaloneRoot, "pr18-runtime-surface.json"),
  `${JSON.stringify(report, null, 2)}\n`,
  "utf8",
);
console.log(JSON.stringify(report));
