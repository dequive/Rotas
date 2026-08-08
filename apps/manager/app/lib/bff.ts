"use client";
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
export class ClientApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

type BffRequestInit = RequestInit & { path?: string };

function assertSameOriginBffPath(path: string): void {
  if (!path.startsWith("/api/") || path.startsWith("/api/v1/")) {
    throw new ClientApiError("Manager BFF path required.", 400);
  }
}

export async function bffRequest(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<Response> {
  const { path: explicit, ...rest } = init;
  const url = explicit ?? `/api/proxy?path=${encodeURIComponent(targetPath)}`;
  assertSameOriginBffPath(url);
  const headers = new Headers(rest.headers ?? {});
  if (rest.body != null && !(rest.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(url, { ...rest, headers, credentials: "include" });
}

export async function bffFetch<T>(
  targetPath: string,
  init: BffRequestInit = {},
): Promise<T> {
  const res = await bffRequest(targetPath, init);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: { message?: string };
    };
    const message = body?.error?.message ?? `HTTP ${res.status}`;
    throw new ClientApiError(message, res.status);
  }
  return (await res.json()) as T;
}
