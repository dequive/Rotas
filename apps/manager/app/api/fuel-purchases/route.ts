import { upstreamFetch } from "@/app/lib/upstream-http";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const idempotencyKey = req.headers.get("Idempotency-Key");
  const headers = await getAuthHeaders();
  const res = await upstreamFetch(`${API_BASE}/api/v1/fuel-operations/purchases`, {
    method: "POST",
    headers: {
      ...headers,
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
