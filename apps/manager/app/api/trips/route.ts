import { upstreamFetch } from "@/app/lib/upstream-http";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { refreshAccessToken } from "../../lib/auth";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

async function getAuthHeaders(idempotencyKey?: string) {
  const jar = await cookies();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${jar.get("rotas_access_token")?.value ?? ""}`,
    "X-Tenant-Id": jar.get("rotas_tenant_id")?.value ?? "",
    ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
  };
}

async function fetchWithAutoRefresh(url: string, init: RequestInit): Promise<Response> {
  let res = await upstreamFetch(url, init);
  if (res.status === 401) {
    const refreshedToken = await refreshAccessToken();
    if (refreshedToken) {
      const jar = await cookies();
      const tenantId = jar.get("rotas_tenant_id")?.value ?? "";
      const headers = new Headers(init.headers);
      headers.set("Content-Type", "application/json");
      headers.set("Authorization", `Bearer ${refreshedToken}`);
      headers.set("X-Tenant-Id", tenantId);
      res = await upstreamFetch(url, { ...init, headers });
    }
  }
  return res;
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as Record<string, unknown>;
  const { _action, id, ...payload } = body;
  const action = typeof _action === "string" ? _action : "create";
  const resourceId = typeof id === "string" ? id : "new";
  const headers = await getAuthHeaders(`manager:trip:${action}:${resourceId}`);

  let targetUrl = `${API_BASE}/api/v1/trips`;
  if (_action === "request_clearance") {
    targetUrl = `${API_BASE}/api/v1/trips/${String(id)}/dispatch-clearance/request`;
  } else if (_action === "start") {
    targetUrl = `${API_BASE}/api/v1/trips/${String(id)}/start`;
  } else if (_action === "complete") {
    targetUrl = `${API_BASE}/api/v1/trips/${String(id)}/complete`;
  }

  const res = await fetchWithAutoRefresh(targetUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  const resData = await res.json().catch(() => ({}));
  return NextResponse.json(resData, { status: res.status });
}
