import { cookies } from "next/headers";
import { readFileSync } from "node:fs";
import { upstreamFetch } from "./upstream-http";

const ROTAS_API_BASE =
  process.env.ROTAS_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";
const MAX_JSON_BYTES = 64 * 1024;
const MAX_UPSTREAM_BYTES = 1024 * 1024;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type JsonObject = Record<string, unknown>;

class GovernanceBoundaryError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "GovernanceBoundaryError";
  }
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorResponse(status: number, code: string, message: string) {
  return Response.json({ error: { code, message } }, { status });
}

async function verifiedTenantContext(): Promise<{
  tenantId: string;
  apiKey: string;
}> {
  const jar = await cookies();
  const accessToken = jar.get("rotas_access_token")?.value;
  const tenantId = jar.get("rotas_tenant_id")?.value;
  if (!accessToken || !tenantId) {
    throw new GovernanceBoundaryError(
      401,
      "authentication_required",
      "Authentication required.",
    );
  }
  if (!UUID_PATTERN.test(tenantId)) {
    throw new GovernanceBoundaryError(
      403,
      "invalid_tenant_session",
      "The tenant session is invalid.",
    );
  }

  const tenantResponse = await upstreamFetch(
    `${ROTAS_API_BASE}/api/v1/tenants/me`,
    {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Tenant-Id": tenantId,
      },
      cache: "no-store",
    },
  );
  if (tenantResponse.status === 401) {
    throw new GovernanceBoundaryError(
      401,
      "authentication_required",
      "Authentication required.",
    );
  }
  if (!tenantResponse.ok) {
    throw new GovernanceBoundaryError(
      502,
      "rotas_session_verification_failed",
      "The ROTAS session could not be verified.",
    );
  }

  const verifiedTenant = (await tenantResponse.json().catch(() => null)) as
    | JsonObject
    | null;
  if (verifiedTenant?.id !== tenantId) {
    throw new GovernanceBoundaryError(
      403,
      "tenant_session_mismatch",
      "The authenticated tenant does not match the active session.",
    );
  }

  return { tenantId, apiKey: governanceKeyForTenant(tenantId) };
}

function governanceKeyForTenant(tenantId: string): string {
  const serialized = configuredSecret(
    "GOVERNANCE_API_KEYS_BY_TENANT",
    "GOVERNANCE_API_KEYS_BY_TENANT_FILE",
  );
  if (serialized) {
    try {
      const parsed = JSON.parse(serialized) as unknown;
      if (!isObject(parsed)) throw new Error("not an object");
      const key = parsed[tenantId];
      if (typeof key === "string" && key.length > 0) return key;
    } catch {
      throw new GovernanceBoundaryError(
        503,
        "governance_configuration_invalid",
        "Governance credentials are not configured correctly.",
      );
    }
  }

  const singleTenant = process.env.GOVERNANCE_TENANT_ID;
  const singleKey = configuredSecret(
    "GOVERNANCE_API_KEY",
    "GOVERNANCE_API_KEY_FILE",
  );
  if (singleTenant === tenantId && singleKey) return singleKey;

  throw new GovernanceBoundaryError(
    503,
    "governance_tenant_not_configured",
    "Governance is not configured for this tenant.",
  );
}

function configuredSecret(valueName: string, fileName: string): string | undefined {
  const direct = process.env[valueName]?.trim();
  if (direct) return direct;
  const path = process.env[fileName]?.trim();
  if (!path) return undefined;
  try {
    const value = readFileSync(path, "utf8").trim();
    if (!value || value.length > MAX_JSON_BYTES) throw new Error("invalid secret");
    return value;
  } catch {
    throw new GovernanceBoundaryError(
      503,
      "governance_configuration_invalid",
      "Governance credentials are not configured correctly.",
    );
  }
}

function governanceBaseUrl(): string {
  const configured = process.env.GOVERNANCE_API_URL;
  if (!configured) {
    throw new GovernanceBoundaryError(
      503,
      "governance_configuration_missing",
      "Governance service is not configured.",
    );
  }
  let url: URL;
  try {
    url = new URL(configured);
  } catch {
    throw new GovernanceBoundaryError(
      503,
      "governance_configuration_invalid",
      "Governance service URL is invalid.",
    );
  }
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    !["http:", "https:"].includes(url.protocol)
  ) {
    throw new GovernanceBoundaryError(
      503,
      "governance_configuration_invalid",
      "Governance service URL is invalid.",
    );
  }
  const localHost = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  const approvedInternalService =
    process.env.GOVERNANCE_ALLOW_INSECURE_INTERNAL === "true" &&
    url.hostname === "governance";
  if (
    url.protocol !== "https:" &&
    !localHost &&
    !approvedInternalService
  ) {
    throw new GovernanceBoundaryError(
      503,
      "governance_transport_insecure",
      "Governance requires a secure upstream connection.",
    );
  }
  if (
    process.env.NODE_ENV === "production" &&
    url.protocol !== "https:" &&
    !approvedInternalService
  ) {
    throw new GovernanceBoundaryError(
      503,
      "governance_transport_insecure",
      "Governance requires a secure upstream connection.",
    );
  }
  return url.toString().replace(/\/$/, "");
}

export function assertUuid(value: string): string {
  if (!UUID_PATTERN.test(value)) {
    throw new GovernanceBoundaryError(400, "invalid_case_id", "Case id is invalid.");
  }
  return value;
}

export async function readJsonObject(request: Request): Promise<JsonObject> {
  const declaredLength = Number(request.headers.get("Content-Length") ?? "0");
  if (declaredLength > MAX_JSON_BYTES) {
    throw new GovernanceBoundaryError(413, "payload_too_large", "Request body is too large.");
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > MAX_JSON_BYTES) {
    throw new GovernanceBoundaryError(413, "payload_too_large", "Request body is too large.");
  }
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!isObject(parsed)) throw new Error("not an object");
    return parsed;
  } catch {
    throw new GovernanceBoundaryError(400, "invalid_json", "A JSON object is required.");
  }
}

export function requireIdempotencyKey(request: Request): string {
  const value = request.headers.get("Idempotency-Key")?.trim();
  if (!value || value.length > 256) {
    throw new GovernanceBoundaryError(
      400,
      "idempotency_key_required",
      "A valid Idempotency-Key header is required.",
    );
  }
  return value;
}

export function caseCreateBody(body: JsonObject): JsonObject {
  const code = body.case_type_code;
  const payload = body.payload ?? {};
  const occurrenceIds = body.occurrence_ids ?? [];
  if (typeof code !== "string" || !/^[a-z0-9][a-z0-9._-]{1,99}$/i.test(code)) {
    throw new GovernanceBoundaryError(
      422,
      "invalid_case_type_code",
      "A valid case_type_code is required.",
    );
  }
  if (!isObject(payload)) {
    throw new GovernanceBoundaryError(422, "invalid_payload", "Payload must be an object.");
  }
  if (
    !Array.isArray(occurrenceIds) ||
    occurrenceIds.length > 100 ||
    occurrenceIds.some((id) => typeof id !== "string" || !UUID_PATTERN.test(id))
  ) {
    throw new GovernanceBoundaryError(
      422,
      "invalid_occurrence_ids",
      "occurrence_ids must contain valid UUIDs.",
    );
  }
  return { case_type_code: code, occurrence_ids: occurrenceIds, payload };
}

export function transitionBody(body: JsonObject): JsonObject {
  const status = body.to_status;
  const payload = body.payload ?? {};
  const reason = body.reason;
  const attachmentsPresent = body.attachments_present ?? false;
  if (typeof status !== "string" || !/^[a-z][a-z0-9_-]{1,63}$/i.test(status)) {
    throw new GovernanceBoundaryError(422, "invalid_status", "A valid to_status is required.");
  }
  if (!isObject(payload)) {
    throw new GovernanceBoundaryError(422, "invalid_payload", "Payload must be an object.");
  }
  if (reason !== undefined && (typeof reason !== "string" || reason.length > 1000)) {
    throw new GovernanceBoundaryError(422, "invalid_reason", "Reason is invalid.");
  }
  if (typeof attachmentsPresent !== "boolean") {
    throw new GovernanceBoundaryError(
      422,
      "invalid_attachments_flag",
      "attachments_present must be a boolean.",
    );
  }
  return {
    to_status: status,
    payload,
    ...(reason === undefined ? {} : { reason }),
    attachments_present: attachmentsPresent,
  };
}

export function caseListQuery(searchParams: URLSearchParams): string {
  const output = new URLSearchParams();
  for (const name of ["status", "type", "limit", "offset"] as const) {
    const value = searchParams.get(name);
    if (value !== null) output.set(name, value);
  }
  const query = output.toString();
  return query ? `?${query}` : "";
}

async function relayJson(response: Response): Promise<Response> {
  const declaredLength = Number(response.headers.get("Content-Length") ?? "0");
  if (declaredLength > MAX_UPSTREAM_BYTES) {
    return errorResponse(502, "invalid_upstream_response", "Governance returned an invalid response.");
  }
  const text = await response.text();
  if (new TextEncoder().encode(text).byteLength > MAX_UPSTREAM_BYTES) {
    return errorResponse(502, "invalid_upstream_response", "Governance returned an invalid response.");
  }
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return errorResponse(502, "invalid_upstream_response", "Governance returned an invalid response.");
  }
  if (response.ok) return Response.json(body, { status: response.status });

  const source = isObject(body) && isObject(body.detail) ? body.detail : body;
  const upstreamCode = isObject(source) && typeof source.code === "string" ? source.code : "governance_request_failed";
  const upstreamMessage =
    isObject(source) && typeof source.message === "string"
      ? source.message
      : "Governance rejected the request.";
  const status = response.status >= 400 && response.status < 500 ? response.status : 502;
  return errorResponse(status, upstreamCode, upstreamMessage);
}

export async function governanceRequest(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  try {
    const { apiKey } = await verifiedTenantContext();
    const headers = new Headers(init.headers);
    headers.set("X-API-Key", apiKey);
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    const response = await upstreamFetch(
      `${governanceBaseUrl()}${path}`,
      { ...init, headers, cache: "no-store" },
      { timeoutMs: 5000, maxRetries: 0 },
    );
    return relayJson(response);
  } catch (error) {
    if (error instanceof GovernanceBoundaryError) {
      return errorResponse(error.status, error.code, error.message);
    }
    return errorResponse(502, "governance_unavailable", "Governance service is unavailable.");
  }
}

export function boundaryErrorResponse(error: unknown): Response {
  if (error instanceof GovernanceBoundaryError) {
    return errorResponse(error.status, error.code, error.message);
  }
  return errorResponse(500, "internal_error", "The request could not be processed.");
}
