import assert from "node:assert/strict";
import test from "node:test";
import {
  auditContractReferences,
  extractContractReferences,
  inspectContractReference,
  matchOpenApiOperation,
  normalizeRuntimePath,
} from "./verify-api-contracts.mjs";

const spec = {
  paths: {
    "/api/v1/checklists": {
      get: {
        responses: {
          200: {
            content: {
              "application/json": {
                schema: { type: "array", items: { $ref: "#/components/schemas/Checklist" } },
              },
            },
          },
        },
      },
    },
    "/api/v1/trips/{trip_id}/start": {
      post: {
        responses: {
          200: {
            content: {
              "application/json": { schema: { $ref: "#/components/schemas/Trip" } },
            },
          },
        },
      },
    },
    "/api/v1/empty": {
      get: {
        responses: {
          200: { content: { "application/json": { schema: {} } } },
        },
      },
    },
  },
};

test("normalizes query strings and runtime template values", () => {
  assert.equal(
    normalizeRuntimePath("/api/v1/trips/${tripId}/start?include=audit"),
    "/api/v1/trips/{param}/start",
  );
});

test("removes an interpolated query suffix without treating it as a path parameter", () => {
  assert.equal(normalizeRuntimePath("/api/v1/alerts${query}"), "/api/v1/alerts");
  assert.equal(
    normalizeRuntimePath("/api/v1/billing/ar/summary${asOfParam}&limit=5"),
    "/api/v1/billing/ar/summary",
  );
  assert.equal(
    normalizeRuntimePath('/api/v1/auth/sessions${userId ? `?user_id=${userId}` : ""}'),
    "/api/v1/auth/sessions",
  );
});

test("matches runtime paths to OpenAPI templates without depending on parameter names", () => {
  const match = matchOpenApiOperation(spec, "POST", "/api/v1/trips/${tripId}/start");
  assert.equal(match?.path, "/api/v1/trips/{trip_id}/start");
});

test("rejects an endpoint or HTTP method absent from OpenAPI", () => {
  const result = inspectContractReference(spec, {
    method: "GET",
    path: "/api/v1/checklists/checklists",
    source: "fixture.tsx:1",
  });
  assert.deepEqual(result.violations.map((item) => item.rule), ["missing-operation"]);
});

test("rejects empty success response schemas", () => {
  const result = inspectContractReference(spec, {
    method: "GET",
    path: "/api/v1/empty",
    source: "fixture.tsx:1",
  });
  assert.deepEqual(result.violations.map((item) => item.rule), ["empty-success-schema"]);
});

test("accepts an operation with a typed success response", () => {
  const result = inspectContractReference(spec, {
    method: "GET",
    path: "/api/v1/checklists?limit=5",
    source: "fixture.tsx:1",
  });
  assert.deepEqual(result.violations, []);
});

test("extracts methods and template paths from approved frontend clients", () => {
  const references = extractContractReferences(
    `
      await apiFetch("/api/v1/checklists?limit=5");
      const response = await bffRequest(\`/api/v1/trips/\${tripId}/start\`, {
        method: "POST",
      });
      await fetch("/api/clients");
    `,
    "fixture.tsx",
  );

  assert.deepEqual(
    references.map(({ client, method, path }) => ({ client, method, path })),
    [
      { client: "apiFetch", method: "GET", path: "/api/v1/checklists?limit=5" },
      { client: "bffRequest", method: "POST", path: "/api/v1/trips/${tripId}/start" },
    ],
  );
});

test("extracts external service paths from URL templates", () => {
  const references = extractContractReferences(
    "await fetch(`${GOVERNANCE_API}/api/v1/cases`, { method: 'POST' });",
    "fixture.ts",
  );
  assert.equal(references[0].path, "/api/v1/cases");
  assert.equal(references[0].client, "fetch");
  assert.equal(references[0].method, "POST");
});

test("audits every discovered reference and preserves source evidence", () => {
  const audit = auditContractReferences(spec, [
    { method: "GET", path: "/api/v1/checklists", source: "good.ts:4" },
    { method: "GET", path: "/api/v1/missing", source: "bad.ts:9" },
  ]);

  assert.equal(audit.references.length, 2);
  assert.deepEqual(audit.violations, [
    {
      rule: "missing-operation",
      message: "GET /api/v1/missing is absent from OpenAPI.",
      source: "bad.ts:9",
    },
  ]);
});
