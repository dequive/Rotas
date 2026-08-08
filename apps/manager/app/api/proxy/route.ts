/**
 * Stabilization/P0-F7: generic BFF proxy for client components.
 *
 * Page TSX files can still need to call the backend from "use client"
 * contexts (forms, modals, etc.). They MUST NOT read tokens from
 * localStorage and they MUST NOT include secrets in the response.
 *
 * The intended migration is to replace each call site with a dedicated,
 * domain-specific route handler under `app/api/<domain>/route.ts` (the
 * existing pattern in this codebase). The catch-all here is acceptable
 * as an interim bridge while the per-domain migrations land in P1.
 *
 * Usage from a client component:
 *   const data = await fetch("/api/proxy?path=/api/v1/hr/employees", {
 *     method: "POST",
 *     headers: { "Content-Type": "application/json",
 *                  "Idempotency-Key": "<uuid>" },
 *     body: JSON.stringify(payload),
 *     credentials: "include",
 *   }).then(r => r.json());
 *
 * The handler dispatches to the configured backend, carrying ONLY the
 * HttpOnly cookies as credentials. The handler refuses to proxy any
 * non-allowlisted path.
 */
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { refreshAccessToken } from "../../lib/auth";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

const ALLOWED_PREFIXES = [
  "/api/v1/",
];

function isAllowed(pathname: string): boolean {
  if (!pathname.startsWith("/") || pathname.startsWith("//")) return false;
  try {
    const target = new URL(pathname, "http://manager-bff.invalid");
    return (
      target.origin === "http://manager-bff.invalid" &&
      ALLOWED_PREFIXES.some((prefix) => target.pathname.startsWith(prefix))
    );
  } catch {
    return false;
  }
}

function isSameOriginMutation(req: NextRequest): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return true;
  const origin = req.headers.get("Origin");
  if (!origin) return false;
  try {
    return new URL(origin).origin === req.nextUrl.origin;
  } catch {
    return false;
  }
}

async function buildHeaders(extraHeaders: Headers) {
  const jar = await cookies();
  const accessToken = jar.get("rotas_access_token")?.value;
  const tenantId = jar.get("rotas_tenant_id")?.value;
  if (!accessToken || !tenantId) return null;
  const headers = new Headers({
    Authorization: `Bearer ${accessToken}`,
    "X-Tenant-Id": tenantId,
  });
  const contentType = extraHeaders.get("Content-Type");
  if (contentType) headers.set("Content-Type", contentType);
  const idem = extraHeaders.get("Idempotency-Key");
  if (idem) headers.set("Idempotency-Key", idem);
  // Forward X-Request-Id for cross-system correlation if supplied by client.
  const reqId = extraHeaders.get("X-Request-Id");
  if (reqId) headers.set("X-Request-Id", reqId);
  return headers;
}

async function dispatch(req: NextRequest, targetPath: string): Promise<NextResponse> {
  if (!isSameOriginMutation(req)) {
    return NextResponse.json(
      { error: { code: "cross_origin_request", message: "Same-origin request required." } },
      { status: 403 },
    );
  }
  if (!isAllowed(targetPath)) {
    return NextResponse.json(
      { error: { code: "proxy_path_not_allowed", message: "Path not allowlisted." } },
      { status: 400 },
    );
  }
  const headers = await buildHeaders(req.headers);
  if (!headers) {
    return NextResponse.json(
      { error: { code: "authentication_required", message: "Authentication required." } },
      { status: 401 },
    );
  }
  const upstream = `${API_BASE}${targetPath}`;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };
  if (hasBody) {
    init.body = await req.text();
  }
  let res: Response;
  try {
    res = await fetch(upstream, init);
    if (res.status === 401) {
      const refreshedToken = await refreshAccessToken();
      if (refreshedToken) {
        headers.set("Authorization", `Bearer ${refreshedToken}`);
        res = await fetch(upstream, init);
      }
    }
  } catch {
    return NextResponse.json(
      { error: { code: "upstream_unavailable", message: "Upstream service unavailable." } },
      { status: 502 },
    );
  }
  // Pass-through; do not inject secrets.
  return new NextResponse(res.body, {
    status: res.status,
    headers: Object.fromEntries(
      ["Content-Type", "Content-Disposition", "ETag"]
        .map((name) => [name, res.headers.get(name)] as const)
        .filter((entry): entry is readonly [string, string] => entry[1] !== null),
    ),
  });
}

export async function GET(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("path") ?? "";
  return dispatch(req, target);
}

export async function POST(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("path") ?? "";
  return dispatch(req, target);
}

export async function PUT(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("path") ?? "";
  return dispatch(req, target);
}

export async function PATCH(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("path") ?? "";
  return dispatch(req, target);
}

export async function DELETE(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("path") ?? "";
  return dispatch(req, target);
}
