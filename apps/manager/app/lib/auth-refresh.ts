const API_BASE =
  process.env.ROTAS_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export interface RefreshedTokens {
  accessToken: string;
  refreshToken: string;
}

const refreshFlights = new Map<string, Promise<RefreshedTokens | null>>();

async function requestTokenRefresh(
  refreshToken: string,
): Promise<RefreshedTokens | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;

    const data = (await response.json()) as {
      access_token?: unknown;
      refresh_token?: unknown;
    };
    if (
      typeof data.access_token !== "string" ||
      data.access_token.length === 0 ||
      typeof data.refresh_token !== "string" ||
      data.refresh_token.length === 0
    ) {
      return null;
    }
    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    };
  } catch {
    return null;
  }
}

export function refreshTokenPair(
  refreshToken: string,
): Promise<RefreshedTokens | null> {
  const existing = refreshFlights.get(refreshToken);
  if (existing) return existing;

  const flight = requestTokenRefresh(refreshToken);
  refreshFlights.set(refreshToken, flight);
  void flight.finally(() => {
    if (refreshFlights.get(refreshToken) === flight) {
      refreshFlights.delete(refreshToken);
    }
  });
  return flight;
}

export function shouldRefreshAccessToken(
  accessToken: string,
  skewSeconds = 60,
): boolean {
  try {
    const parts = accessToken.split(".");
    if (parts.length !== 3) return true;

    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payload.padEnd(Math.ceil(payload.length / 4) * 4, "=");
    const decoded = JSON.parse(atob(padded)) as { exp?: unknown };
    return (
      typeof decoded.exp !== "number" ||
      decoded.exp <= Math.floor(Date.now() / 1000) + skewSeconds
    );
  } catch {
    return true;
  }
}
