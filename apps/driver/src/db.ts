import Dexie, { type Table } from "dexie";

export type SyncStatus = "local_only" | "syncing" | "synced" | "retrying" | "conflict" | "failed";

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

class RotasDriverDb extends Dexie {
  syncQueue!: Table<SyncQueueItem, number>;
  photoQueue!: Table<PhotoQueueItem, number>;
  pendingFuelLogs!: Table<PendingFuelLogItem, number>;
  loadPermits!: Table<LoadPermitItem, number>;
  cargoManifests!: Table<CargoManifestItem, number>;
  deliveryProofs!: Table<DeliveryProofItem, number>;

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
  }
}

export const db = new RotasDriverDb();

export function makeLocalId(prefix: string) {
  return `${prefix}_${crypto.randomUUID()}`;
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
