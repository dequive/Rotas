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

export async function bffFetch<T>(
  targetPath: string,
  init: RequestInit & { path?: string } = {},
): Promise<T> {
  const { path: explicit, ...rest } = init;
  let url: string;
  if (explicit) {
    url = explicit;
  } else {
    url = `/api/proxy?path=${encodeURIComponent(targetPath)}`;
  }
  const headers = new Headers(rest.headers ?? {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, {
    ...rest,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: { message?: string };
    };
    const message = body?.error?.message ?? `HTTP ${res.status}`;
    throw new ClientApiError(message, res.status);
  }
  return (await res.json()) as T;
}