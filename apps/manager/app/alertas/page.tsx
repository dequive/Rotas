import { requireSession } from "@/app/lib/auth";
import { apiFetch } from "@/app/lib/api";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { AlertsClient } from "./AlertsClient";
import type { Alert } from "@/app/lib/alerts-api";
import type { ExpiryAlert } from "@/app/components/DocumentExpiryBanner";

async function getDocumentExpiry(): Promise<ExpiryAlert[]> {
  try {
    return await apiFetch<ExpiryAlert[]>(
      "/api/v1/analytics/document-expiry?horizon_days=30",
      { revalidate: 60 }
    );
  } catch {
    return [];
  }
}

async function getSystemAlerts(): Promise<{ data: Alert[]; error: string | null }> {
  try {
    const data = await apiFetch<Alert[]>("/api/v1/alerts", { revalidate: 5 });
    return { data, error: null };
  } catch (err) {
    return { data: [], error: err instanceof Error ? err.message : "Erro ao carregar alertas do sistema." };
  }
}

export default async function AlertasPage() {
  await requireSession();

  const [expiryAlerts, { data: systemAlerts, error: systemAlertsError }] = await Promise.all([
    getDocumentExpiry(),
    getSystemAlerts(),
  ]);

  return (
    <SidebarLayout active="alertas">
      <div className="w-full max-w-5xl mx-auto space-y-6">
        <PageHeader
          title="Central de Alertas"
          description="Avisos do sistema, vencimentos de documentos e eventos críticos da frota em tempo real."
        />

        <AlertsClient
          expiryAlerts={expiryAlerts}
          systemAlerts={systemAlerts}
          systemAlertsError={systemAlertsError}
        />
      </div>
    </SidebarLayout>
  );
}
