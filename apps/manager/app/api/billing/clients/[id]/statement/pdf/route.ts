import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.ROTAS_API_BASE_URL ?? "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const cookieStore = await cookies();
  // Cookie names match auth.ts: rotas_access_token + rotas_tenant_id
  const accessToken = cookieStore.get("rotas_access_token")?.value;
  const tenantId = cookieStore.get("rotas_tenant_id")?.value;

  if (!accessToken) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  // Forward as_of query param if present
  const { searchParams } = new URL(request.url);
  const asOf = searchParams.get("as_of");
  const backendUrl = `${API_BASE}/api/v1/billing/clients/${id}/statement/pdf${
    asOf ? `?as_of=${encodeURIComponent(asOf)}` : ""
  }`;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
        Accept: "application/pdf",
      },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "backend_unavailable" }, { status: 503 });
  }

  if (!backendResponse.ok) {
    return NextResponse.json(
      { error: "backend_error", status: backendResponse.status },
      { status: backendResponse.status }
    );
  }

  const pdfBytes = await backendResponse.arrayBuffer();

  return new NextResponse(pdfBytes, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="extrato_${id}.pdf"`,
      "Cache-Control": "no-store",
    },
  });
}
