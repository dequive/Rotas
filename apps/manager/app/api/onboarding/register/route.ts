import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

type RegisterResponse = {
  access_token: string;
  refresh_token: string;
  owner: { id: string; role: string; full_name: string };
  tenant: { id: string; slug: string };
  verification_token?: string;
  verification_url?: string;
};

function errorMessage(body: unknown): string {
  if (body && typeof body === "object" && "error" in body) {
    const error = (body as { error?: { message?: string } }).error;
    if (error?.message) return error.message;
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: string }).detail;
    if (detail) return detail;
  }
  return "Não foi possível concluir o registo.";
}

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const upstream = await fetch(`${API_BASE}/api/v1/onboarding/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!upstream.ok) {
    const body = await upstream.json().catch(() => ({}));
    return NextResponse.json({ error: errorMessage(body) }, { status: upstream.status });
  }

  const data = (await upstream.json()) as RegisterResponse;
  const jar = await cookies();
  const isProduction = process.env.NODE_ENV === "production";
  const opts = {
    httpOnly: true,
    path: "/",
    maxAge: 60 * 60 * 8,
    secure: isProduction,
    sameSite: "lax" as const,
  };
  jar.set("rotas_access_token", data.access_token, opts);
  jar.set("rotas_refresh_token", data.refresh_token, opts);
  jar.set("rotas_tenant_id", data.tenant.id, opts);
  jar.set("rotas_user_id", data.owner.id, opts);
  jar.set("rotas_role", data.owner.role, opts);
  jar.set("rotas_full_name", data.owner.full_name, opts);

  return NextResponse.json({
    ok: true,
    tenant: data.tenant,
    verificationUrl: data.verification_token
      ? `/verify-email?token=${data.verification_token}`
      : data.verification_url,
  });
}
