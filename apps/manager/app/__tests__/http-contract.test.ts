import { HttpContractError, requestWithPolicy, responseToHttpError } from "@rotas/http-contract";
import { afterEach, describe, expect, it, vi } from "vitest";
import { bffRequest } from "../lib/bff";

afterEach(() => vi.restoreAllMocks());

describe("contrato HTTP partilhado", () => {
  it("repete uma leitura transitória e respeita Retry-After", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 503, headers: { "Retry-After": "1" } }))
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));
    const sleep = vi.fn().mockResolvedValue(undefined);
    const response = await requestWithPolicy(
      "https://rotas.test/resource",
      { method: "GET" },
      { fetch: fetchMock, sleep, random: () => 0 },
    );
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(1_000);
  });

  it("não repete uma mutação sem chave de idempotência", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 503 }));
    const response = await requestWithPolicy(
      "https://rotas.test/resource",
      { method: "POST", body: "{}" },
      { fetch: fetchMock, sleep: vi.fn() },
    );
    expect(response.status).toBe(503);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("repete uma mutação idempotente preservando a mesma chave", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));
    await requestWithPolicy(
      "https://rotas.test/resource",
      { method: "POST", headers: { "Idempotency-Key": "operation-123" }, body: "{}" },
      { fetch: fetchMock, sleep: vi.fn() },
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const call of fetchMock.mock.calls) {
      expect(new Headers(call[1]?.headers).get("Idempotency-Key")).toBe("operation-123");
    }
  });

  it("converte timeout num erro tipado e repetível", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation((_input, init) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
    );
    await expect(requestWithPolicy(
      "https://rotas.test/slow",
      {},
      { fetch: fetchMock, timeoutMs: 1, maxRetries: 0 },
    )).rejects.toMatchObject({ code: "request_timeout", status: 0, retryable: true });
  });

  it("preserva o envelope ROTAS num erro tipado", async () => {
    const error = await responseToHttpError(new Response(JSON.stringify({
      error: { code: "stock_conflict", message: "Stock insuficiente.", details: { available: 2 } },
    }), { status: 409, headers: { "Content-Type": "application/json" } }));
    expect(error).toBeInstanceOf(HttpContractError);
    expect(error).toMatchObject({
      status: 409,
      code: "stock_conflict",
      message: "Stock insuficiente.",
      details: { available: 2 },
      retryable: false,
    });
  });
});

describe("Manager BFF", () => {
  it("atribui idempotência automática às mutações", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    const response = await bffRequest("/api/v1/trips", {
      method: "POST",
      body: JSON.stringify({ origin: "Maputo" }),
      policy: { fetch: fetchMock, maxRetries: 0 },
    });
    expect(response.status).toBe(204);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toContain(encodeURIComponent("/api/v1/trips"));
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(init?.credentials).toBe("include");
  });
});
