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

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

const ALLOWED_PREFIXES = [
  "/api/v1/",
];

function isAllowed(pathname: string): boolean {
  return ALLOWED_PREFIXES.some(p => pathname.startsWith(p));
}

async function buildHeaders(extraHeaders: Headers) {
  const jar = await cookies();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${jar.get("rotas_access_token")?.value ?? ""}`,
    "X-Tenant-Id": jar.get("rotas_tenant_id")?.value ?? "",
  };
  const idem = extraHeaders.get("Idempotency-Key");
  if (idem) headers["Idempotency-Key"] = idem;
  // Forward X-Request-Id for cross-system correlation if supplied by client.
  const reqId = extraHeaders.get("X-Request-Id");
  if (reqId) headers["X-Request-Id"] = reqId;
  return headers;
}

async function dispatch(req: NextRequest, targetPath: string): Promise<NextResponse> {
  if (!isAllowed(targetPath)) {
    return NextResponse.json(
      { error: { code: "proxy_path_not_allowed", message: "Path not allowlisted." } },
      { status: 400 },
    );
  }
  const upstream = `${API_BASE}${targetPath}${req.nextUrl.search}`;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const init: RequestInit = {
    method: req.method,
    headers: await buildHeaders(req.headers),
  };
  if (hasBody) {
    init.body = await req.text();
  }
  const res = await fetch(upstream, init);
  // Pass-through; do not inject secrets.
  return new NextResponse(res.body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
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