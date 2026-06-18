import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

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

function errorMessage(body: unknown): string {
  if (body && typeof body === "object" && "error" in body) {
    const error = (body as { error?: { message?: string } }).error;
    if (error?.message) return error.message;
  }
  return "Não foi possível revogar a sessão.";
}

export async function DELETE(
  _req: NextRequest,
  context: { params: Promise<{ sessionId: string }> }
) {
  const headers = await authHeaders();
  if (!headers) return NextResponse.json({ error: "Sessão expirada." }, { status: 401 });

  const { sessionId } = await context.params;
  const upstream = await fetch(`${API_BASE}/api/v1/auth/sessions/${sessionId}`, {
    method: "DELETE",
    headers,
  });
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json({ error: errorMessage(body) }, { status: upstream.status });
  }
  return NextResponse.json(body);
}
