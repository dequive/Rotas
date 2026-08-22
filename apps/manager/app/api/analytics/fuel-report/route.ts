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

export async function GET(request: NextRequest) {
  const month = request.nextUrl.searchParams.get("month") ?? "";
  const res = await upstreamFetch(
    `${API_BASE}/api/v1/analytics/fuel-report?month=${encodeURIComponent(month)}`,
    {
      method: "GET",
      headers: await getAuthHeaders(),
      cache: "no-store",
    },
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
