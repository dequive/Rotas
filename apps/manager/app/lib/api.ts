import {
  HttpContractError,
  ensureIdempotencyKey,
  getHttpErrorMessage,
  requestWithPolicy,
  responseToHttpError,
  type HttpErrorBody,
  type HttpPolicy,
} from "@rotas/http-contract";
import { redirect } from "next/navigation";
import { requireSession, refreshAccessToken } from "./auth";

const API_BASE =
  process.env.ROTAS_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

/** Extract a human-readable message from the ROTAS error envelope. */
export function extractApiError(body: HttpErrorBody, fallback: string): string {
  return getHttpErrorMessage(body) ?? fallback;
}

type ApiFetchOptions = RequestInit & {
  revalidate?: number;
  policy?: HttpPolicy;
};

export async function apiFetch<T>(
  path: string,
  options?: ApiFetchOptions,
): Promise<T> {
  const session = await requireSession();
  const { revalidate, policy, ...rest } = options ?? {};
  let requestHeaders = new Headers(rest.headers);
  if (!requestHeaders.has("Content-Type") && rest.body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }
  const method = (rest.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    requestHeaders = ensureIdempotencyKey(requestHeaders);
  }

  const buildHeaders = (accessToken: string, tenantId: string) => {
    const headers = new Headers(requestHeaders);
    headers.set("Authorization", `Bearer ${accessToken}`);
    headers.set("X-Tenant-Id", tenantId);
    return headers;
  };

  const fetchBackend = async (
    accessToken: string,
    tenantId: string,
  ): Promise<Response> => {
    const requestInit = {
      ...rest,
      headers: buildHeaders(accessToken, tenantId),
      next: revalidate !== undefined ? { revalidate } : undefined,
    };
    try {
      return await requestWithPolicy(`${API_BASE}${path}`, requestInit, policy);
    } catch (error) {
      const fallbackBase = "http://127.0.0.1:8000";
      const mayFallback =
        error instanceof HttpContractError &&
        error.status === 0 &&
        !API_BASE.startsWith(fallbackBase);
      if (mayFallback) {
        return requestWithPolicy(`${fallbackBase}${path}`, requestInit, policy);
      }
      throw error;
    }
  };

  let res = await fetchBackend(session.accessToken, session.tenantId);

  // AUTH-01: silent token refresh — retry once on 401 before failing
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      // Retry with the fresh token; cookies are updated by refreshAccessToken()
      const session2 = await requireSession();
      res = await fetchBackend(newToken, session2.tenantId);
    }

    // If token refresh failed or retry still returns 401, redirect cleanly to login
    if (res.status === 401) {
      redirect("/login");
    }
  }

  if (!res.ok) {
    throw await responseToHttpError(res);
  }
  return res.json() as Promise<T>;
}
