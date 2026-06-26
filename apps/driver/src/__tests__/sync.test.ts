import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi, type Mock } from "vitest";
import { db, queueOperation, queueFuelLog } from "../db";
import { processSyncQueue } from "../sync";

describe("Driver Offline-First & Sync Queue", () => {
  beforeEach(async () => {
    // Clear all IndexedDB tables before each test
    await db.syncQueue.clear();
    await db.photoQueue.clear();
    await db.pendingFuelLogs.clear();
    
    // Reset global fetch and localStorage mocks
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("rotas_tenant_id", "00000000-0000-0000-0000-000000000001");
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
    expect(options.headers["Authorization"]).toBe("Bearer token-xyz");
    expect(options.headers["X-Tenant-Id"]).toBe("00000000-0000-0000-0000-000000000001");
    
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
});
