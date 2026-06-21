import { db, type SyncQueueItem } from "./db";

interface SyncResult {
  local_id: string;
  server_id?: string;
  status: "processed" | "conflict" | "failed";
  entity_type: string;
  error_code?: string;
  message?: string;
}

export async function processSyncQueue(token: string) {
  const items = await db.syncQueue
    .where("status")
    .anyOf(["local_only", "retrying"])
    .filter((item) => item.retryCount < 5)
    .toArray();

  for (const item of items) {
    await syncItem(item, token);
  }
}

function apiBaseUrl() {
  return localStorage.getItem("rotas_api_base_url") ?? import.meta.env.VITE_ROTAS_API_BASE_URL ?? "";
}

function tenantId() {
  return localStorage.getItem("rotas_tenant_id") ?? import.meta.env.VITE_ROTAS_TENANT_ID;
}

async function uploadQueuedPhotos(item: SyncQueueItem, token: string) {
  if (!["fuel_log", "checklist", "delivery_proof", "load_permit"].includes(item.entityType)) {
    return item.payload;
  }

  const tenant = tenantId();
  if (!tenant) {
    throw new Error("tenant_not_configured");
  }

  const photos = await db.photoQueue.where("entityLocalId").equals(item.localId).toArray();
  let payload = { ...item.payload };

  for (const photo of photos) {
    if (photo.serverFileId) {
      payload = applyPhotoFileId(payload, item.entityType, photo.fileType, photo.serverFileId, photo.fieldKey);
      continue;
    }

    await db.photoQueue.update(photo.id!, { status: "syncing" });
    const form = new FormData();
    form.append("upload", photo.blob, `${photo.localId}.jpg`);
    form.append("file_type", photo.fileType);
    form.append("entity_type", item.entityType);

    const response = await fetch(`${apiBaseUrl()}/api/v1/files/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Tenant-Id": tenant
      },
      body: form
    });

    if (!response.ok) {
      await db.photoQueue.update(photo.id!, {
        status: "retrying",
        retryCount: photo.retryCount + 1
      });
      throw new Error(`photo_upload_failed_${response.status}`);
    }

    const uploaded = (await response.json()) as { id: string };
    await db.photoQueue.update(photo.id!, {
      status: "synced",
      serverFileId: uploaded.id
    });
    payload = applyPhotoFileId(payload, item.entityType, photo.fileType, uploaded.id, photo.fieldKey);
  }

  if (payload !== item.payload) {
    await db.syncQueue.update(item.id!, { payload });
  }
  return payload;
}

function applyPhotoFileId(
  payload: Record<string, unknown>,
  entityType: string,
  fileType: string,
  fileId: string,
  fieldKey?: string
) {
  const next = { ...payload };
  if (entityType === "checklist" && fieldKey) {
    const responses = { ...((next.responses as Record<string, unknown> | undefined) ?? {}) };
    const response = responses[fieldKey];
    responses[fieldKey] = {
      ...(typeof response === "object" && response !== null ? response : { value: response }),
      photoFileId: fileId
    };
    next.responses = responses;
    return next;
  }

  if (fileType === "receipt") {
    next.receiptFileId = fileId;
    delete next.receiptPhotoLocalId;
  } else {
    next.odometerFileId = fileId;
    delete next.odometerPhotoLocalId;
  }
  return next;
}

async function syncItem(item: SyncQueueItem, token: string) {
  await db.syncQueue.update(item.id!, { status: "syncing" });

  try {
    const tenant = tenantId();
    if (!tenant) {
      throw new Error("tenant_not_configured");
    }
    const payload = await uploadQueuedPhotos(item, token);

    const response = await fetch(`${apiBaseUrl()}/api/v1/sync/batch`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Tenant-Id": tenant,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        device_id: localStorage.getItem("rotas_device_id") ?? "unpaired-device",
        operations: [
          {
            local_id: item.localId,
            idempotency_key: item.idempotencyKey,
            operation: item.operation,
            entity_type: item.entityType,
            payload
          }
        ]
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const body = (await response.json()) as { results: SyncResult[] };
    const result = body.results[0];

    if (result.status === "processed") {
      if (item.entityType === "fuel_log") {
        const localFuelLog = await db.pendingFuelLogs
          .where("localId")
          .equals(item.localId)
          .first();
        if (localFuelLog?.id) {
          await db.pendingFuelLogs.update(localFuelLog.id, { status: "synced" });
        }
      }
      await db.syncQueue.delete(item.id!);
      return;
    }

    if (item.entityType === "fuel_log") {
      const localFuelLog = await db.pendingFuelLogs.where("localId").equals(item.localId).first();
      if (localFuelLog?.id) {
        await db.pendingFuelLogs.update(localFuelLog.id, {
          status: result.status === "conflict" ? "conflict" : "failed"
        });
      }
    }

    await db.syncQueue.update(item.id!, {
      status: result.status === "conflict" ? "conflict" : "failed",
      lastError: result.message ?? result.error_code ?? "sync_failed"
    });
  } catch (error) {
    if (item.entityType === "fuel_log") {
      const localFuelLog = await db.pendingFuelLogs.where("localId").equals(item.localId).first();
      if (localFuelLog?.id) {
        await db.pendingFuelLogs.update(localFuelLog.id, { status: "retrying" });
      }
    }
    await db.syncQueue.update(item.id!, {
      status: "retrying",
      retryCount: item.retryCount + 1,
      lastError: error instanceof Error ? error.message : "unknown_error"
    });
  }
}
