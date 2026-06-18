import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

function errorMessage(body: unknown): string {
  if (body && typeof body === "object" && "error" in body) {
    const error = (body as { error?: { message?: string } }).error;
    if (error?.message) return error.message;
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: string }).detail;
    if (detail) return detail;
  }
  return "Não foi possível iniciar a recuperação.";
}

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const upstream = await fetch(`${API_BASE}/api/v1/auth/password-reset/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json({ error: errorMessage(body) }, { status: upstream.status });
  }

  return NextResponse.json({
    ok: true,
    resetToken:
      body && typeof body === "object" && "reset_token" in body
        ? (body as { reset_token?: string }).reset_token
        : undefined,
    resetUrl:
      body && typeof body === "object" && "reset_url" in body
        ? (body as { reset_url?: string }).reset_url
        : undefined,
  });
}
