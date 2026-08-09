import Dexie, { type Table } from "dexie";

export type SyncStatus =
  | "local_only"
  | "syncing"
  | "synced"
  | "retrying"
  | "conflict"
  | "failed"
  | "dead_letter";

export interface SyncQueueItem {
  id?: number;
  localId: string;
  idempotencyKey: string;
  operation: "create" | "update";
  entityType:
    | "checklist"
    | "fuel_log"
    | "trip"
    | "trip_stop"
    | "load_permit"
    | "cargo_manifest"
    | "transport_document"
    | "delivery_proof"
    | "trip_cost";
  payload: Record<string, unknown>;
  retryCount: number;
  status: SyncStatus;
  lastError?: string;
  lastAttemptAt?: string;
  nextAttemptAt?: string;
  deadLetteredAt?: string;
  createdAt: string;
}

export interface PhotoQueueItem {
  id?: number;
  localId: string;
  entityType: SyncQueueItem["entityType"];
  entityLocalId: string;
  fieldKey?: string;
  blob: Blob;
  fileType: "photo" | "document" | "signature" | "receipt";
  retryCount: number;
  status: SyncStatus;
  serverFileId?: string;
  lastAttemptAt?: string;
  nextAttemptAt?: string;
  deadLetteredAt?: string;
  createdAt: string;
}

export interface PendingFuelLogItem {
  id?: number;
  localId: string;
  vehicleId: string;
  driverId: string;
  stationName?: string;
  fuelType: string;
  liters: number;
  totalCost: number;
  kmAtRefuel: number;
  paymentMethod?: string;
  receiptPhotoLocalId?: string;
  odometerPhotoLocalId?: string;
  status: SyncStatus;
  createdAt: string;
}

export interface LoadPermitItem {
  id?: number;
  localId: string;
  tripLocalId: string;
  permitNumber: string;
  status: SyncStatus;
}

export interface CargoManifestItem {
  id?: number;
  localId: string;
  tripLocalId: string;
  manifestNumber: string;
  status: SyncStatus;
}

export interface DeliveryProofItem {
  id?: number;
  localId: string;
  tripLocalId: string;
  deliveredAt: string;
  status: SyncStatus;
}

export interface BootstrapCacheItem<T = unknown> {
  id: string;
  tenantId: string;
  driverId: string;
  data: T;
  cachedAt: string;
}

class RotasDriverDb extends Dexie {
  syncQueue!: Table<SyncQueueItem, number>;
  photoQueue!: Table<PhotoQueueItem, number>;
  pendingFuelLogs!: Table<PendingFuelLogItem, number>;
  loadPermits!: Table<LoadPermitItem, number>;
  cargoManifests!: Table<CargoManifestItem, number>;
  deliveryProofs!: Table<DeliveryProofItem, number>;
  bootstrapCache!: Table<BootstrapCacheItem, string>;

  constructor() {
    super("RotasMotoristaDB");
    this.version(1).stores({
      driverProfile: "id, name, phone, lastSync",
      vehicles: "id, plate, brand, model, currentKm, lastSync",
      checklistTemplates: "id, type, category, lastSync",
      pendingChecklists: "++id, localId, serverId, vehicleId, type, status, createdAt",
      checklistResponses: "++id, checklistLocalId, itemId, timestamp",
      activeTrip: "id, tripId, vehicleId, startedAt, status",
      tripStops: "++id, tripLocalId, type, timestamp, synced",
      loadPermits: "++id, tripLocalId, permitNumber, status",
      cargoManifests: "++id, tripLocalId, manifestNumber, status",
      transportDocuments: "++id, tripLocalId, documentType, status",
      deliveryProofs: "++id, tripLocalId, deliveredAt, status",
      tripCosts: "++id, tripLocalId, costType, status",
      pendingFuelLogs: "++id, localId, vehicleId, timestamp, status",
      photoQueue: "++id, localId, entityType, entityLocalId, status, serverFileId, createdAt",
      syncQueue: "++id, localId, idempotencyKey, entityType, status, createdAt",
      destinations: "id, name, frequency, lastSync"
    });
    this.version(2).stores({
      photoQueue:
        "++id, localId, entityType, entityLocalId, status, serverFileId, nextAttemptAt, createdAt",
      syncQueue:
        "++id, localId, idempotencyKey, entityType, status, nextAttemptAt, createdAt"
    });
    this.version(3).stores({
      bootstrapCache: "id, tenantId, driverId, cachedAt"
    });
  }
}

export const db = new RotasDriverDb();

export function makeLocalId(prefix: string) {
  return `${prefix}_${crypto.randomUUID()}`;
}

export async function requeueSyncItem(
  id: number,
  payload?: Record<string, unknown>,
): Promise<void> {
  const item = await db.syncQueue.get(id);
  if (
    !item ||
    !["conflict", "failed", "dead_letter"].includes(item.status)
  ) {
    throw new Error("sync_item_not_requeueable");
  }
  await db.syncQueue.update(id, {
    ...(payload ? { payload } : {}),
    idempotencyKey: crypto.randomUUID(),
    retryCount: 0,
    status: "retrying",
    lastError: undefined,
    lastAttemptAt: undefined,
    nextAttemptAt: new Date().toISOString(),
    deadLetteredAt: undefined,
  });
}

export async function discardSyncItem(id: number): Promise<void> {
  const item = await db.syncQueue.get(id);
  if (
    !item ||
    !["conflict", "failed", "dead_letter"].includes(item.status)
  ) {
    throw new Error("sync_item_not_discardable");
  }
  await db.transaction(
    "rw",
    db.syncQueue,
    db.photoQueue,
    db.pendingFuelLogs,
    async () => {
      await db.photoQueue
        .where("entityLocalId")
        .equals(item.localId)
        .delete();
      if (item.entityType === "fuel_log") {
        await db.pendingFuelLogs
          .where("localId")
          .equals(item.localId)
          .delete();
      }
      await db.syncQueue.delete(id);
    },
  );
}

function bootstrapCacheId(tenantId: string, driverId: string): string {
  return `${tenantId}:${driverId}`;
}

export async function saveBootstrapCache<T>(
  tenantId: string,
  driverId: string,
  data: T,
): Promise<void> {
  await db.bootstrapCache.put({
    id: bootstrapCacheId(tenantId, driverId),
    tenantId,
    driverId,
    data,
    cachedAt: new Date().toISOString(),
  });
}

export async function getBootstrapCache<T>(
  tenantId: string,
  driverId: string,
): Promise<BootstrapCacheItem<T> | undefined> {
  return db.bootstrapCache.get(
    bootstrapCacheId(tenantId, driverId),
  ) as Promise<BootstrapCacheItem<T> | undefined>;
}

export async function queueOperation(
  item: Omit<SyncQueueItem, "idempotencyKey" | "retryCount" | "status" | "createdAt">
) {
  await db.syncQueue.add({
    ...item,
    idempotencyKey: crypto.randomUUID(),
    retryCount: 0,
    status: "local_only",
    createdAt: new Date().toISOString()
  });
}

export async function queueFuelLog(
  item: Omit<PendingFuelLogItem, "id" | "status" | "createdAt">
) {
  const createdAt = new Date().toISOString();
  await db.transaction("rw", db.pendingFuelLogs, db.syncQueue, async () => {
    await db.pendingFuelLogs.add({
      ...item,
      status: "local_only",
      createdAt
    });
    await queueOperation({
      localId: item.localId,
      operation: "create",
      entityType: "fuel_log",
      payload: {
        vehicleId: item.vehicleId,
        driverId: item.driverId,
        fuelDate: createdAt,
        stationName: item.stationName,
        fuelType: item.fuelType,
        liters: item.liters,
        totalCost: item.totalCost,
        kmAtRefuel: item.kmAtRefuel,
        paymentMethod: item.paymentMethod,
        receiptPhotoLocalId: item.receiptPhotoLocalId,
        odometerPhotoLocalId: item.odometerPhotoLocalId,
        clientCapturedAt: createdAt
      }
    });
  });
}
