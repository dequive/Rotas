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

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const searchParams = req.nextUrl.searchParams;
  const periodStart = searchParams.get("period_start");
  const periodEnd = searchParams.get("period_end");

  const backendUrl = new URL(`${API_BASE}/api/v1/clients/${id}/statement`);
  if (periodStart) backendUrl.searchParams.set("period_start", periodStart);
  if (periodEnd) backendUrl.searchParams.set("period_end", periodEnd);

  const res = await fetch(backendUrl.toString(), {
    method: "GET",
    headers: await getAuthHeaders(),
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
