import { upstreamFetch } from "@/app/lib/upstream-http";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

async function getAuthHeaders() {
  const jar = await cookies();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${jar.get("rotas_access_token")?.value ?? ""}`,
    "X-Tenant-Id": jar.get("rotas_tenant_id")?.value ?? "",
  };
}

export async function POST(req: NextRequest) {
  const body = (await req.json()) as Record<string, unknown>;
  const { _action, id, ...payload } = body;

  if (_action === "start") {
    const res = await upstreamFetch(`${API_BASE}/api/v1/trips/${String(id)}/start`, {
      method: "POST",
      headers: await getAuthHeaders(),
    });
    return NextResponse.json(await res.json(), { status: res.status });
  }

  if (_action === "complete") {
    const res = await upstreamFetch(`${API_BASE}/api/v1/trips/${String(id)}/complete`, {
      method: "POST",
      headers: await getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    return NextResponse.json(await res.json(), { status: res.status });
  }

  const res = await upstreamFetch(`${API_BASE}/api/v1/trips`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
