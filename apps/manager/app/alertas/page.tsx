import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { AlertsClient } from "./AlertsClient";
import { loadAlerts } from "@/app/lib/alerts-api";
import { apiFetch } from "@/app/lib/api";
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

export default async function AlertasPage() {
  await requireSession();

  // Load document expiry and system alerts in parallel
  const [expiryAlerts, systemAlerts] = await Promise.all([
    getDocumentExpiry(),
    loadAlerts(),
  ]);

  return (
    <SidebarLayout active="alertas">
      <div className="w-full max-w-5xl mx-auto space-y-6">
        <PageHeader 
          title="Central de Alertas" 
          description="Avisos do sistema, vencimentos de documentos e eventos críticos da frota em tempo real."
        />

        <AlertsClient expiryAlerts={expiryAlerts} systemAlerts={systemAlerts} />
      </div>
    </SidebarLayout>
  );
}
