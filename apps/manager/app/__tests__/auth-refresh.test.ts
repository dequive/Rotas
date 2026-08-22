import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  deleteCookie: vi.fn(),
  getCookie: vi.fn((name: string) =>
    name === "rotas_refresh_token" ? { value: "refresh-old" } : undefined,
  ),
  setCookie: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    delete: state.deleteCookie,
    get: state.getCookie,
    set: state.setCookie,
  })),
}));

import { refreshAccessToken } from "../lib/auth";

describe("refreshAccessToken concurrency", () => {
  beforeEach(() => {
    state.deleteCookie.mockReset();
    state.getCookie.mockClear();
    state.setCookie.mockReset();
    vi.restoreAllMocks();
  });

  it("coalesces concurrent refreshes of the same rotating token", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "access-new",
          refresh_token: "refresh-new",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const refreshed = await Promise.all([
      refreshAccessToken(),
      refreshAccessToken(),
      refreshAccessToken(),
    ]);

    expect(refreshed).toEqual(["access-new", "access-new", "access-new"]);
    expect(upstream).toHaveBeenCalledOnce();
    expect(state.deleteCookie).not.toHaveBeenCalled();
    expect(state.setCookie).toHaveBeenCalledTimes(6);
  });
});
