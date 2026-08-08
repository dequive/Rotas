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
  const body = await req.json();
  const res = await upstreamFetch(`${API_BASE}/api/v1/known-routes`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function PATCH(req: NextRequest) {
  const { id, ...body } = (await req.json()) as { id: string } & Record<string, unknown>;
  const res = await upstreamFetch(`${API_BASE}/api/v1/known-routes/${id}`, {
    method: "PATCH",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}

export async function DELETE(req: NextRequest) {
  const { id } = (await req.json()) as { id: string };
  const res = await upstreamFetch(`${API_BASE}/api/v1/known-routes/${id}`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });
  return NextResponse.json(await res.json(), { status: res.status });
}
