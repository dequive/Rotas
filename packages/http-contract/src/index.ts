export type HttpErrorBody = {
  detail?: string;
  error?: string | {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

export type HttpPolicy = {
  timeoutMs?: number;
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryStatuses?: readonly number[];
  fetch?: typeof globalThis.fetch;
  sleep?: (delayMs: number) => Promise<void>;
  random?: () => number;
};

const DEFAULT_RETRY_STATUSES = [408, 425, 429, 502, 503, 504] as const;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class HttpContractError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details?: unknown,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = "HttpContractError";
  }
}

export function getHttpErrorCode(body: HttpErrorBody): string | undefined {
  if (typeof body.error === "string") return body.error;
  if (body.error?.code) return body.error.code;
  return undefined;
}

export function getHttpErrorMessage(body: HttpErrorBody): string | undefined {
  if (typeof body.error === "object" && body.error.message) {
    return body.error.message;
  }
  return body.detail ?? getHttpErrorCode(body);
}

export async function responseToHttpError(
  response: Response,
): Promise<HttpContractError> {
  let body: HttpErrorBody = {};
  try {
    body = (await response.clone().json()) as HttpErrorBody;
  } catch {
    // Empty and non-JSON error responses still receive a stable typed error.
  }
  const code = getHttpErrorCode(body) ?? `http_${response.status}`;
  const message = getHttpErrorMessage(body) ?? `HTTP ${response.status}`;
  const details =
    typeof body.error === "object" ? body.error.details : undefined;
  return new HttpContractError(
    message,
    response.status,
    code,
    details,
    DEFAULT_RETRY_STATUSES.includes(
      response.status as (typeof DEFAULT_RETRY_STATUSES)[number],
    ),
  );
}

export function ensureIdempotencyKey(
  headersInit?: HeadersInit,
  key = globalThis.crypto.randomUUID(),
): Headers {
  const headers = new Headers(headersInit);
  if (!headers.has("Idempotency-Key")) {
    headers.set("Idempotency-Key", key);
  }
  return headers;
}

function retryAllowed(method: string, headers: Headers): boolean {
  return SAFE_METHODS.has(method) || headers.has("Idempotency-Key");
}

function retryAfterMs(response: Response): number | undefined {
  const value = response.headers.get("Retry-After");
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;
  const at = Date.parse(value);
  if (Number.isNaN(at)) return undefined;
  return Math.max(0, at - Date.now());
}

function delayForAttempt(
  attempt: number,
  baseDelayMs: number,
  maxDelayMs: number,
  random: () => number,
): number {
  const exponential = Math.min(maxDelayMs, baseDelayMs * 2 ** attempt);
  return Math.round(exponential * (0.5 + random() * 0.5));
}

async function cancelResponse(response: Response): Promise<void> {
  try {
    await response.body?.cancel();
  } catch {
    // A consumed or synthetic response may not expose a cancellable body.
  }
}

export async function requestWithPolicy(
  input: RequestInfo | URL,
  init: RequestInit = {},
  policy: HttpPolicy = {},
): Promise<Response> {
  const fetchImpl = policy.fetch ?? globalThis.fetch;
  const sleep =
    policy.sleep ??
    ((delayMs: number) =>
      new Promise<void>((resolve) => globalThis.setTimeout(resolve, delayMs)));
  const random = policy.random ?? Math.random;
  const timeoutMs = policy.timeoutMs ?? 15_000;
  const maxRetries = Math.max(0, policy.maxRetries ?? 2);
  const baseDelayMs = Math.max(0, policy.baseDelayMs ?? 250);
  const maxDelayMs = Math.max(baseDelayMs, policy.maxDelayMs ?? 2_000);
  const retryStatuses = new Set(
    policy.retryStatuses ?? DEFAULT_RETRY_STATUSES,
  );
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  const canRetry = retryAllowed(method, headers);

  for (let attempt = 0; ; attempt += 1) {
    const controller = new AbortController();
    let timedOut = false;
    const relayAbort = () => controller.abort(init.signal?.reason);
    if (init.signal?.aborted) relayAbort();
    else init.signal?.addEventListener("abort", relayAbort, { once: true });
    const timer = globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    try {
      const response = await fetchImpl(input, {
        ...init,
        headers,
        signal: controller.signal,
      });
      if (
        canRetry &&
        attempt < maxRetries &&
        retryStatuses.has(response.status)
      ) {
        const retryDelay = Math.min(
          maxDelayMs,
          retryAfterMs(response) ??
            delayForAttempt(attempt, baseDelayMs, maxDelayMs, random),
        );
        await cancelResponse(response);
        await sleep(retryDelay);
        continue;
      }
      return response;
    } catch (error) {
      if (init.signal?.aborted) {
        throw new HttpContractError(
          "Pedido cancelado.",
          0,
          "request_aborted",
          undefined,
          false,
        );
      }
      const retryable = timedOut || error instanceof TypeError;
      if (canRetry && retryable && attempt < maxRetries) {
        await sleep(
          delayForAttempt(attempt, baseDelayMs, maxDelayMs, random),
        );
        continue;
      }
      throw new HttpContractError(
        timedOut ? "O pedido excedeu o tempo limite." : "Serviço indisponível.",
        0,
        timedOut ? "request_timeout" : "network_error",
        error,
        retryable,
      );
    } finally {
      globalThis.clearTimeout(timer);
      init.signal?.removeEventListener("abort", relayAbort);
    }
  }
}
