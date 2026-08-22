import assert from "node:assert/strict";
import test from "node:test";
import {
  inspectApiRouteSource,
  inspectSource,
} from "./verify-bff-boundary.mjs";

test("allows authenticated client calls through the Manager BFF", () => {
  const violations = inspectSource(`
    "use client";
    import { bffRequest } from "../app/lib/bff";
    export async function save() {
      return bffRequest("/api/v1/workshop/work-orders", { method: "POST" });
    }
  `);
  assert.deepEqual(violations, []);
});

test("ignores backend access in server-only modules", () => {
  const violations = inspectSource(`
    export async function load() {
      return fetch("http://backend.internal/api/v1/trips");
    }
  `);
  assert.deepEqual(violations, []);
});

test("rejects direct and alternate browser network clients", () => {
  const violations = inspectSource(`
    "use client";
    const direct = "http://backend.internal/api/v1/trips";
    fetch(direct);
    fetch("/api/v1/drivers");
    new XMLHttpRequest();
  `);
  assert.equal(violations.filter((item) => item.includes("[direct-fetch]")).length, 2);
  assert.equal(
    violations.filter((item) => item.includes("[alternate-network-client]")).length,
    1,
  );
});

test("rejects browser token storage, public backend URLs and auth headers", () => {
  const violations = inspectSource(`
    "use client";
    const endpoint = process.env.NEXT_PUBLIC_API_URL;
    localStorage.setItem("access_token", access_token);
    fetch("/api/proxy", { headers: { Authorization: "Bearer secret" } });
  `);
  for (const rule of [
    "public-backend-url",
    "browser-storage",
    "browser-token",
    "browser-authorization",
  ]) {
    assert.ok(violations.some((item) => item.includes(`[${rule}]`)), rule);
  }
});

test("allows API route handlers through the common upstream helper", () => {
  const violations = inspectApiRouteSource(`
    import { upstreamFetch } from "@/app/lib/upstream-http";
    export async function GET() {
      return upstreamFetch("http://backend.internal/api/v1/trips");
    }
  `);
  assert.deepEqual(violations, []);
});

test("rejects direct fetch from API route handlers", () => {
  const violations = inspectApiRouteSource(`
    export async function GET() {
      return globalThis.fetch("http://backend.internal/api/v1/trips");
    }
  `);
  assert.equal(violations.length, 1);
  assert.match(violations[0], /direct-upstream-fetch/);
});
