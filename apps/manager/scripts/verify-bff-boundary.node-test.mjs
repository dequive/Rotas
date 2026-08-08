import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { inspectSource, verifyBoundary } from "./verify-bff-boundary.mjs";

test("allows same-origin calls through the Manager BFF", () => {
  assert.deepEqual(inspectSource(`"use client"; fetch("/api/proxy?path=/api/v1/trips");`), []);
});

test("rejects direct, dynamic and alternate browser clients", () => {
  const violations = inspectSource(`
    "use client";
    const direct = "http://backend.internal/api/v1/trips";
    fetch(direct);
    fetch("/api/v1/drivers");
    fetch(getEndpoint());
    new XMLHttpRequest();
  `);
  for (const rule of ["direct-fetch", "dynamic-fetch", "alternate-network-client"]) {
    assert.ok(violations.some((item) => item.includes(`[${rule}]`)), rule);
  }
});

test("rejects browser token storage, public backend URLs and auth headers", () => {
  const violations = inspectSource(`
    "use client";
    const endpoint = process.env.NEXT_PUBLIC_API_URL;
    localStorage.setItem("access_token", access_token);
    fetch("/api/proxy", { headers: { Authorization: "Bearer secret" } });
  `);
  for (const rule of ["public-backend-url", "browser-storage", "browser-token", "browser-authorization"]) {
    assert.ok(violations.some((item) => item.includes(`[${rule}]`)), rule);
  }
});

test("allows server-only source when it is not browser reachable", () => {
  assert.deepEqual(inspectSource(`fetch("http://backend.internal/api/v1/trips");`, "server.ts", false), []);
});

test("follows transitive local imports from a client root", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rotas-bff-"));
  try {
    fs.writeFileSync(
      path.join(root, "Client.tsx"),
      `"use client"; import { read } from "./helper"; export const value = read();`,
    );
    fs.writeFileSync(
      path.join(root, "helper.ts"),
      `export const read = () => localStorage.getItem("token");`,
    );
    const result = verifyBoundary(root);
    assert.equal(result.clientRoots.length, 1);
    assert.equal(result.browserModules.length, 2);
    assert.ok(result.violations.some((item) => item.includes("[browser-storage]")));
    assert.ok(result.violations.some((item) => item.includes("import-chain")));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("follows dynamic local imports from a client root", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rotas-bff-"));
  try {
    fs.writeFileSync(
      path.join(root, "Client.tsx"),
      `"use client"; export const load = () => import("./helper");`,
    );
    fs.writeFileSync(
      path.join(root, "helper.ts"),
      `export const token = sessionStorage.getItem("token");`,
    );
    const result = verifyBoundary(root);
    assert.equal(result.browserModules.length, 2);
    assert.ok(result.violations.some((item) => item.includes("[browser-storage]")));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("treats use-server actions as a terminal boundary", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rotas-bff-"));
  try {
    fs.writeFileSync(
      path.join(root, "Client.tsx"),
      `"use client"; import { save } from "./actions"; export { save };`,
    );
    fs.writeFileSync(
      path.join(root, "actions.ts"),
      `"use server"; import "./secret"; export async function save() {}`,
    );
    fs.writeFileSync(
      path.join(root, "secret.ts"),
      `export const secret = process.env.ROTAS_API_BASE_URL;`,
    );
    const result = verifyBoundary(root);
    assert.deepEqual(result.violations, []);
    assert.equal(result.browserModules.length, 2);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
