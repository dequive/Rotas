import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  requestHeaders: new Map<string, string>(),
  refreshedToken: null as string | null,
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => {
      const value = state.cookies.get(name);
      return value ? { value } : undefined;
    },
  })),
  headers: vi.fn(async () => ({
    get: (name: string) =>
      state.requestHeaders.get(name) ??
      state.requestHeaders.get(name.toLowerCase()) ??
      null,
  })),
}));

vi.mock("../lib/auth", () => ({
  refreshAccessToken: vi.fn(async () => state.refreshedToken),
}));

import { GET } from "../api/proxy/route";
import { upstreamFetch } from "../lib/upstream-http";

describe("generic BFF proxy boundary", () => {
  beforeEach(() => {
    state.cookies.clear();
    state.cookies.set("rotas_access_token", "access-token");
    state.cookies.set("rotas_tenant_id", "tenant-1");
    state.requestHeaders.clear();
    state.refreshedToken = null;
    vi.restoreAllMocks();
  });

  it("preserves the upstream query without forwarding the BFF path parameter", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ items: [] }), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    const target = "/api/v1/items?limit=5";
    const req = new NextRequest(
      `http://manager.local/api/proxy?path=${encodeURIComponent(target)}`,
    );

    const response = await GET(req);

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledOnce();
    expect(upstream.mock.calls[0]?.[0]).toBe(`http://localhost:8000${target}`);
    const init = upstream.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer access-token",
    );
    expect(new Headers(init.headers).get("X-Tenant-Id")).toBe("tenant-1");
  });

  it("fails closed when the HttpOnly session is missing", async () => {
    state.cookies.clear();
    const upstream = vi.spyOn(globalThis, "fetch");
    const req = new NextRequest(
      "http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems",
    );

    const response = await GET(req);

    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("rejects paths outside the backend API allowlist", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const req = new NextRequest(
      "http://manager.local/api/proxy?path=https%3A%2F%2Fevil.example",
    );

    const response = await GET(req);

    expect(response.status).toBe(400);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("returns a typed safe failure when the upstream is unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const req = new NextRequest(
      "http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems",
    );

    const response = await GET(req);
    const body = (await response.json()) as { error: { code: string } };

    expect(response.status).toBe(502);
    expect(body.error.code).toBe("upstream_unavailable");
  });

  it("rotates an expired access token and retries once", async () => {
    state.refreshedToken = "rotated-token";
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          headers: { "Content-Type": "application/json" },
        }),
      );
    const req = new NextRequest(
      "http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems",
    );

    const response = await GET(req);

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(2);
    const retry = upstream.mock.calls[1]?.[1] as RequestInit;
    expect(new Headers(retry.headers).get("Authorization")).toBe(
      "Bearer rotated-token",
    );
  });

  it("propagates idempotency and correlation metadata at the upstream boundary", async () => {
    state.requestHeaders.set("Idempotency-Key", "operation-123");
    state.requestHeaders.set("X-Request-Id", "request-456");
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    const response = await upstreamFetch("http://localhost:8000/api/v1/items", {
      method: "POST",
      body: "{}",
    });

    expect(response.status).toBe(204);
    const init = upstream.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Idempotency-Key")).toBe("operation-123");
    expect(headers.get("X-Request-Id")).toBe("request-456");
  });
});
