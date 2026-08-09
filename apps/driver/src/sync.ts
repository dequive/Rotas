import {
  HttpContractError,
  requestWithPolicy,
  responseToHttpError,
} from "@rotas/http-contract";
import { refreshDriverAccessToken } from "./api";
import {
  belongsToIdentity,
  db,
  getCurrentIdentityScope,
  type DriverIdentityScope,
  type SyncQueueItem,
} from "./db";

interface SyncResult {
  local_id: string;
  server_id?: string;
  status: "processed" | "conflict" | "failed";
  entity_type: string;
  error_code?: string;
  message?: string;
}

const MAX_ATTEMPTS = 5;
const BASE_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 5 * 60_000;

type SyncOptions = {
  now?: () => Date;
  random?: () => number;
};

type TokenContext = { value: string };

export function computeSyncBackoffMs(
  retryCount: number,
  random = Math.random,
): number {
  const ceiling = Math.min(
    MAX_BACKOFF_MS,
    BASE_BACKOFF_MS * 2 ** Math.max(0, retryCount - 1),
  );
  return Math.round(ceiling * (0.5 + random() * 0.5));
}

async function recoverInterruptedSync(
  now: Date,
  scope: DriverIdentityScope,
): Promise<void> {
  const nextAttemptAt = now.toISOString();
  await db.transaction("rw", db.syncQueue, db.photoQueue, async () => {
    await db.syncQueue
      .where("status")
      .equals("syncing")
      .filter((item) => belongsToIdentity(item, scope))
      .modify({
        status: "retrying",
        lastError: "sync_interrupted",
        nextAttemptAt,
      });
    await db.photoQueue
      .where("status")
      .equals("syncing")
      .filter((item) => belongsToIdentity(item, scope))
      .modify({ status: "retrying", nextAttemptAt });
  });
}

export async function processSyncQueue(
  token: string,
  options: SyncOptions = {},
): Promise<void> {
  const now = options.now?.() ?? new Date();
  const random = options.random ?? Math.random;
  const tokenContext: TokenContext = {
    value: localStorage.getItem("rotas_access_token") ?? token,
  };
  const scope = getCurrentIdentityScope();
  if (!scope) throw new Error("driver_identity_scope_missing");
  await recoverInterruptedSync(now, scope);
  const items = await db.syncQueue
    .where("status")
    .anyOf(["local_only", "retrying"])
    .filter(
      (item) =>
        belongsToIdentity(item, scope) &&
        item.retryCount < MAX_ATTEMPTS &&
        (!item.nextAttemptAt || item.nextAttemptAt <= now.toISOString()),
    )
    .toArray();

  for (const item of items) {
    await syncItem(item, tokenContext, now, random);
  }
}

function apiBaseUrl() {
  return localStorage.getItem("rotas_api_base_url") ?? import.meta.env.VITE_ROTAS_API_BASE_URL ?? "";
}

function assertCurrentIdentity(item: SyncQueueItem): void {
  const scope = getCurrentIdentityScope();
  if (!scope || !belongsToIdentity(item, scope)) {
    throw new Error("driver_identity_changed");
  }
}

async function authorizedRequest(
  token: TokenContext,
  input: RequestInfo | URL,
  init: RequestInit,
  policy?: Parameters<typeof requestWithPolicy>[2],
): Promise<Response> {
  const buildInit = () => {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token.value}`);
    return { ...init, headers };
  };
  let response = await requestWithPolicy(input, buildInit(), policy);
  if (response.status === 401) {
    const refreshed = await refreshDriverAccessToken();
    if (refreshed) {
      token.value = refreshed;
      response = await requestWithPolicy(input, buildInit(), policy);
    }
  }
  return response;
}

async function uploadQueuedPhotos(item: SyncQueueItem, token: TokenContext) {
  if (!["fuel_log", "checklist", "delivery_proof", "load_permit"].includes(item.entityType)) {
    return item.payload;
  }

  const photos = await db.photoQueue
    .where("entityLocalId")
    .equals(item.localId)
    .filter((photo) => belongsToIdentity(photo, item))
    .toArray();
  let payload = { ...item.payload };

  for (const photo of photos) {
    if (photo.status === "dead_letter") {
      throw new HttpContractError(
        "O upload da evidência esgotou as tentativas.",
        0,
        "photo_dead_letter",
        undefined,
        false,
      );
    }
    if (photo.serverFileId) {
      payload = applyPhotoFileId(payload, item.entityType, photo.fileType, photo.serverFileId, photo.fieldKey);
      continue;
    }

    await db.photoQueue.update(photo.id!, {
      status: "syncing",
      lastAttemptAt: new Date().toISOString(),
    });
    const form = new FormData();
    form.append("upload", photo.blob, `${photo.localId}.jpg`);
    form.append("file_type", photo.fileType);
    form.append("entity_type", item.entityType);

    assertCurrentIdentity(item);
    const response = await authorizedRequest(
      token,
      `${apiBaseUrl()}/api/v1/files/upload`,
      {
        method: "POST",
        headers: { "X-Tenant-Id": item.tenantId },
        body: form,
      },
      { timeoutMs: 30_000, maxRetries: 0 },
    );

    if (!response.ok) {
      const retryCount = photo.retryCount + 1;
      const deadLetter = retryCount >= MAX_ATTEMPTS;
      await db.photoQueue.update(photo.id!, {
        status: deadLetter ? "dead_letter" : "retrying",
        retryCount,
        deadLetteredAt: deadLetter ? new Date().toISOString() : undefined,
      });
      throw await responseToHttpError(response);
    }

    const uploaded = (await response.json()) as { id: string };
    await db.photoQueue.update(photo.id!, {
      status: "synced",
      serverFileId: uploaded.id,
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
  fieldKey?: string,
) {
  const next = { ...payload };
  if (entityType === "checklist" && fieldKey) {
    const responses = { ...((next.responses as Record<string, unknown> | undefined) ?? {}) };
    const response = responses[fieldKey];
    responses[fieldKey] = {
      ...(typeof response === "object" && response !== null ? response : { value: response }),
      photoFileId: fileId,
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

async function syncItem(
  item: SyncQueueItem,
  token: TokenContext,
  now: Date,
  random: () => number,
): Promise<void> {
  await db.syncQueue.update(item.id!, {
    status: "syncing",
    lastAttemptAt: now.toISOString(),
  });

  try {
    assertCurrentIdentity(item);
    const payload = await uploadQueuedPhotos(item, token);
    assertCurrentIdentity(item);

    const response = await authorizedRequest(
      token,
      `${apiBaseUrl()}/api/v1/sync/batch`,
      {
        method: "POST",
        headers: {
          "X-Tenant-Id": item.tenantId,
          "Idempotency-Key": item.idempotencyKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          device_id: localStorage.getItem("rotas_device_id") ?? "unpaired-device",
          operations: [
            {
              local_id: item.localId,
              idempotency_key: item.idempotencyKey,
              operation: item.operation,
              entity_type: item.entityType,
              payload,
            },
          ],
        }),
      },
      { timeoutMs: 30_000, maxRetries: 0 },
    );

    if (!response.ok) {
      throw await responseToHttpError(response);
    }

    const body = (await response.json()) as { results: SyncResult[] };
    const result = body.results[0];

    if (result.status === "processed") {
      if (item.entityType === "fuel_log") {
        const localFuelLog = await db.pendingFuelLogs
          .where("localId")
          .equals(item.localId)
          .filter((fuelLog) => belongsToIdentity(fuelLog, item))
          .first();
        if (localFuelLog?.id) {
          await db.pendingFuelLogs.update(localFuelLog.id, { status: "synced" });
        }
      }
      await db.syncQueue.delete(item.id!);
      return;
    }

    if (item.entityType === "fuel_log") {
      const localFuelLog = await db.pendingFuelLogs
        .where("localId")
        .equals(item.localId)
        .filter((fuelLog) => belongsToIdentity(fuelLog, item))
        .first();
      if (localFuelLog?.id) {
        await db.pendingFuelLogs.update(localFuelLog.id, {
          status: result.status === "conflict" ? "conflict" : "failed",
        });
      }
    }

    await db.syncQueue.update(item.id!, {
      status: result.status === "conflict" ? "conflict" : "failed",
      lastError: result.message ?? result.error_code ?? "sync_failed",
    });
  } catch (error) {
    if (
      error instanceof HttpContractError &&
      error.code === "driver_access_revoked"
    ) {
      window.dispatchEvent(new CustomEvent("driver-access-revoked"));
      await db.syncQueue.update(item.id!, {
        status: "failed",
        nextAttemptAt: undefined,
        lastError: error.code,
      });
      return;
    }
    if (error instanceof HttpContractError && error.status === 401) {
      await db.syncQueue.update(item.id!, {
        status: "retrying",
        nextAttemptAt: new Date(now.getTime() + MAX_BACKOFF_MS).toISOString(),
        lastError: "session_expired",
      });
      return;
    }
    if (
      error instanceof HttpContractError &&
      error.status >= 400 &&
      error.status < 500 &&
      ![408, 425, 429].includes(error.status)
    ) {
      await db.syncQueue.update(item.id!, {
        status: "failed",
        nextAttemptAt: undefined,
        lastError: error.code,
      });
      return;
    }

    const retryCount = item.retryCount + 1;
    const deadLetter = retryCount >= MAX_ATTEMPTS;
    const nextAttemptAt = deadLetter
      ? undefined
      : new Date(
          now.getTime() + computeSyncBackoffMs(retryCount, random),
        ).toISOString();
    if (item.entityType === "fuel_log") {
      const localFuelLog = await db.pendingFuelLogs
        .where("localId")
        .equals(item.localId)
        .filter((fuelLog) => belongsToIdentity(fuelLog, item))
        .first();
      if (localFuelLog?.id) {
        await db.pendingFuelLogs.update(localFuelLog.id, {
          status: deadLetter ? "dead_letter" : "retrying",
        });
      }
    }
    await db.syncQueue.update(item.id!, {
      status: deadLetter ? "dead_letter" : "retrying",
      retryCount,
      nextAttemptAt,
      deadLetteredAt: deadLetter ? now.toISOString() : undefined,
      lastError:
        error instanceof HttpContractError
          ? error.code
          : error instanceof Error
            ? error.message
            : "unknown_error",
    });
  }
}
