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

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = await req.json();
  const res = await fetch(`${API_BASE}/api/v1/billing/payments/${id}/apply`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
