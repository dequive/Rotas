import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const jar = await cookies();
  const { driver_id } = (await req.json()) as { driver_id: string };
  const res = await fetch(`${API_BASE}/api/v1/drivers/${driver_id}/pairing-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${jar.get("rotas_access_token")?.value ?? ""}`,
      "X-Tenant-Id": jar.get("rotas_tenant_id")?.value ?? "",
    },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
