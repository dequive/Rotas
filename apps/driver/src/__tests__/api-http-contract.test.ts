import { HttpContractError } from "@rotas/http-contract";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { bootstrap } from "../api";

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("rotas_access_token", "access-token");
  localStorage.setItem("rotas_tenant_id", "tenant-1");
  localStorage.setItem("rotas_driver_id", "driver-1");
  localStorage.setItem("rotas_device_id", "device-1");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Driver HTTP contract", () => {
  it("carrega apenas o bootstrap atribuído com a identidade autenticada", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        profile: {
          tenant_id: "tenant-1",
          driver_id: "driver-1",
          device_id: "device-1",
        },
        checklistTemplates: [],
        activeTrip: null,
        vehicles: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const data = await bootstrap();

    expect(data.activeTrip).toBeNull();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/v1/driver/bootstrap");
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("X-Tenant-Id")).toBe("tenant-1");
    expect(headers.has("Idempotency-Key")).toBe(false);
  });

  it("expõe o envelope de erro do bootstrap como HttpContractError tipado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "driver_access_revoked",
              message: "Acesso revogado.",
              details: {},
            },
          }),
          {
            status: 403,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    await expect(bootstrap()).rejects.toEqual(
      expect.objectContaining<HttpContractError>({
        name: "HttpContractError",
        status: 403,
        code: "driver_access_revoked",
        message: "Acesso revogado.",
        details: {},
        retryable: false,
      }),
    );
  });
});
