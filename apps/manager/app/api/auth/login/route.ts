import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { email, password } = (await req.json()) as { email: string; password: string };

  const upstream = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!upstream.ok) {
    const body = (await upstream.json().catch(() => ({}))) as { detail?: string };
    return NextResponse.json({ error: body.detail ?? "Credenciais inválidas." }, { status: 401 });
  }

  const data = (await upstream.json()) as {
    access_token?: string;
    refresh_token?: string;
    user?: { id: string; tenant_id: string; role: string; full_name: string };
    mfa_required?: boolean;
    mfa_challenge?: string;
    expires_in?: number;
  };

  if (data.mfa_required) {
    return NextResponse.json({
      ok: true,
      mfaRequired: true,
      mfaChallenge: data.mfa_challenge,
      expiresIn: data.expires_in,
    });
  }

  if (!data.access_token || !data.refresh_token || !data.user) {
    return NextResponse.json({ error: "Resposta de autenticação inválida." }, { status: 502 });
  }

  const jar = await cookies();
  // SEC-04 / D-12: Secure flag prevents cookie transmission over HTTP in production.
  // SameSite=lax required for Next.js App Router — Strict blocks cross-site navigations.
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
  jar.set("rotas_tenant_id", String(data.user.tenant_id), opts);
  jar.set("rotas_user_id", String(data.user.id), opts);
  jar.set("rotas_role", data.user.role, opts);
  jar.set("rotas_full_name", data.user.full_name, opts);

  return NextResponse.json({ ok: true });
}
