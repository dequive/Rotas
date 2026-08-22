"use client";
import {
  HttpContractError,
  type HttpPolicy,
  ensureIdempotencyKey,
  requestWithPolicy,
  responseToHttpError,
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
  constructor(error: HttpContractError) {
    super(
      error.message,
      error.status,
      error.code,
      error.details,
      error.retryable,
    );
    this.name = "ClientApiError";
  }
}

type BffRequestInit = RequestInit & {
  path?: string;
  policy?: HttpPolicy;
};

export async function bffRequest(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<Response> {
  const { path: explicit, policy, ...rest } = init;
  const url =
    explicit ?? `/api/proxy?path=${encodeURIComponent(targetPath)}`;
  let headers = new Headers(rest.headers ?? {});
  const hasBody = rest.body !== undefined && rest.body !== null;
  if (
    hasBody &&
    !(rest.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const method = (rest.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers = ensureIdempotencyKey(headers);
  }
  return requestWithPolicy(
    url,
    {
      ...rest,
      headers,
      credentials: "include",
    },
    policy,
  );
}

export async function bffFetch<T>(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<T> {
  const res = await bffRequest(targetPath, init);
  if (!res.ok) {
    throw new ClientApiError(await responseToHttpError(res));
  }
  return (await res.json()) as T;
}
