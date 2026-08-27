import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const managerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const appRoot = path.join(managerRoot, "app");
const apiRoot = path.join(appRoot, "api");
const sourceExtensions = new Set([".ts", ".tsx"]);
const ignoredDirectories = new Set(["__tests__", "api"]);

function collectSourceFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) {
        files.push(...collectSourceFiles(path.join(directory, entry.name)));
      }
      continue;
    }
    if (sourceExtensions.has(path.extname(entry.name))) {
      files.push(path.join(directory, entry.name));
    }
  }
  return files;
}

function isClientModule(sourceFile) {
  const first = sourceFile.statements[0];
  return Boolean(
    first &&
      ts.isExpressionStatement(first) &&
      ts.isStringLiteral(first.expression) &&
      first.expression.text === "use client",
  );
}

function propertyName(node) {
  if (ts.isIdentifier(node) || ts.isStringLiteral(node)) {
    return node.text;
  }
  return "";
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
  return "";
}

function isDirectBackendTarget(value) {
  return /^https?:\/\//i.test(value) || /^\/api\/v1(?:\/|$|\?)/.test(value);
}

function location(sourceFile, node) {
  const point = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return `${path.relative(managerRoot, sourceFile.fileName)}:${point.line + 1}:${point.character + 1}`;
}

export function inspectClientModule(sourceFile) {
  const violations = [];
  const bindings = new Map();
  const backendEnvironmentNames = new Set([
    "NEXT_PUBLIC_API_URL",
    "ROTAS_API_BASE_URL",
    "VITE_ROTAS_API_BASE_URL",
  ]);
  const forbiddenNetworkConstructors = new Set([
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
  ]);

  function report(node, rule, message) {
    violations.push(`${location(sourceFile, node)} [${rule}] ${message}`);
  }

  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const value = staticPrefix(node.initializer, bindings);
      if (value) bindings.set(node.name.text, value);
    }

    if (
      ts.isIdentifier(node) &&
      ["localStorage", "sessionStorage"].includes(node.text)
    ) {
      report(
        node,
        "browser-storage",
        `${node.text} is forbidden in authenticated Manager client modules.`,
      );
    }

    if (isProcessEnvReference(node, backendEnvironmentNames)) {
      report(
        node,
        "public-backend-url",
        `${node.name.text} exposes a backend address to browser code.`,
      );
    }

    if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier) &&
      /(?:^|\/)lib\/api$/.test(node.moduleSpecifier.text)
    ) {
      report(
        node,
        "server-api-import",
        "Client modules must use the BFF helper or a dedicated /api route.",
      );
    }

    if (isFetchCall(node)) {
      const target = node.arguments[0];
      const prefix = target ? staticPrefix(target, bindings) : "";
      if (prefix && isDirectBackendTarget(prefix)) {
        report(
          node,
          "direct-fetch",
          `Browser fetch targets the backend directly (${prefix}).`,
        );
      }
    }

    if (
      ts.isNewExpression(node) &&
      ts.isIdentifier(node.expression) &&
      forbiddenNetworkConstructors.has(node.expression.text)
    ) {
      report(
        node,
        "alternate-network-client",
        `${node.expression.text} bypasses the approved BFF boundary.`,
      );
    }

    if (
      ts.isPropertyAssignment(node) &&
      propertyName(node.name).toLowerCase() === "authorization"
    ) {
      report(
        node,
        "browser-authorization",
        "Authorization headers may only be assembled inside server-side BFF routes.",
      );
    }

    if (
      ts.isIdentifier(node) &&
      ["access_token", "refresh_token"].includes(node.text)
    ) {
      report(
        node,
        "browser-token",
        `${node.text} must never be handled by a client module.`,
      );
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}

export function inspectSource(source, fileName = "fixture.tsx") {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  return isClientModule(sourceFile) ? inspectClientModule(sourceFile) : [];
}

export function inspectApiRouteSource(source, fileName = "app/api/fixture/route.ts") {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
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

export function verifyUpstreamBoundary(root = apiRoot) {
  const routeFiles = [];
  const violations = [];

  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        visit(target);
      } else if (entry.name === "route.ts") {
        routeFiles.push(target);
        violations.push(
          ...inspectApiRouteSource(fs.readFileSync(target, "utf8"), target),
        );
      }
    }
  }

  visit(root);
  return { routeFiles, violations };
}

export function verifyBoundary(root = appRoot) {
  const clientModules = [];
  const violations = [];
  for (const file of collectSourceFiles(root)) {
    const source = fs.readFileSync(file, "utf8");
    const sourceViolations = inspectSource(source, file);
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    if (!isClientModule(sourceFile)) continue;
    clientModules.push(file);
    violations.push(...sourceViolations);
  }
  return { clientModules, violations };
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  const clientResult = verifyBoundary();
  const upstreamResult = verifyUpstreamBoundary();
  const violations = [
    ...clientResult.violations,
    ...upstreamResult.violations,
  ];
  if (violations.length > 0) {
    console.error("Manager BFF boundary violations:");
    for (const violation of violations) console.error(`- ${violation}`);
    process.exit(1);
  }
  console.log(
    `Manager BFF boundary verified: ${clientResult.clientModules.length} client modules, ` +
      `${upstreamResult.routeFiles.length} API route handlers, 0 violations.`,
  );
}
