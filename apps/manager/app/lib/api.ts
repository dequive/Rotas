import { requireSession, refreshAccessToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ApiErrorBody = {
  detail?: string;
  error?: { code?: string; message?: string; details?: unknown };
};

/** Extract a human-readable message from the ROTAS error envelope. */
export function extractApiError(body: ApiErrorBody, fallback: string): string {
  if (typeof body.error === "object" && body.error !== null) {
    if (body.error.message) return body.error.message;
    if (body.error.code) return body.error.code;
  }
  if (typeof body.detail === "string" && body.detail) return body.detail;
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit & { revalidate?: number }
): Promise<T> {
  const session = await requireSession();
  const { revalidate, ...rest } = options ?? {};

  const buildHeaders = (accessToken: string, tenantId: string) => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Tenant-Id": tenantId,
    ...(rest.headers ?? {}),
  });

  let res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: buildHeaders(session.accessToken, session.tenantId),
    next: revalidate !== undefined ? { revalidate } : undefined,
  });

  // AUTH-01: silent token refresh — retry once on 401 before failing
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      // Retry with the fresh token; cookies are updated by refreshAccessToken()
      const session2 = await requireSession();
      res = await fetch(`${API_BASE}${path}`, {
        ...rest,
        headers: buildHeaders(newToken, session2.tenantId),
        next: revalidate !== undefined ? { revalidate } : undefined,
      });
    }
    // If refresh failed (newToken = null), fall through to the error below
    // requireSession() will redirect to /login on the next navigation
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(extractApiError(body, `HTTP ${res.status}`));
  }
  return res.json() as Promise<T>;
}
