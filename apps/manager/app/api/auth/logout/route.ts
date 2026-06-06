import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST() {
  const jar = await cookies();
  jar.delete("rotas_access_token");
  jar.delete("rotas_refresh_token");
  jar.delete("rotas_tenant_id");
  jar.delete("rotas_user_id");
  jar.delete("rotas_role");
  jar.delete("rotas_full_name");
  return NextResponse.json({ ok: true });
}
