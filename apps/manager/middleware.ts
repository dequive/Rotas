import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("rotas_access_token")?.value;
  const isLogin = request.nextUrl.pathname === "/login";
  const isApi = request.nextUrl.pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();
  if (!token && !isLogin) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (token && isLogin) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
