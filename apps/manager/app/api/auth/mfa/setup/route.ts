import { upstreamFetch } from "@/app/lib/upstream-http";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

async function authHeaders() {
  const jar = await cookies();
  const accessToken = jar.get("rotas_access_token")?.value;
  const tenantId = jar.get("rotas_tenant_id")?.value;
  if (!accessToken || !tenantId) return null;
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Tenant-Id": tenantId,
  };
}

export async function POST() {
  const headers = await authHeaders();
  if (!headers) return NextResponse.json({ error: "Sessão expirada." }, { status: 401 });
  const upstream = await upstreamFetch(`${API_BASE}/api/v1/auth/mfa/setup`, {
    method: "POST",
    headers,
  });
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json({ error: "Não foi possível iniciar MFA." }, { status: upstream.status });
  }
  return NextResponse.json(body);
}
