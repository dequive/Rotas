import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  refreshedToken: "rotated-token" as string | null,
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => {
      const values: Record<string, string> = {
        rotas_access_token: "expired-token",
        rotas_tenant_id: "tenant-1",
      };
      return values[name] ? { value: values[name] } : undefined;
    },
  })),
}));

vi.mock("../lib/auth", () => ({
  refreshAccessToken: vi.fn(async () => state.refreshedToken),
}));

import { POST } from "../api/trips/route";

describe("trips BFF route", () => {
  beforeEach(() => {
    state.refreshedToken = "rotated-token";
    vi.restoreAllMocks();
  });

  it("preserves the idempotency key when retrying after access-token refresh", async () => {
    const upstream = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "in_progress" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const request = new NextRequest("http://manager.local/api/trips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ _action: "start", id: "trip-1", km_start: 1200 }),
    });

    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(2);
    const firstHeaders = new Headers(upstream.mock.calls[0]?.[1]?.headers);
    const retryHeaders = new Headers(upstream.mock.calls[1]?.[1]?.headers);
    expect(firstHeaders.get("Idempotency-Key")).toBe("manager:trip:start:trip-1");
    expect(retryHeaders.get("Idempotency-Key")).toBe(
      firstHeaders.get("Idempotency-Key"),
    );
    expect(retryHeaders.get("Authorization")).toBe("Bearer rotated-token");
  });
});
