import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi, type Mock } from "vitest";
import {
  db,
  getBootstrapCache,
  queueOperation,
  queueFuelLog,
  requeueSyncItem,
  saveBootstrapCache,
} from "../db";
import { computeSyncBackoffMs, processSyncQueue } from "../sync";

const identityScope = {
  tenantId: "00000000-0000-0000-0000-000000000001",
  driverId: "driver-test",
  sessionId: "session-test",
};

describe("Driver Offline-First & Sync Queue", () => {
  beforeEach(async () => {
    // Clear all IndexedDB tables before each test
    await db.syncQueue.clear();
    await db.photoQueue.clear();
    await db.pendingFuelLogs.clear();
    await db.bootstrapCache.clear();
    
    // Reset global fetch and localStorage mocks
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("rotas_tenant_id", identityScope.tenantId);
    localStorage.setItem("rotas_driver_id", identityScope.driverId);
    localStorage.setItem("rotas_session_id", identityScope.sessionId);
    localStorage.setItem("rotas_device_id", "device-123");
  });

  it("stores generic operation offline in syncQueue", async () => {
    await queueOperation({
      localId: "trip_123",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_123", destination: "Beira" }
    });

    const count = await db.syncQueue.count();
    expect(count).toBe(1);

    const items = await db.syncQueue.toArray();
    expect(items[0].localId).toBe("trip_123");
    expect(items[0].status).toBe("local_only");
    expect(items[0].entityType).toBe("trip");
    expect(items[0].payload.destination).toBe("Beira");
  });

  it("stores fuel registration in pendingFuelLogs and syncQueue in a single transaction", async () => {
    await queueFuelLog({
      localId: "fuel_123",
      vehicleId: "vehicle_abc",
      driverId: "driver_xyz",
      fuelType: "diesel",
      liters: 50.5,
      totalCost: 3500.0,
      kmAtRefuel: 120500,
      stationName: "Petromoc",
      paymentMethod: "cash"
    });

    // Verify it is added to pendingFuelLogs
    const fuelLogsCount = await db.pendingFuelLogs.count();
    expect(fuelLogsCount).toBe(1);
    const fuelLog = await db.pendingFuelLogs.where("localId").equals("fuel_123").first();
    expect(fuelLog).toBeDefined();
    expect(fuelLog?.status).toBe("local_only");
    expect(fuelLog?.liters).toBe(50.5);

    // Verify it is added to syncQueue
    const syncCount = await db.syncQueue.count();
    expect(syncCount).toBe(1);
    const syncItem = await db.syncQueue.where("localId").equals("fuel_123").first();
    expect(syncItem).toBeDefined();
    expect(syncItem?.entityType).toBe("fuel_log");
    expect(syncItem?.payload.liters).toBe(50.5);
  });

  it("successfully synchronizes items in syncQueue to the server", async () => {
    // Seed an item in syncQueue
    await queueOperation({
      localId: "trip_123",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_123" }
    });

    // Mock fetch for batch sync endpoint
    const mockResponse = {
      results: [
        {
          local_id: "trip_123",
          status: "processed",
          entity_type: "trip"
        }
      ]
    };

    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })
    );
    global.fetch = fetchMock as unknown as typeof global.fetch;

    await processSyncQueue("token-xyz");

    // After successful sync, the item should be removed from syncQueue
    const syncCount = await db.syncQueue.count();
    expect(syncCount).toBe(0);

    // Verify fetch was called with correct headers and payload
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/sync/batch");
    expect(options.method).toBe("POST");
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-xyz");
    expect(headers.get("X-Tenant-Id")).toBe("00000000-0000-0000-0000-000000000001");
    
    const body = JSON.parse(options.body);
    expect(body.device_id).toBe("device-123");
    expect(body.operations[0].local_id).toBe("trip_123");
  });

  it("handles server conflicts by marking item status as conflict", async () => {
    await queueOperation({
      localId: "trip_123",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_123" }
    });

    const mockResponse = {
      results: [
        {
          local_id: "trip_123",
          status: "conflict",
          entity_type: "trip",
          error_code: "resource_conflict",
          message: "Conflict detected"
        }
      ]
    };

    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      })
    ) as unknown as typeof global.fetch;

    await processSyncQueue("token-xyz");

    // Item should remain in queue but with conflict status
    const syncCount = await db.syncQueue.count();
    expect(syncCount).toBe(1);
    const item = await db.syncQueue.where("localId").equals("trip_123").first();
    expect(item?.status).toBe("conflict");
    expect(item?.lastError).toBe("Conflict detected");
  });

  it("persiste backoff e não tenta novamente antes de nextAttemptAt", async () => {
    const now = new Date("2026-07-26T10:00:00.000Z");
    await queueOperation({
      localId: "trip_backoff",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_backoff" },
    });
    global.fetch = vi.fn().mockRejectedValue(
      new Error("offline"),
    ) as unknown as typeof fetch;

    await processSyncQueue("token-xyz", {
      now: () => now,
      random: () => 0,
    });

    const item = await db.syncQueue
      .where("localId")
      .equals("trip_backoff")
      .first();
    expect(item?.status).toBe("retrying");
    expect(item?.retryCount).toBe(1);
    expect(item?.nextAttemptAt).toBe("2026-07-26T10:00:00.500Z");

    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;
    await processSyncQueue("token-xyz", {
      now: () => new Date("2026-07-26T10:00:00.499Z"),
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("recupera item preso em syncing depois de encerramento abrupto", async () => {
    await db.syncQueue.add({
      ...identityScope,
      localId: "trip_interrupted",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_interrupted" },
      retryCount: 0,
      status: "syncing",
      createdAt: "2026-07-26T09:00:00.000Z",
    });
    global.fetch = vi.fn().mockRejectedValue(
      new Error("still_offline"),
    ) as unknown as typeof fetch;

    await processSyncQueue("token-xyz", {
      now: () => new Date("2026-07-26T10:00:00.000Z"),
      random: () => 0,
    });

    const item = await db.syncQueue
      .where("localId")
      .equals("trip_interrupted")
      .first();
    expect(item?.status).toBe("retrying");
    expect(item?.retryCount).toBe(1);
    expect(item?.lastAttemptAt).toBe("2026-07-26T10:00:00.000Z");
  });

  it("requeue explícito gera nova chave após resolução de conflito", async () => {
    await queueOperation({
      localId: "trip_conflict_requeue",
      operation: "create",
      entityType: "trip",
      payload: { destination: "Old" },
    });
    const original = await db.syncQueue
      .where("localId")
      .equals("trip_conflict_requeue")
      .first();
    await db.syncQueue.update(original!.id!, {
      status: "conflict",
      lastError: "resource_conflict",
    });

    await requeueSyncItem(original!.id!, { destination: "Corrected" });

    const requeued = await db.syncQueue.get(original!.id!);
    expect(requeued?.status).toBe("retrying");
    expect(requeued?.retryCount).toBe(0);
    expect(requeued?.payload).toEqual({ destination: "Corrected" });
    expect(requeued?.idempotencyKey).not.toBe(original?.idempotencyKey);
    expect(requeued?.nextAttemptAt).toBeTruthy();
  });

  it("calcula backoff exponencial limitado com jitter determinístico", () => {
    expect(computeSyncBackoffMs(1, () => 0)).toBe(500);
    expect(computeSyncBackoffMs(2, () => 0)).toBe(1_000);
    expect(computeSyncBackoffMs(20, () => 1)).toBe(300_000);
  });

  it("renova uma sessão expirada e reutiliza o token no mesmo lote", async () => {
    localStorage.setItem("rotas_access_token", "access-old");
    localStorage.setItem("rotas_refresh_token", "refresh-old");
    await queueOperation({
      localId: "trip_refresh",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_refresh" },
    });
    const fetchMock = vi.fn().mockImplementation((
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => {
      const url = String(input);
      if (url.includes("/auth/refresh")) {
        return Promise.resolve(Response.json({
          access_token: "access-new",
          refresh_token: "refresh-new",
        }));
      }
      const authorization = new Headers(init?.headers).get("Authorization");
      return Promise.resolve(
        authorization === "Bearer access-old"
          ? new Response(null, { status: 401 })
          : Response.json({
              results: [{
                local_id: "trip_refresh",
                status: "processed",
                entity_type: "trip",
              }],
            }),
      );
    });
    global.fetch = fetchMock as typeof fetch;

    await processSyncQueue("access-old");

    expect(await db.syncQueue.count()).toBe(0);
    expect(localStorage.getItem("rotas_access_token")).toBe("access-new");
    expect(localStorage.getItem("rotas_refresh_token")).toBe("refresh-new");
    const batchRequests = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("/sync/batch"),
    );
    expect(batchRequests).toHaveLength(2);
    expect(
      new Headers(batchRequests[1]?.[1]?.headers).get("Authorization"),
    ).toBe("Bearer access-new");

    await queueOperation({
      localId: "trip_after_refresh",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_after_refresh" },
    });
    fetchMock.mockClear();
    await processSyncQueue("access-old");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Authorization"),
    ).toBe("Bearer access-new");
  });

  it("não consome tentativas quando a sessão expirou sem refresh token", async () => {
    await queueOperation({
      localId: "trip_session_expired",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_session_expired" },
    });
    global.fetch = vi.fn().mockResolvedValue(
      new Response(null, { status: 401 }),
    ) as unknown as typeof fetch;

    await processSyncQueue("access-expired", {
      now: () => new Date("2026-07-26T10:00:00.000Z"),
    });

    const item = await db.syncQueue
      .where("localId")
      .equals("trip_session_expired")
      .first();
    expect(item?.status).toBe("retrying");
    expect(item?.retryCount).toBe(0);
    expect(item?.lastError).toBe("session_expired");
    expect(item?.nextAttemptAt).toBe("2026-07-26T10:05:00.000Z");
  });

  it("acesso revogado preserva o item como falha terminal visível", async () => {
    await queueOperation({
      localId: "trip_revoked",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip_revoked" },
    });
    const revokedEvent = vi.fn();
    window.addEventListener("driver-access-revoked", revokedEvent, { once: true });
    global.fetch = vi.fn().mockResolvedValue(
      Response.json(
        {
          error: {
            code: "driver_access_revoked",
            message: "Acesso do motorista revogado.",
          },
        },
        { status: 401 },
      ),
    ) as unknown as typeof fetch;

    await processSyncQueue("access-revoked");

    const item = await db.syncQueue
      .where("localId")
      .equals("trip_revoked")
      .first();
    expect(item?.status).toBe("failed");
    expect(item?.retryCount).toBe(0);
    expect(item?.lastError).toBe("driver_access_revoked");
    expect(item?.nextAttemptAt).toBeUndefined();
    expect(revokedEvent).toHaveBeenCalledTimes(1);
  });

  it("cache bootstrap só é recuperado para o mesmo tenant e motorista", async () => {
    const snapshot = { activeTrip: { id: "trip-cached" } };
    await saveBootstrapCache("tenant-a", "driver-a", "session-a", snapshot);

    expect(
      (await getBootstrapCache<typeof snapshot>("tenant-a", "driver-a", "session-a"))?.data,
    ).toEqual(snapshot);
    expect(
      await getBootstrapCache("tenant-a", "driver-b", "session-a"),
    ).toBeUndefined();
    expect(
      await getBootstrapCache("tenant-b", "driver-a", "session-a"),
    ).toBeUndefined();
  });
});
