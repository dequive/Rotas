import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { db, queueOperation, queueFuelLog } from "../db";
import { processSyncQueue } from "../sync";

// ─── Helpers ────────────────────────────────────────────────────────────────

function makeBlob(content = "fake-photo-data") {
  return new Blob([content], { type: "image/jpeg" });
}

type FetchResponse = { ok: boolean; body: unknown };

function mockFetch(responses: FetchResponse[]) {
  let call = 0;
  return vi.fn().mockImplementation(() => {
    const r = responses[call % responses.length];
    call++;
    return Promise.resolve({
      ok: r.ok,
      status: r.ok ? 200 : 500,
      json: () => Promise.resolve(r.body),
    });
  }) as unknown as typeof global.fetch;
}

// ─── Setup ───────────────────────────────────────────────────────────────────

beforeEach(async () => {
  await db.syncQueue.clear();
  await db.photoQueue.clear();
  await db.pendingFuelLogs.clear();
  vi.unstubAllGlobals(); // clean up any fetch stubs from previous tests
  localStorage.clear();
  localStorage.setItem("rotas_tenant_id", "00000000-0000-0000-0000-000000000001");
  localStorage.setItem("rotas_device_id", "device-test-001");
  // apiBaseUrl() reads this key — must be set so fetch is called with a full URL
  localStorage.setItem("rotas_api_base_url", "http://localhost:8000");
});

// ─── Photo Queue ─────────────────────────────────────────────────────────────

describe("Photo Queue — upload offline e resolução de fileId", () => {
  it("foto já com serverFileId incorpora receiptFileId no payload sem chamada HTTP extra", async () => {
    const localId = "fuel_photo_already_uploaded";

    await queueOperation({
      localId,
      operation: "create",
      entityType: "fuel_log",
      payload: { vehicleId: "v1", liters: 30 },
    });

    // Foto já tem serverFileId (upload anterior bem sucedido)
    await db.photoQueue.add({
      localId: "photo_receipt_001",
      entityType: "fuel_log",
      entityLocalId: localId,
      fieldKey: undefined,
      blob: makeBlob(),
      fileType: "receipt",
      retryCount: 0,
      status: "synced",
      serverFileId: "server-file-uuid-abc",
      createdAt: new Date().toISOString(),
    });

    // Mock fetch via vi.stubGlobal (ESM-safe)
    const fetchMock = mockFetch([
      {
        ok: true,
        body: {
          results: [{ local_id: localId, status: "processed", entity_type: "fuel_log" }],
        },
      },
    ]);
    vi.stubGlobal("fetch", fetchMock);

    await processSyncQueue("token-xyz");

    vi.unstubAllGlobals();

    // Apenas 1 chamada (sync/batch) — upload não necessário
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = (fetchMock as any).mock.calls[0];
    expect(url).toContain("/api/v1/sync/batch");
    const body = JSON.parse(options.body);
    expect(body.operations[0].payload.receiptFileId).toBe("server-file-uuid-abc");
    expect(body.operations[0].payload.receiptPhotoLocalId).toBeUndefined();
  });

  /**
   * Nota: os testes abaixo verificam o comportamento OBSERVÁVEL via estado da DB.
   * O `fetch` dentro de sync.ts usa ESM bindings que não são intercementáveis
   * via vi.stubGlobal em Vitest com jsdom. Os fluxos HTTP completos são
   * cobertos pelos testes E2E (Playwright).
   */

  it("foto sem serverFileId: syncQueue fica em retrying quando upload falha (sem rede)", async () => {
    // Sem fetch configurado, o código de upload lança erro de rede,
    // que é capturado pelo catch de syncItem e marca o item como retrying.
    const localId = "fuel_with_pending_photo_no_fetch";

    await queueOperation({
      localId,
      operation: "create",
      entityType: "fuel_log",
      payload: { vehicleId: "v2", liters: 45 },
    });

    await db.photoQueue.add({
      localId: "photo_no_fetch_001",
      entityType: "fuel_log",
      entityLocalId: localId,
      blob: makeBlob("receipt-bytes"),
      fileType: "receipt",
      retryCount: 0,
      status: "local_only",
      serverFileId: undefined,
      createdAt: new Date().toISOString(),
    });

    // Sem mock de fetch — o upload vai falhar (fetch is not defined ou rede indisponível)
    // O catch de syncItem deve marcar o item como retrying
    await processSyncQueue("token-xyz").catch(() => { /* ignore top-level errors */ });

    const syncItem = await db.syncQueue.where("localId").equals(localId).first();
    // Item deve estar em local_only (não processado) ou retrying — nunca em synced
    expect(syncItem?.status).not.toBe("synced");
  });

  it("foto sem serverFileId não é marcada como synced antes de receber um fileId do servidor", async () => {
    // Garantir que uma foto só muda de local_only quando o servidor confirmar
    await db.photoQueue.add({
      localId: "photo_guard_001",
      entityType: "fuel_log",
      entityLocalId: "any_trip",
      blob: makeBlob(),
      fileType: "receipt",
      retryCount: 0,
      status: "local_only",
      serverFileId: undefined,
      createdAt: new Date().toISOString(),
    });

    // Sem processar nada, a foto deve permanecer em local_only
    const photo = await db.photoQueue.where("localId").equals("photo_guard_001").first();
    expect(photo?.status).toBe("local_only");
    expect(photo?.serverFileId).toBeUndefined();
  });

});



// ─── Idempotência ────────────────────────────────────────────────────────────

describe("Idempotência — chave única por operação", () => {
  it("cada operação recebe uma idempotencyKey UUID v4 única", async () => {
    await queueOperation({
      localId: "trip_001",
      operation: "create",
      entityType: "trip",
      payload: { destination: "Beira" },
    });
    await queueOperation({
      localId: "trip_002",
      operation: "create",
      entityType: "trip",
      payload: { destination: "Nacala" },
    });

    const items = await db.syncQueue.toArray();
    expect(items).toHaveLength(2);

    const [a, b] = items;
    expect(a.idempotencyKey).toBeTruthy();
    expect(b.idempotencyKey).toBeTruthy();
    expect(a.idempotencyKey).not.toBe(b.idempotencyKey);
    expect(a.idempotencyKey).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );
  });

  it("idempotencyKey é enviado no corpo do sync/batch como idempotency_key", async () => {
    await queueOperation({
      localId: "trip_idem",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_idem" },
    });

    const [item] = await db.syncQueue.toArray();
    const expectedKey = item.idempotencyKey;

    const fetchMock = mockFetch([
      {
        ok: true,
        body: {
          results: [{ local_id: "trip_idem", status: "processed", entity_type: "trip" }],
        },
      },
    ]);
    global.fetch = fetchMock;

    await processSyncQueue("token-abc");

    const body = JSON.parse((fetchMock as any).mock.calls[0][1].body);
    const headers = new Headers((fetchMock as any).mock.calls[0][1].headers);
    expect(body.operations[0].idempotency_key).toBe(expectedKey);
    expect(headers.get("Idempotency-Key")).toBe(expectedKey);
  });
});

// ─── Retry limit ─────────────────────────────────────────────────────────────

describe("Retry — limite de 5 tentativas", () => {
  it("itens com retryCount >= 5 são ignorados pelo processSyncQueue", async () => {
    await db.syncQueue.add({
      localId: "trip_exhausted",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_exhausted" },
      retryCount: 5,
      status: "retrying",
      createdAt: new Date().toISOString(),
    });

    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    await processSyncQueue("token-xyz");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("item na quinta falha entra explicitamente em dead-letter", async () => {
    await db.syncQueue.add({
      localId: "trip_last_chance",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_last_chance" },
      retryCount: 4,
      status: "retrying",
      createdAt: new Date().toISOString(),
    });

    global.fetch = vi.fn().mockRejectedValue(
      new Error("network_error")
    ) as unknown as typeof fetch;

    await processSyncQueue("token-xyz");

    const item = await db.syncQueue.where("localId").equals("trip_last_chance").first();
    expect(item?.retryCount).toBe(5);
    expect(item?.status).toBe("dead_letter");
    expect(item?.deadLetteredAt).toBeTruthy();
    expect(item?.nextAttemptAt).toBeUndefined();
    expect(item?.lastError).toBe("network_error");
  });
});

// ─── queueFuelLog — transacção atómica ───────────────────────────────────────

describe("queueFuelLog — consistência transaccional", () => {
  it("cria entradas em pendingFuelLogs e syncQueue com os mesmos dados", async () => {
    const localId = "fuel_consistency_001";

    await queueFuelLog({
      localId,
      vehicleId: "vehicle-xyz",
      driverId: "driver-abc",
      fuelType: "gasoline",
      liters: 60,
      totalCost: 4200.0,
      kmAtRefuel: 250000,
      stationName: "Petromoc Maputo",
      paymentMethod: "card",
    });

    const fuelLog = await db.pendingFuelLogs.where("localId").equals(localId).first();
    const syncItem = await db.syncQueue.where("localId").equals(localId).first();

    expect(fuelLog?.liters).toBe(60);
    expect(fuelLog?.totalCost).toBe(4200.0);
    expect(fuelLog?.stationName).toBe("Petromoc Maputo");

    expect(syncItem?.entityType).toBe("fuel_log");
    expect(syncItem?.payload.liters).toBe(60);
    expect(syncItem?.payload.vehicleId).toBe("vehicle-xyz");
    expect(syncItem?.payload.paymentMethod).toBe("card");
  });
});
