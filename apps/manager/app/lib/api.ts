import {
  ensureIdempotencyKey,
  requestWithPolicy,
  responseToHttpError,
  type HttpErrorBody,
  type HttpPolicy,
} from "@rotas/http-contract";
import { requireSession, refreshAccessToken } from "./auth";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

/** Extract a human-readable message from the ROTAS error envelope. */
export function extractApiError(body: HttpErrorBody, fallback: string): string {
  if (typeof body.error === "object" && body.error !== null) {
    if (body.error.message) return body.error.message;
    if (body.error.code) return body.error.code;
  }
  if (typeof body.detail === "string" && body.detail) return body.detail;
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit & { revalidate?: number; policy?: HttpPolicy }
): Promise<T> {
  const session = await requireSession();
  const { revalidate, policy, ...rest } = options ?? {};
  const method = (rest.method ?? "GET").toUpperCase();
  const isMutation = !["GET", "HEAD", "OPTIONS"].includes(method);
  const idempotencyKey = isMutation
    ? new Headers(rest.headers).get("Idempotency-Key") ?? globalThis.crypto.randomUUID()
    : undefined;

  const buildHeaders = (accessToken: string, tenantId: string) => {
    const headers = new Headers(rest.headers);
    if (rest.body != null && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("Authorization", `Bearer ${accessToken}`);
    headers.set("X-Tenant-Id", tenantId);
    return idempotencyKey ? ensureIdempotencyKey(headers, idempotencyKey) : headers;
  };

  const request = (accessToken: string, tenantId: string) => requestWithPolicy(`${API_BASE}${path}`, {
    ...rest,
    headers: buildHeaders(accessToken, tenantId),
    next: revalidate !== undefined ? { revalidate } : undefined,
  }, policy);

  let res = await request(session.accessToken, session.tenantId);

  // AUTH-01: silent token refresh — retry once on 401 before failing
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      // Retry with the fresh token; cookies are updated by refreshAccessToken()
      const session2 = await requireSession();
      res = await request(newToken, session2.tenantId);
    }
    // If refresh failed (newToken = null), fall through to the error below
    // requireSession() will redirect to /login on the next navigation
  }

  if (!res.ok) {
    throw await responseToHttpError(res);
  }
  return res.json() as Promise<T>;
}
