import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  setCookie: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    set: state.setCookie,
  })),
}));

import { POST } from "../api/auth/login/route";

describe("authentication BFF boundary", () => {
  beforeEach(() => {
    state.setCookie.mockReset();
    vi.restoreAllMocks();
  });

  it("keeps access and refresh tokens in HttpOnly cookies", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "access-secret",
          refresh_token: "refresh-secret",
          user: {
            id: "user-1",
            tenant_id: "tenant-1",
            role: "admin",
            full_name: "Tenant Admin",
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const request = new NextRequest("http://manager.local/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "admin@tenant.test",
        password: "not-returned",
      }),
    });

    const response = await POST(request);
    const body = (await response.json()) as Record<string, unknown>;

    expect(response.status).toBe(200);
    expect(body).toEqual({ ok: true });
    expect(JSON.stringify(body)).not.toContain("access-secret");
    expect(JSON.stringify(body)).not.toContain("refresh-secret");
    expect(upstream).toHaveBeenCalledOnce();

    for (const [name, value] of [
      ["rotas_access_token", "access-secret"],
      ["rotas_refresh_token", "refresh-secret"],
    ]) {
      const cookieCall = state.setCookie.mock.calls.find(
        ([cookieName]) => cookieName === name,
      );
      expect(cookieCall).toBeDefined();
      expect(cookieCall?.[1]).toBe(value);
      expect(cookieCall?.[2]).toMatchObject({
        httpOnly: true,
        sameSite: "lax",
        path: "/",
      });
    }
  });
});
