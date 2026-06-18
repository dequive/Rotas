import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("rotas_access_token")?.value;
  const isLogin = request.nextUrl.pathname === "/login";
  const isRegister = request.nextUrl.pathname === "/register";
  const isPasswordRecovery =
    request.nextUrl.pathname === "/forgot-password" ||
    request.nextUrl.pathname === "/reset-password";
  const isEmailVerification = request.nextUrl.pathname === "/verify-email";
  const isApi = request.nextUrl.pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();
  if (!token && !isLogin && !isRegister && !isPasswordRecovery && !isEmailVerification) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (token && (isLogin || isRegister || isPasswordRecovery)) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
