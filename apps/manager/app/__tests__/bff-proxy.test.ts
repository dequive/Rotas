import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  refreshedToken: null as string | null,
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => {
      const value = state.cookies.get(name);
      return value ? { value } : undefined;
    },
  })),
}));

vi.mock("../lib/auth", () => ({
  refreshAccessToken: vi.fn(async () => state.refreshedToken),
}));

import { GET, POST } from "../api/proxy/route";

describe("generic BFF proxy boundary", () => {
  beforeEach(() => {
    state.cookies.clear();
    state.cookies.set("rotas_access_token", "access-token");
    state.cookies.set("rotas_tenant_id", "tenant-1");
    state.refreshedToken = null;
    vi.restoreAllMocks();
  });

  it("preserves the upstream query without forwarding the BFF path parameter", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    const target = "/api/v1/items?limit=5";
    const response = await GET(
      new NextRequest(
        `http://manager.local/api/proxy?path=${encodeURIComponent(target)}`,
      ),
    );

    expect(response.status).toBe(200);
    expect(upstream.mock.calls[0]?.[0]).toBe(`http://localhost:8000${target}`);
    const headers = new Headers((upstream.mock.calls[0]?.[1] as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("X-Tenant-Id")).toBe("tenant-1");
  });

  it("fails closed when the HttpOnly session is missing", async () => {
    state.cookies.clear();
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await GET(
      new NextRequest("http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems"),
    );
    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it.each([
    "https://evil.example/api/v1/items",
    "//evil.example/api/v1/items",
    "/api/v1/../admin",
  ])("rejects non-allowlisted target %s", async (target) => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await GET(
      new NextRequest(
        `http://manager.local/api/proxy?path=${encodeURIComponent(target)}`,
      ),
    );
    expect(response.status).toBe(400);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("returns a safe typed failure when upstream is unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const response = await GET(
      new NextRequest("http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems"),
    );
    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "upstream_unavailable" },
    });
  });

  it("rotates an expired access token and retries once", async () => {
    state.refreshedToken = "rotated-token";
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true })));
    const response = await GET(
      new NextRequest("http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems"),
    );
    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(2);
    const retryHeaders = new Headers(
      (upstream.mock.calls[1]?.[1] as RequestInit).headers,
    );
    expect(retryHeaders.get("Authorization")).toBe("Bearer rotated-token");
  });

  it("rejects cross-origin mutations before reaching the backend", async () => {
    const upstream = vi.spyOn(globalThis, "fetch");
    const response = await POST(
      new NextRequest("http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems", {
        method: "POST",
        headers: { Origin: "https://evil.example" },
        body: JSON.stringify({ name: "malicious" }),
      }),
    );
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: { code: "cross_origin_request" },
    });
    expect(upstream).not.toHaveBeenCalled();
  });

  it("accepts same-origin mutations", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ ok: true })));
    const response = await POST(
      new NextRequest("http://manager.local/api/proxy?path=%2Fapi%2Fv1%2Fitems", {
        method: "POST",
        headers: { Origin: "http://manager.local", "Content-Type": "application/json" },
        body: JSON.stringify({ name: "safe" }),
      }),
    );
    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledOnce();
  });
});
