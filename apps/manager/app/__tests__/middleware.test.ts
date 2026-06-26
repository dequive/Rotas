import { NextRequest } from "next/server";
import { middleware } from "../../middleware";
import { describe, it, expect } from "vitest";

describe("Middleware", () => {
  it("redirects unauthenticated users to login", () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = middleware(req);
    expect(res?.status).toBe(307);
    expect(res?.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("allows unauthenticated users to access login, register, password recovery, email verification", () => {
    const paths = ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email"];
    for (const path of paths) {
      const req = new NextRequest(`http://localhost:3000${path}`);
      const res = middleware(req);
      expect(res?.headers.get("location")).toBeNull();
    }
  });

  it("redirects authenticated users away from login/register/forgot-password/reset-password to home", () => {
    const paths = ["/login", "/register", "/forgot-password", "/reset-password"];
    for (const path of paths) {
      const req = new NextRequest(`http://localhost:3000${path}`);
      req.cookies.set("rotas_access_token", "some-token-value");
      const res = middleware(req);
      expect(res?.status).toBe(307);
      expect(res?.headers.get("location")).toBe("http://localhost:3000/");
    }
  });

  it("allows authenticated users to access dashboard", () => {
    const req = new NextRequest("http://localhost:3000/dashboard");
    req.cookies.set("rotas_access_token", "some-token-value");
    const res = middleware(req);
    expect(res?.headers.get("location")).toBeNull();
  });

  it("always allows API requests regardless of authentication", () => {
    const req = new NextRequest("http://localhost:3000/api/some-endpoint");
    const res = middleware(req);
    expect(res?.headers.get("location")).toBeNull();
  });
});
