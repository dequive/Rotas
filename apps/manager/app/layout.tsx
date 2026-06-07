import "./globals.css";
import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { LimitWarningBanner, type TenantLimits } from "@/app/components/LimitWarningBanner";
import { DocumentExpiryBanner, type ExpiryAlert } from "@/app/components/DocumentExpiryBanner";

export const metadata: Metadata = {
  title: "ROTAS — Gestão de Frotas",
  description: "Dashboard operacional ROTAS — gestão de frotas, viagens e logística",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Safe limits fetch — reads session cookies without redirecting.
 *
 * Unlike apiFetch(), this helper returns null instead of throwing/redirecting
 * when the user is unauthenticated. This keeps the root layout safe for the
 * /login page and any other unauthenticated routes.
 *
 * Cache strategy: revalidate: 30 matches the Redis TTL on the backend (INFRA-03 / D-15).
 */
async function getTenantLimits(): Promise<TenantLimits | null> {
  try {
    const jar = await cookies();
    const accessToken = jar.get("rotas_access_token")?.value;
    const tenantId = jar.get("rotas_tenant_id")?.value;

    // No session — unauthenticated route (e.g. /login). Hide banner silently.
    if (!accessToken || !tenantId) return null;

    const res = await fetch(`${API_BASE}/api/v1/tenants/me/limits`, {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        "X-Tenant-Id": tenantId,
      },
      next: { revalidate: 30 },
    });

    if (!res.ok) return null;
    return (await res.json()) as TenantLimits;
  } catch {
    // Banner is non-critical — if fetch fails, hide it rather than crash layout
    return null;
  }
}

/**
 * Safe document expiry fetch — returns [] instead of throwing when unauthenticated.
 *
 * Fetches GET /api/v1/analytics/document-expiry?horizon_days=30.
 * Cache strategy: revalidate: 60 — documents renew slowly, 60s is sufficient.
 */
async function getDocumentExpiry(): Promise<ExpiryAlert[]> {
  try {
    const jar = await cookies();
    const accessToken = jar.get("rotas_access_token")?.value;
    const tenantId = jar.get("rotas_tenant_id")?.value;

    if (!accessToken || !tenantId) return [];

    const res = await fetch(
      `${API_BASE}/api/v1/analytics/document-expiry?horizon_days=30`,
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
          "X-Tenant-Id": tenantId,
        },
        next: { revalidate: 60 },
      }
    );

    if (!res.ok) return [];
    return (await res.json()) as ExpiryAlert[];
  } catch {
    return [];
  }
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [limits, expiryAlerts] = await Promise.all([
    getTenantLimits(),
    getDocumentExpiry(),
  ]);

  return (
    <html lang="pt">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <LimitWarningBanner limits={limits} />
        <DocumentExpiryBanner alerts={expiryAlerts} />
        {children}
      </body>
    </html>
  );
}
