"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface AuthSession {
  accessToken: string;
  tenantId: string;
  userId: string;
  role: string;
  fullName: string;
}

async function getSession(): Promise<AuthSession | null> {
  const jar = await cookies();
  const token = jar.get("rotas_access_token")?.value;
  const tenantId = jar.get("rotas_tenant_id")?.value;
  const userId = jar.get("rotas_user_id")?.value;
  const role = jar.get("rotas_role")?.value;
  const fullName = jar.get("rotas_full_name")?.value;
  if (!token || !tenantId || !userId || !role) return null;
  return { accessToken: token, tenantId, userId, role, fullName: fullName ?? "" };
}

export async function requireSession(): Promise<AuthSession> {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

async function login(email: string, password: string): Promise<{ error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      return { error: body.detail ?? "Credenciais inválidas." };
    }
    const data = (await res.json()) as {
      access_token: string;
      user: { id: string; tenant_id: string; role: string; full_name: string };
    };
    const jar = await cookies();
    // SEC-04 / D-12: Secure flag prevents cookie transmission over HTTP in production.
    const isProduction = process.env.NODE_ENV === "production";
    const opts = {
      httpOnly: true,
      path: "/",
      maxAge: 60 * 60 * 8,
      secure: isProduction,
      sameSite: "lax" as const,
    };
    jar.set("rotas_access_token", data.access_token, opts);
    jar.set("rotas_tenant_id", String(data.user.tenant_id), opts);
    jar.set("rotas_user_id", String(data.user.id), opts);
    jar.set("rotas_role", data.user.role, opts);
    jar.set("rotas_full_name", data.user.full_name, opts);
    return {};
  } catch {
    return { error: "Servidor indisponível." };
  }
}

async function logout() {
  const jar = await cookies();
  jar.delete("rotas_access_token");
  jar.delete("rotas_tenant_id");
  jar.delete("rotas_user_id");
  jar.delete("rotas_role");
  jar.delete("rotas_full_name");
  redirect("/login");
}
