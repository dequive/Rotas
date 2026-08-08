"use client";
import {
  HttpContractError,
  ensureIdempotencyKey,
  requestWithPolicy,
  responseToHttpError,
  type HttpPolicy,
} from "@rotas/http-contract";
/**
 * Stabilization/P0-F7: client-side helper that proxies through the Manager BFF.
 *
 * For components that already have a dedicated route handler (preferred), do
 * NOT use this helper. For "use client" forms/modals that need to mutate
 * state without a domain route, this avoids direct token reads from
 * localStorage.
 *
 * NOTE: prefers individual route handlers under /api/<domain>/** when they
 * exist; falls back to /api/proxy only when no dedicated handler exists.
 */
export class ClientApiError extends HttpContractError {
  constructor(message: string, status: number, code = `http_${status}`, details?: unknown, retryable = false) {
    super(message, status, code, details, retryable);
    this.name = "ClientApiError";
  }
}

type BffRequestInit = RequestInit & { path?: string; policy?: HttpPolicy };

function assertSameOriginBffPath(path: string): void {
  if (!path.startsWith("/api/") || path.startsWith("/api/v1/")) {
    throw new ClientApiError("Manager BFF path required.", 400);
  }
}

export async function bffRequest(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<Response> {
  const { path: explicit, policy, ...rest } = init;
  const url = explicit ?? `/api/proxy?path=${encodeURIComponent(targetPath)}`;
  assertSameOriginBffPath(url);
  const headers = new Headers(rest.headers ?? {});
  if (rest.body != null && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (rest.method ?? "GET").toUpperCase();
  const requestHeaders = ["GET", "HEAD", "OPTIONS"].includes(method)
    ? headers
    : ensureIdempotencyKey(headers);
  return requestWithPolicy(url, { ...rest, headers: requestHeaders, credentials: "include" }, policy);
}

export async function bffFetch<T>(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<T> {
  const res = await bffRequest(targetPath, init);
  if (!res.ok) {
    const error = await responseToHttpError(res);
    throw new ClientApiError(error.message, error.status, error.code, error.details, error.retryable);
  }
  return (await res.json()) as T;
}
