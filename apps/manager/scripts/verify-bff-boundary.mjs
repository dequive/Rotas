import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const managerRoot = process.env.ROTAS_MANAGER_ROOT
  ? path.resolve(process.env.ROTAS_MANAGER_ROOT)
  : path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appRoot = path.join(managerRoot, "app");
const sourceExtensions = [".ts", ".tsx"];
const ignoredDirectories = new Set(["__tests__", "api", "generated", "node_modules", ".next"]);

function collectSourceFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) files.push(...collectSourceFiles(path.join(directory, entry.name)));
      continue;
    }
    if (sourceExtensions.includes(path.extname(entry.name))) files.push(path.resolve(directory, entry.name));
  }
  return files;
}

function collectApiRouteFiles(root) {
  const apiRoot = path.join(root, "api");
  if (!fs.existsSync(apiRoot)) return [];
  return collectAllFiles(apiRoot).filter((file) => path.basename(file) === "route.ts");
}

function collectAllFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...collectAllFiles(target));
    else files.push(path.resolve(target));
  }
  return files;
}

function parse(fileName, source = fs.readFileSync(fileName, "utf8")) {
  return ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
}

function isClientModule(sourceFile) {
  const first = sourceFile.statements[0];
  return Boolean(
    first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) && first.expression.text === "use client",
  );
}

function isServerActionModule(sourceFile) {
  const first = sourceFile.statements[0];
  return Boolean(
    first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) && first.expression.text === "use server",
  );
}

function propertyName(node) {
  return ts.isIdentifier(node) || ts.isStringLiteral(node) ? node.text : "";
}

function isProcessEnvReference(node, names) {
  return (
    ts.isPropertyAccessExpression(node) &&
    names.has(node.name.text) &&
    ts.isPropertyAccessExpression(node.expression) &&
    node.expression.name.text === "env" &&
    ts.isIdentifier(node.expression.expression) &&
    node.expression.expression.text === "process"
  );
}

function isFetchCall(node) {
  if (!ts.isCallExpression(node)) return false;
  if (ts.isIdentifier(node.expression)) return node.expression.text === "fetch";
  return (
    ts.isPropertyAccessExpression(node.expression) &&
    node.expression.name.text === "fetch" &&
    ts.isIdentifier(node.expression.expression) &&
    ["globalThis", "window"].includes(node.expression.expression.text)
  );
}

function staticPrefix(node, bindings) {
  if (ts.isStringLiteralLike(node)) return node.text;
  if (ts.isTemplateExpression(node)) return node.head.text;
  if (ts.isIdentifier(node)) return bindings.get(node.text) ?? "";
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    return `${staticPrefix(node.left, bindings)}${staticPrefix(node.right, bindings)}`;
  }
  return "";
}

function isDirectBackendTarget(value) {
  return /^https?:\/\//i.test(value) || /^\/api\/v1(?:\/|$|\?)/.test(value);
}

function location(sourceFile, node) {
  const point = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return `${path.relative(managerRoot, sourceFile.fileName)}:${point.line + 1}:${point.character + 1}`;
}

export function inspectBrowserModule(sourceFile) {
  const violations = [];
  const bindings = new Map();
  const backendEnvironmentNames = new Set([
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_ROTAS_API_BASE_URL",
    "ROTAS_API_BASE_URL",
    "VITE_ROTAS_API_BASE_URL",
  ]);
  const forbiddenNetworkConstructors = new Set(["XMLHttpRequest", "WebSocket", "EventSource"]);

  function report(node, rule, message) {
    violations.push(`${location(sourceFile, node)} [${rule}] ${message}`);
  }

  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      bindings.set(node.name.text, node.initializer);
    }
    if (ts.isIdentifier(node) && ["localStorage", "sessionStorage"].includes(node.text)) {
      report(node, "browser-storage", `${node.text} is forbidden in authenticated browser modules.`);
    }
    if (isProcessEnvReference(node, backendEnvironmentNames)) {
      report(node, "public-backend-url", `${node.name.text} exposes a backend address to browser code.`);
    }
    if (isFetchCall(node)) {
      const target = node.arguments[0];
      const prefix = target ? staticPrefix(target, new Map([...bindings].map(([name, value]) => [name, staticPrefix(value, new Map())]))) : "";
      const approvedHelper = sourceFile.fileName.replaceAll("\\", "/").endsWith("/app/lib/bff.ts");
      if (!prefix && !approvedHelper) report(node, "dynamic-fetch", "Browser fetch target cannot be proven to use the Manager BFF.");
      else if (isDirectBackendTarget(prefix)) report(node, "direct-fetch", `Browser fetch targets the backend directly (${prefix}).`);
    }
    if (ts.isNewExpression(node) && ts.isIdentifier(node.expression) && forbiddenNetworkConstructors.has(node.expression.text)) {
      report(node, "alternate-network-client", `${node.expression.text} bypasses the approved BFF boundary.`);
    }
    if (ts.isPropertyAssignment(node) && propertyName(node.name).toLowerCase() === "authorization") {
      report(node, "browser-authorization", "Authorization headers may only be assembled inside server-side BFF code.");
    }
    if (ts.isIdentifier(node) && ["access_token", "refresh_token"].includes(node.text)) {
      report(node, "browser-token", `${node.text} must never be handled by browser code.`);
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

function resolveLocalImport(fromFile, specifier) {
  let base;
  if (specifier.startsWith("@/")) base = path.join(managerRoot, specifier.slice(2));
  else if (specifier.startsWith(".")) base = path.resolve(path.dirname(fromFile), specifier);
  else return null;
  const candidates = [
    base,
    ...sourceExtensions.map((extension) => `${base}${extension}`),
    ...sourceExtensions.map((extension) => path.join(base, `index${extension}`)),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile()) ?? null;
}

function localDependencies(sourceFile) {
  const dependencies = new Set();
  for (const statement of sourceFile.statements) {
    const moduleSpecifier =
      (ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement)) && statement.moduleSpecifier;
    if (!moduleSpecifier || !ts.isStringLiteral(moduleSpecifier)) continue;
    if (ts.isImportDeclaration(statement) && statement.importClause?.isTypeOnly) continue;
    const resolved = resolveLocalImport(sourceFile.fileName, moduleSpecifier.text);
    if (resolved) dependencies.add(resolved);
  }
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments.length === 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      const resolved = resolveLocalImport(sourceFile.fileName, node.arguments[0].text);
      if (resolved) dependencies.add(resolved);
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return [...dependencies];
}

export function inspectSource(source, fileName = path.join(appRoot, "fixture.tsx"), browserReachable = true) {
  return browserReachable ? inspectBrowserModule(parse(fileName, source)) : [];
}

export function inspectApiRouteSource(source, fileName = path.join(appRoot, "api", "fixture", "route.ts")) {
  const sourceFile = parse(fileName, source);
  const violations = [];
  function visit(node) {
    if (isFetchCall(node)) {
      violations.push(
        `${location(sourceFile, node)} [direct-upstream-fetch] API route handlers must use upstreamFetch().`,
      );
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return violations;
}

export function verifyBoundary(root = appRoot) {
  const files = collectSourceFiles(root);
  const sourceFiles = new Map(files.map((file) => [file, parse(file)]));
  const roots = files.filter((file) => isClientModule(sourceFiles.get(file)));
  const reachable = new Set();
  const parent = new Map(roots.map((file) => [file, null]));
  const queue = [...roots];
  while (queue.length > 0) {
    const file = queue.pop();
    if (!file || reachable.has(file)) continue;
    reachable.add(file);
    const sourceFile = sourceFiles.get(file) ?? parse(file);
    sourceFiles.set(file, sourceFile);
    if (isServerActionModule(sourceFile)) continue;
    for (const dependency of localDependencies(sourceFile)) {
      if (!parent.has(dependency)) parent.set(dependency, file);
      queue.push(dependency);
    }
  }
  const violations = [];
  for (const file of reachable) {
    if (isServerActionModule(sourceFiles.get(file))) continue;
    const chain = [];
    for (let current = file; current; current = parent.get(current)) {
      chain.unshift(path.relative(managerRoot, current));
    }
    violations.push(
      ...inspectBrowserModule(sourceFiles.get(file)).map(
        (violation) => `${violation} [import-chain: ${chain.join(" -> ")}]`,
      ),
    );
  }
  const routeHandlers = collectApiRouteFiles(root);
  for (const file of routeHandlers) {
    violations.push(...inspectApiRouteSource(fs.readFileSync(file, "utf8"), file));
  }
  return { clientRoots: roots, browserModules: [...reachable], routeHandlers, violations };
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  const result = verifyBoundary();
  if (result.violations.length > 0) {
    console.error("Manager BFF boundary violations:");
    for (const violation of result.violations) console.error(`- ${violation}`);
    process.exit(1);
  }
  console.log(
    `Manager BFF boundary verified: ${result.clientRoots.length} client roots, ` +
      `${result.browserModules.length} browser-reachable modules, ` +
      `${result.routeHandlers.length} API route handlers, 0 violations.`,
  );
}
