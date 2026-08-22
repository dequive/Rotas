import { upstreamFetch } from "@/app/lib/upstream-http";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

function errorMessage(body: unknown): string {
  if (body && typeof body === "object" && "error" in body) {
    const error = (body as { error?: { message?: string } }).error;
    if (error?.message) return error.message;
  }
  return "Código MFA inválido.";
}

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const upstream = await upstreamFetch(`${API_BASE}/api/v1/auth/mfa/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      challenge_token: payload.challengeToken,
      code: payload.code,
    }),
  });

  const data = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json({ error: errorMessage(data) }, { status: upstream.status });
  }

  const tokens = data as {
    access_token: string;
    refresh_token: string;
    user: { id: string; tenant_id: string; role: string; full_name: string };
  };
  const jar = await cookies();
  const isProduction = process.env.NODE_ENV === "production";
  const opts = {
    httpOnly: true,
    path: "/",
    maxAge: 60 * 60 * 8,
    secure: isProduction,
    sameSite: "lax" as const,
  };
  jar.set("rotas_access_token", tokens.access_token, opts);
  jar.set("rotas_refresh_token", tokens.refresh_token, opts);
  jar.set("rotas_tenant_id", String(tokens.user.tenant_id), opts);
  jar.set("rotas_user_id", String(tokens.user.id), opts);
  jar.set("rotas_role", tokens.user.role, opts);
  jar.set("rotas_full_name", tokens.user.full_name, opts);

  return NextResponse.json({ ok: true });
}
