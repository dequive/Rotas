import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuth } from "../api";
import {
  db,
  getBootstrapCache,
  queueOperation,
  saveBootstrapCache,
} from "../db";
import { purgeDriverIdentity } from "../identity";
import { processSyncQueue } from "../sync";

const currentScope = {
  tenantId: "tenant-current",
  driverId: "driver-current",
  sessionId: "session-current",
};

beforeEach(async () => {
  await Promise.all(db.tables.map((table) => table.clear()));
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.setItem("rotas_access_token", "access-current");
  localStorage.setItem("rotas_refresh_token", "refresh-current");
  localStorage.setItem("rotas_tenant_id", currentScope.tenantId);
  localStorage.setItem("rotas_driver_id", currentScope.driverId);
  localStorage.setItem("rotas_device_id", "device-current");
  localStorage.setItem("rotas_driver_name", "Motorista Actual");
  localStorage.setItem("rotas_session_id", currentScope.sessionId);
});

describe("isolamento da identidade offline", () => {
  it("não lê snapshot de outra sessão do mesmo tenant e motorista", async () => {
    await saveBootstrapCache(
      currentScope.tenantId,
      currentScope.driverId,
      "session-old",
      { activeTrip: { id: "trip-old" } },
    );

    expect(
      await getBootstrapCache(
        currentScope.tenantId,
        currentScope.driverId,
        currentScope.sessionId,
      ),
    ).toBeUndefined();
  });

  it("sincroniza apenas operações da identidade corrente", async () => {
    await db.syncQueue.add({
      tenantId: "tenant-old",
      driverId: "driver-old",
      sessionId: "session-old",
      localId: "trip-old",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-old" },
      retryCount: 0,
      status: "local_only",
      createdAt: new Date().toISOString(),
    });
    await queueOperation({
      localId: "trip-current",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-current" },
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          results: [
            {
              local_id: "trip-current",
              status: "processed",
              entity_type: "trip",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await processSyncQueue("access-current");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      await db.syncQueue.where("localId").equals("trip-current").first(),
    ).toBeUndefined();
    expect(
      await db.syncQueue.where("localId").equals("trip-old").first(),
    ).toBeDefined();
  });

  it("logout revoga credenciais e limpa dados/caches autenticados", async () => {
    await queueOperation({
      localId: "trip-sensitive",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-sensitive" },
    });
    await saveBootstrapCache(
      currentScope.tenantId,
      currentScope.driverId,
      currentScope.sessionId,
      { activeTrip: { id: "trip-sensitive" } },
    );
    const deleteCache = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", { delete: deleteCache });

    await purgeDriverIdentity();

    expect(getAuth()).toBeNull();
    expect(localStorage.getItem("rotas_refresh_token")).toBeNull();
    expect(await db.syncQueue.count()).toBe(0);
    expect(await db.bootstrapCache.count()).toBe(0);
    await Promise.all(
      db.tables.map(async (table) => {
        expect(await table.count()).toBe(0);
      }),
    );
    expect(deleteCache).toHaveBeenCalledWith("api-cache");
    expect(deleteCache).toHaveBeenCalledWith("sync-api");
    expect(deleteCache).not.toHaveBeenCalledWith("static-assets");
  });
});
