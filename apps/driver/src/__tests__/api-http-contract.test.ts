import { HttpContractError } from "@rotas/http-contract";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createTrip, getVehicles } from "../api";

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
  it("repete uma mutação transitória com a mesma chave", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: "trip-1", origin: "Maputo", destination: "Beira", status: "draft",
        billing_status: "not_billed", load_state: null, vehicle_id: "vehicle-1",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const trip = await createTrip({
      vehicle_id: "vehicle-1", driver_id: "driver-1", origin: "Maputo", destination: "Beira",
    });
    expect(trip.id).toBe("trip-1");
    const keys = fetchMock.mock.calls.map(([, init]) => new Headers(init?.headers).get("Idempotency-Key"));
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });

  it("expõe o envelope como HttpContractError tipado", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      error: { code: "tenant_scope_invalid", message: "Tenant inválido.", details: { tenant_id: "tenant-1" } },
    }), { status: 403, headers: { "Content-Type": "application/json" } })));
    await expect(getVehicles()).rejects.toEqual(expect.objectContaining<HttpContractError>({
      name: "HttpContractError", status: 403, code: "tenant_scope_invalid",
      message: "Tenant inválido.", details: { tenant_id: "tenant-1" }, retryable: false,
    }));
  });
});
