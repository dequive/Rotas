import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  refreshTokenPair: vi.fn(),
}));

vi.mock("../lib/auth-refresh", () => ({
  refreshTokenPair: state.refreshTokenPair,
  shouldRefreshAccessToken: (token: string) => token.startsWith("expired."),
}));

import { proxy } from "../../proxy";

describe("Middleware", () => {
  beforeEach(() => {
    state.refreshTokenPair.mockReset();
  });

  it("redirects unauthenticated users to login", async () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = await proxy(req);
    expect(res?.status).toBe(307);
    expect(res?.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("allows unauthenticated users to access login, register, password recovery, email verification", async () => {
    const paths = ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email"];
    for (const path of paths) {
      const req = new NextRequest(`http://localhost:3000${path}`);
      const res = await proxy(req);
      expect(res?.headers.get("location")).toBeNull();
    }
  });

  it("redirects authenticated users away from login/register/forgot-password/reset-password to home", async () => {
    const paths = ["/login", "/register", "/forgot-password", "/reset-password"];
    for (const path of paths) {
      const req = new NextRequest(`http://localhost:3000${path}`);
      req.cookies.set("rotas_access_token", "some-token-value");
      const res = await proxy(req);
      expect(res?.status).toBe(307);
      expect(res?.headers.get("location")).toBe("http://localhost:3000/");
    }
  });

  it("allows authenticated users to access dashboard", async () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    req.cookies.set("rotas_access_token", "some-token-value");
    const res = await proxy(req);
    expect(res?.headers.get("location")).toBeNull();
  });

  it("always allows API requests regardless of authentication", async () => {
    const req = new NextRequest("http://localhost:3000/api/some-endpoint");
    const res = await proxy(req);
    expect(res?.headers.get("location")).toBeNull();
  });

  it("refreshes an expired page session before Server Components execute", async () => {
    state.refreshTokenPair.mockResolvedValue({
      accessToken: "access-new",
      refreshToken: "refresh-new",
    });
    const req = new NextRequest("http://localhost:3000/dashboard");
    req.cookies.set("rotas_access_token", "expired.access-token");
    req.cookies.set("rotas_refresh_token", "refresh-old");

    const res = await proxy(req);

    expect(state.refreshTokenPair).toHaveBeenCalledWith("refresh-old");
    expect(res.headers.get("set-cookie")).toContain("rotas_access_token=access-new");
    expect(res.headers.get("set-cookie")).toContain("rotas_refresh_token=refresh-new");
    expect(res.headers.get("x-middleware-request-cookie")).toContain(
      "rotas_access_token=access-new",
    );
  });
});
