import { NextRequest, NextResponse } from "next/server";
import { requireSession } from "@/app/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const session = await requireSession();
  const body = (await request.json()) as Record<string, unknown>;
  const res = await fetch(`${API_BASE}/api/v1/third-party/documents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      "X-Tenant-Id": session.tenantId,
    },
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as unknown;
  return NextResponse.json(data, { status: res.status });
}
