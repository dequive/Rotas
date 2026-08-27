import { upstreamFetch } from "@/app/lib/upstream-http";
import { NextResponse } from "next/server";
import { refreshAccessToken, requireSession } from "../../../lib/auth";

const API_BASE =
  process.env.ROTAS_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function uploadFile(formData: FormData, accessToken: string, tenantId: string) {
  return upstreamFetch(`${API_BASE}/api/v1/files/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "X-Tenant-Id": tenantId,
    },
    body: formData,
    cache: "no-store",
  });
}

export async function POST(request: Request) {
  try {
    const session = await requireSession();
    const formData = await request.formData();

    const cloneFormData = () => {
      const fd = new FormData();
      for (const [key, value] of formData.entries()) {
        fd.append(key, value);
      }
      return fd;
    };

    let response = await uploadFile(cloneFormData(), session.accessToken, session.tenantId);

    if (response.status === 401) {
      const refreshedToken = await refreshAccessToken();
      if (refreshedToken) {
        const refreshedSession = await requireSession();
        response = await uploadFile(cloneFormData(), refreshedToken, refreshedSession.tenantId);
      }
    }

    const data = await response.json().catch(() => ({ detail: "Upload falhou." }));
    return NextResponse.json(data, { status: response.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Erro interno no upload de ficheiro.";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
