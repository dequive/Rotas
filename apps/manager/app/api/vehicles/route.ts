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

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const params = new URLSearchParams();
  const limit = searchParams.get("limit") ?? "200";
  const offset = searchParams.get("offset") ?? "0";
  params.set("limit", limit);
  params.set("offset", offset);
  const status = searchParams.get("status");
  if (status) params.set("status", status);

  const res = await upstreamFetch(`${API_BASE}/api/v1/vehicles?${params}`, {
    method: "GET",
    headers: await getAuthHeaders(),
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const res = await upstreamFetch(`${API_BASE}/api/v1/vehicles`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(req: NextRequest) {
  const { id, ...body } = (await req.json()) as { id: string } & Record<string, unknown>;
  const res = await upstreamFetch(`${API_BASE}/api/v1/vehicles/${id}`, {
    method: "PATCH",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
