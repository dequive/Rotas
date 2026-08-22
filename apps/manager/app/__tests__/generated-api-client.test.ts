import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  request: vi.fn(),
}));

vi.mock("../lib/bff", () => ({
  bffRequest: state.request,
}));

import { generatedApiClient } from "../lib/generated-api-client";

describe("generated OpenAPI client", () => {
  beforeEach(() => {
    state.request.mockReset();
  });

  it("routes typed OpenAPI operations through the Manager BFF", async () => {
    state.request.mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await generatedApiClient.GET("/api/v1/alerts");

    expect(result.error).toBeUndefined();
    expect(result.data).toEqual([]);
    expect(state.request).toHaveBeenCalledOnce();
    expect(state.request.mock.calls[0]?.[0]).toBe("/api/v1/alerts");
    expect(state.request.mock.calls[0]?.[1]).toMatchObject({ method: "GET" });
    expect(
      new Headers(state.request.mock.calls[0]?.[1]?.headers).has("Authorization"),
    ).toBe(false);
  });
});
