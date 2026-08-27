import { upstreamFetch } from "@/app/lib/upstream-http";
import { NextResponse } from "next/server";

import { refreshAccessToken, requireSession } from "../../../../lib/auth";

const API_BASE =
  process.env.ROTAS_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function fetchFile(id: string, accessToken: string, tenantId: string) {
  return upstreamFetch(`${API_BASE}/api/v1/files/${encodeURIComponent(id)}/download`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "X-Tenant-Id": tenantId,
    },
    cache: "no-store",
  });
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await requireSession();
  const { id } = await params;
  let response = await fetchFile(id, session.accessToken, session.tenantId);

  if (response.status === 401) {
    const refreshedToken = await refreshAccessToken();
    if (refreshedToken) {
      const refreshedSession = await requireSession();
      response = await fetchFile(id, refreshedToken, refreshedSession.tenantId);
    }
  }

  if (!response.ok) {
    return NextResponse.json(
      { detail: response.status === 404 ? "Ficheiro não encontrado." : "Não foi possível obter o ficheiro." },
      { status: response.status },
    );
  }

  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  const contentDisposition = response.headers.get("content-disposition");
  if (contentType) headers.set("content-type", contentType);
  if (contentDisposition) headers.set("content-disposition", contentDisposition);
  headers.set("cache-control", "private, no-store");

  return new Response(response.body, { status: 200, headers });
}
