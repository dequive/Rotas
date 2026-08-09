import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearAuth, getAuth, refreshDriverAccessToken } from "../api";
import {
  db,
  discardSyncItem,
  getBootstrapCache,
  queueOperation,
  requeueSyncItem,
  saveBootstrapCache,
  type SyncQueueItem,
} from "../db";
import { purgeDriverIdentity } from "../identity";
import { processSyncQueue } from "../sync";

const currentScope = {
  tenantId: "tenant-current",
  driverId: "driver-current",
  sessionId: "session-current",
};

const foreignScope = {
  tenantId: "tenant-current",
  driverId: "driver-current",
  sessionId: "session-old",
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
      foreignScope.sessionId,
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

  it("sincroniza só a identidade corrente e mantém dados estrangeiros ou legados em quarentena", async () => {
    await db.syncQueue.add({
      ...foreignScope,
      localId: "trip-old",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-old" },
      retryCount: 0,
      status: "local_only",
      createdAt: new Date().toISOString(),
    });
    await db.syncQueue.add({
      localId: "trip-legacy",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-legacy" },
      retryCount: 0,
      status: "local_only",
      createdAt: new Date().toISOString(),
    } as unknown as SyncQueueItem);
    await queueOperation({
      localId: "trip-current",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-current" },
    });

    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        results: [{
          local_id: "trip-current",
          status: "processed",
          entity_type: "trip",
        }],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await processSyncQueue("access-current");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(await db.syncQueue.where("localId").equals("trip-current").first()).toBeUndefined();
    expect(await db.syncQueue.where("localId").equals("trip-old").first()).toBeDefined();
    expect(await db.syncQueue.where("localId").equals("trip-legacy").first()).toBeDefined();
  });

  it("nega gestão cruzada e descarta apenas evidências da sessão corrente", async () => {
    const foreignId = await db.syncQueue.add({
      ...foreignScope,
      localId: "shared-local-id",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "fuel_log",
      payload: {},
      retryCount: 5,
      status: "dead_letter",
      createdAt: new Date().toISOString(),
    });
    const currentId = await db.syncQueue.add({
      ...currentScope,
      localId: "shared-local-id",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "fuel_log",
      payload: {},
      retryCount: 5,
      status: "dead_letter",
      createdAt: new Date().toISOString(),
    });
    for (const scope of [foreignScope, currentScope]) {
      await db.photoQueue.add({
        ...scope,
        localId: `photo-${scope.sessionId}`,
        entityType: "fuel_log",
        entityLocalId: "shared-local-id",
        blob: new Blob([scope.sessionId]),
        fileType: "receipt",
        retryCount: 5,
        status: "dead_letter",
        createdAt: new Date().toISOString(),
      });
    }

    await expect(requeueSyncItem(foreignId)).rejects.toThrow("sync_item_not_requeueable");
    await expect(discardSyncItem(foreignId)).rejects.toThrow("sync_item_not_discardable");
    await discardSyncItem(currentId);

    expect(await db.syncQueue.get(foreignId)).toBeDefined();
    expect(await db.photoQueue.filter((photo) => photo.sessionId === foreignScope.sessionId).count()).toBe(1);
    expect(await db.photoQueue.filter((photo) => photo.sessionId === currentScope.sessionId).count()).toBe(0);
  });

  it("logout limpa dados e impede refresh em voo de ressuscitar credenciais", async () => {
    await queueOperation({
      localId: "trip-sensitive",
      operation: "create",
      entityType: "trip",
      payload: { id: "trip-sensitive" },
    });
    let resolveRefresh!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    })));
    const refresh = refreshDriverAccessToken();
    const deleteCache = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", { delete: deleteCache });

    const purge = purgeDriverIdentity();
    resolveRefresh(Response.json({ access_token: "resurrected", refresh_token: "rotated" }));
    await expect(refresh).resolves.toBeNull();
    await purge;

    expect(getAuth()).toBeNull();
    expect(localStorage.getItem("rotas_access_token")).toBeNull();
    expect(localStorage.getItem("rotas_refresh_token")).toBeNull();
    expect(await db.syncQueue.count()).toBe(0);
    expect(deleteCache).toHaveBeenCalledWith("api-cache");
    expect(deleteCache).toHaveBeenCalledWith("sync-api");
    expect(deleteCache).not.toHaveBeenCalledWith("static-assets");
  });

  it("mantém credenciais revogadas quando a confirmação do service worker falha", async () => {
    vi.stubGlobal("navigator", {
      serviceWorker: {
        controller: null,
        ready: Promise.resolve({ active: null, waiting: null, installing: null }),
      },
    });
    vi.stubGlobal("caches", { delete: vi.fn().mockResolvedValue(true) });

    await expect(purgeDriverIdentity()).rejects.toThrow(
      "service_worker_unavailable_for_identity_purge",
    );

    expect(getAuth()).toBeNull();
    expect(localStorage.getItem("rotas_refresh_token")).toBeNull();
  });

  it("refresh antigo não liberta o lock pertencente à nova sessão", async () => {
    const resolvers: Array<(response: Response) => void> = [];
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => {
      resolvers.push(resolve);
    }));
    vi.stubGlobal("fetch", fetchMock);

    const oldRefresh = refreshDriverAccessToken();
    clearAuth();
    localStorage.setItem("rotas_access_token", "access-new-session");
    localStorage.setItem("rotas_refresh_token", "refresh-new-session");
    localStorage.setItem("rotas_tenant_id", "tenant-new");
    localStorage.setItem("rotas_driver_id", "driver-new");
    localStorage.setItem("rotas_device_id", "device-new");
    localStorage.setItem("rotas_session_id", "session-new");

    const newRefresh = refreshDriverAccessToken();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    resolvers[0]!(Response.json({ access_token: "stale-access" }));
    await expect(oldRefresh).resolves.toBeNull();

    const concurrentRefresh = refreshDriverAccessToken();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    resolvers[1]!(Response.json({
      access_token: "access-new",
      refresh_token: "refresh-new",
    }));

    await expect(newRefresh).resolves.toBe("access-new");
    await expect(concurrentRefresh).resolves.toBe("access-new");
    expect(localStorage.getItem("rotas_access_token")).toBe("access-new");
  });
});
