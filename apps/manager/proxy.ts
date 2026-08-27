import { NextRequest, NextResponse } from "next/server";
import {
  refreshTokenPair,
  shouldRefreshAccessToken,
} from "./app/lib/auth-refresh";

const ACCESS_COOKIE = "rotas_access_token";
const REFRESH_COOKIE = "rotas_refresh_token";

function setRotatedCookies(
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
) {
  const options = {
    httpOnly: true,
    path: "/",
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
  };
  response.cookies.set(ACCESS_COOKIE, accessToken, {
    ...options,
    maxAge: 60 * 60 * 8,
  });
  response.cookies.set(REFRESH_COOKIE, refreshToken, {
    ...options,
    maxAge: 60 * 60 * 24 * 30,
  });
}

function requestHeadersWithRotatedCookies(
  request: NextRequest,
  accessToken: string,
  refreshToken: string,
): Headers {
  const requestHeaders = new Headers(request.headers);
  const cookies = new Map(
    request.cookies.getAll().map(({ name, value }) => [name, value]),
  );
  cookies.set(ACCESS_COOKIE, accessToken);
  cookies.set(REFRESH_COOKIE, refreshToken);
  requestHeaders.set(
    "cookie",
    [...cookies].map(([name, value]) => `${name}=${value}`).join("; "),
  );
  return requestHeaders;
}

export async function proxy(request: NextRequest) {
  let token = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  const isLogin = request.nextUrl.pathname === "/login";
  const isRegister = request.nextUrl.pathname === "/register";
  const isPasswordRecovery =
    request.nextUrl.pathname === "/forgot-password" ||
    request.nextUrl.pathname === "/reset-password";
  const isEmailVerification = request.nextUrl.pathname === "/verify-email";
  const isApi = request.nextUrl.pathname.startsWith("/api/");

  if (isApi) return NextResponse.next();

  if (token && refreshToken && shouldRefreshAccessToken(token)) {
    const rotated = await refreshTokenPair(refreshToken);
    if (rotated) {
      token = rotated.accessToken;
      if (isLogin || isRegister || isPasswordRecovery) {
        const response = NextResponse.redirect(new URL("/", request.url));
        setRotatedCookies(response, rotated.accessToken, rotated.refreshToken);
        return response;
      }

      const response = NextResponse.next({
        request: {
          headers: requestHeadersWithRotatedCookies(
            request,
            rotated.accessToken,
            rotated.refreshToken,
          ),
        },
      });
      setRotatedCookies(response, rotated.accessToken, rotated.refreshToken);
      return response;
    }

    token = undefined;
  }

  if (!token && !isLogin && !isRegister && !isPasswordRecovery && !isEmailVerification) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(REFRESH_COOKIE);
    return response;
  }
  if (token && (isLogin || isRegister || isPasswordRecovery)) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
