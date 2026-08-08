import { HttpContractError, requestWithPolicy, type HttpPolicy } from "@rotas/http-contract";
import { headers as incomingHeaders } from "next/headers";

const FORWARDED_HEADERS = ["Idempotency-Key", "X-Request-Id"] as const;

/** Common Manager BFF -> ROTAS API transport boundary. */
export async function upstreamFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  policy?: HttpPolicy,
): Promise<Response> {
  const outgoing = new Headers(init.headers);
  try {
    const incoming = await incomingHeaders();
    for (const name of FORWARDED_HEADERS) {
      const value = incoming.get(name);
      if (value && !outgoing.has(name)) outgoing.set(name, value);
    }
  } catch {
    // Unit tests and non-request contexts may not expose Next request headers.
  }
  try {
    return await requestWithPolicy(input, { ...init, headers: outgoing }, policy);
  } catch (error) {
    if (!(error instanceof HttpContractError)) throw error;
    const status = error.code === "request_timeout" ? 504 : 502;
    const code = error.code === "network_error" ? "upstream_unavailable" : error.code;
    const message = error.code === "network_error" ? "Upstream service unavailable." : error.message;
    return Response.json(
      { error: { code, message, details: { retryable: error.retryable } } },
      { status },
    );
  }
}
