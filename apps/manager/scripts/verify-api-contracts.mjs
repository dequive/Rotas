import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const scriptPath = fileURLToPath(import.meta.url);
const managerRoot = path.resolve(path.dirname(scriptPath), "..");
const workspaceRoot = path.resolve(managerRoot, "../..");
const defaultSourceRoot = path.join(managerRoot, "app");
const defaultSpecPath = path.join(workspaceRoot, "backend", "openapi", "rotas-v1.json");

function stripQuery(value) {
  return value.split("?", 1)[0].replace(/\/$/, "") || "/";
}

export function normalizeRuntimePath(value) {
  return stripQuery(value)
    .replace(/([^/])\$\{[\s\S]+$/, "$1")
    .replace(/\$\{[^}]+\}/g, "{param}");
}

function pathMatches(openApiPath, runtimePath) {
  const expected = stripQuery(openApiPath).split("/");
  const actual = normalizeRuntimePath(runtimePath).split("/");
  if (expected.length !== actual.length) return false;

  return expected.every((segment, index) => {
    const candidate = actual[index];
    const expectedParameter = /^\{[^}]+\}$/.test(segment);
    const runtimeParameter = /^\{[^}]+\}$/.test(candidate);
    return expectedParameter || runtimeParameter || segment === candidate;
  });
}

export function matchOpenApiOperation(spec, method, runtimePath) {
  const normalizedMethod = method.toLowerCase();
  for (const [openApiPath, pathItem] of Object.entries(spec.paths ?? {})) {
    if (!pathMatches(openApiPath, runtimePath)) continue;
    const operation = pathItem?.[normalizedMethod];
    if (operation) return { path: openApiPath, method: normalizedMethod, operation };
  }
  return null;
}

function isNonEmptySchema(schema) {
  return Boolean(
    schema &&
      typeof schema === "object" &&
      (Object.keys(schema).length > 0 || schema === true),
  );
}

function hasTypedSuccessResponse(operation) {
  const responses = operation.responses ?? {};
  for (const [status, response] of Object.entries(responses)) {
    if (!/^2\d\d$/.test(status)) continue;
    if (status === "204") return true;
    const content = response?.content ?? {};
    if (
      Object.values(content).some((mediaType) => isNonEmptySchema(mediaType?.schema))
    ) {
      return true;
    }
  }
  return false;
}

export function inspectContractReference(spec, reference) {
  const match = matchOpenApiOperation(spec, reference.method, reference.path);
  if (!match) {
    return {
      reference,
      match: null,
      violations: [
        {
          rule: "missing-operation",
          message: `${reference.method} ${reference.path} is absent from OpenAPI.`,
        },
      ],
    };
  }

  if (!hasTypedSuccessResponse(match.operation)) {
    return {
      reference,
      match,
      violations: [
        {
          rule: "empty-success-schema",
          message: `${reference.method} ${match.path} has no typed success response.`,
        },
      ],
    };
  }

  return { reference, match, violations: [] };
}

export function auditContractReferences(spec, references) {
  const violations = references.flatMap((reference) =>
    inspectContractReference(spec, reference).violations.map((violation) => ({
      ...violation,
      source: reference.source,
    })),
  );

  return { references, violations };
}

function collectSourceFiles(directory) {
  const files = [];
  const ignoredDirectories = new Set(["__tests__", ".next", "node_modules"]);
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) {
        files.push(...collectSourceFiles(path.join(directory, entry.name)));
      }
      continue;
    }
    if ([".ts", ".tsx"].includes(path.extname(entry.name))) {
      files.push(path.join(directory, entry.name));
    }
  }
  return files;
}

export function verifyManagerApiContracts({
  sourceRoot = defaultSourceRoot,
  specPath = defaultSpecPath,
} = {}) {
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  const references = collectSourceFiles(sourceRoot).flatMap((file) =>
    extractContractReferences(
      fs.readFileSync(file, "utf8"),
      path.relative(workspaceRoot, file).replaceAll("\\", "/"),
    ),
  );
  return auditContractReferences(spec, references);
}

function expressionText(node, sourceFile) {
  if (ts.isStringLiteralLike(node)) return node.text;
  if (!ts.isTemplateExpression(node)) return null;
  let value = node.head.text;
  for (const span of node.templateSpans) {
    value += `\${${span.expression.getText(sourceFile)}}${span.literal.text}`;
  }
  return value;
}

function requestMethod(options) {
  if (!options || !ts.isObjectLiteralExpression(options)) return "GET";
  for (const property of options.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    const name = property.name.getText().replace(/["']/g, "");
    if (name !== "method" || !ts.isStringLiteralLike(property.initializer)) continue;
    return property.initializer.text.toUpperCase();
  }
  return "GET";
}

function lineLocation(sourceFile, node, fileName) {
  const point = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
  return `${fileName}:${point.line + 1}:${point.character + 1}`;
}

export function extractContractReferences(source, fileName = "fixture.ts") {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const references = [];
  const supportedClients = new Set([
    "apiFetch",
    "bffFetch",
    "bffRequest",
    "fetch",
    "upstreamFetch",
  ]);

  function visit(node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const client = node.expression.text;
      if (supportedClients.has(client)) {
        const rawTarget = node.arguments[0]
          ? expressionText(node.arguments[0], sourceFile)
          : null;
        const apiIndex = rawTarget?.indexOf("/api/v1/") ?? -1;
        if (rawTarget && apiIndex >= 0) {
          references.push({
            client,
            method: requestMethod(node.arguments[1]),
            path: rawTarget.slice(apiIndex),
            source: lineLocation(sourceFile, node, fileName),
          });
        }
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return references;
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const reportOnly = process.argv.includes("--report");
  const result = verifyManagerApiContracts();
  const distinctOperations = new Set(
    result.references.map(({ method, path: runtimePath }) =>
      `${method} ${normalizeRuntimePath(runtimePath)}`,
    ),
  );

  if (result.violations.length > 0) {
    console.error(
      `Manager API contract audit: ${result.references.length} references, ` +
        `${distinctOperations.size} operations, ${result.violations.length} violations.`,
    );
    for (const violation of result.violations) {
      console.error(`- ${violation.source} [${violation.rule}] ${violation.message}`);
    }
    if (!reportOnly) process.exitCode = 1;
  } else {
    console.log(
      `Manager API contracts verified: ${result.references.length} references, ` +
        `${distinctOperations.size} operations, 0 violations.`,
    );
  }
}
