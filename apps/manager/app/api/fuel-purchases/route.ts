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
  const res = await fetch(`${API_BASE}/api/v1/fuel/purchases`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const params = new URLSearchParams();
  const limit = searchParams.get("limit") ?? "50";
  const offset = searchParams.get("offset") ?? "0";
  params.set("limit", limit);
  params.set("offset", offset);
  const vehicleId = searchParams.get("vehicle_id");
  if (vehicleId) params.set("vehicle_id", vehicleId);

  const res = await fetch(`${API_BASE}/api/v1/fuel/purchases?${params}`, {
    headers: await getAuthHeaders(),
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
