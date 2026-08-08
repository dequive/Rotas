"use client";

import createClient from "openapi-fetch";
import type { paths } from "../generated/rotas-api";
import { bffRequest } from "./bff";

async function bffTransport(input: RequestInfo | URL, init?: RequestInit) {
  const request = input instanceof Request ? input : new Request(input, init);
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  headers.delete("Authorization");

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const body = hasBody ? await request.clone().arrayBuffer() : undefined;
  return bffRequest(`${url.pathname}${url.search}`, {
    method: request.method,
    headers,
    body,
    signal: request.signal,
  });
}

const managerOrigin =
  typeof window === "undefined" ? "http://manager.invalid" : window.location.origin;

/**
 * Contract-first client for incremental migration of Manager API calls.
 *
 * The generated path/request/response types come from FastAPI's committed
 * OpenAPI contract. The transport never calls the backend from the browser:
 * every request is remapped to the Manager BFF, which adds HttpOnly session
 * credentials server-side.
 */
export const generatedApiClient = createClient<paths>({
  baseUrl: managerOrigin,
  fetch: bffTransport,
});
