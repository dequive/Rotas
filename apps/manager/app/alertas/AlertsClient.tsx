"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Clock, ShieldAlert, CheckCircle, HelpCircle } from "lucide-react";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { EmptyState } from "@/app/components/ui/EmptyState";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import type { ExpiryAlert } from "@/app/components/DocumentExpiryBanner";
import type { Alert } from "@/app/lib/alerts-api";
import { updateAlertStatus } from "@/app/lib/alerts-api";

interface Props {
  expiryAlerts: ExpiryAlert[];
  systemAlerts: Alert[];
}

export function AlertsClient({ expiryAlerts, systemAlerts }: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"documentos" | "sistema">("documentos");
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const handleResolveAlert = async (alertId: string) => {
    setResolvingId(alertId);
    try {
      await updateAlertStatus(alertId, "resolved");
      router.refresh();
    } catch (err) {
      console.error("Erro ao resolver alerta:", err);
    } finally {
      setResolvingId(null);
    }
  };

  const pendingSystemAlerts = systemAlerts.filter(a => a.status === "pending" || a.status === "read");

  return (
    <div className="space-y-6">
      {/* Tabs Selector */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("documentos")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors duration-75 ${
            activeTab === "documentos"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          Documentos a Expirar ({expiryAlerts.length})
        </button>
        <button
          onClick={() => setActiveTab("sistema")}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors duration-75 ${
            activeTab === "sistema"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          Alertas de Sistema ({pendingSystemAlerts.length})
        </button>
      </div>

      {activeTab === "documentos" ? (
        <section>
          <SectionHeader title="Documentos a Expirar" count={expiryAlerts.length} />
          {expiryAlerts.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg overflow-hidden mt-3">
              <EmptyState
                icon={ShieldAlert}
                title="Sem alertas de documentos"
                description="Todos os documentos da frota e motoristas estão regulares."
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
              {expiryAlerts.map((alert, i) => (
                <div key={i} className="flex flex-col p-4 bg-surface border border-border rounded-lg shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    {alert.severity === "critical" ? (
                      <AlertTriangle size={16} className="text-error" />
                    ) : (
                      <Clock size={16} className="text-warning" />
                    )}
                    <span className="text-[13px] font-bold text-ink">
                      {alert.entity_type === "vehicle" ? "Viatura" : "Motorista"}
                    </span>
                  </div>
                  <strong className="text-[15px] text-ink mb-1">{alert.entity_name}</strong>
                  <span className="text-[13px] text-ink-2">{alert.document_type}</span>
                  <div className="mt-3 pt-3 border-t border-border flex justify-between items-center text-[12px]">
                    <span className="text-muted">Expira a:</span>
                    <strong className={alert.severity === "critical" ? "text-error" : "text-warning"}>
                      {alert.expires_at}
                    </strong>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section>
          <SectionHeader title="Alertas Ativos de Frota e Telemetria" count={pendingSystemAlerts.length} />
          {pendingSystemAlerts.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg overflow-hidden mt-3">
              <EmptyState
                icon={CheckCircle}
                title="Tudo operacional"
                description="Nenhum alerta crítico ou evento de telemetria pendente de resolução."
              />
            </div>
          ) : (
            <div className="space-y-3 mt-3">
              {pendingSystemAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-surface border border-border rounded-lg shadow-sm gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={alert.priority === "critical" ? "expired" : alert.priority === "high" ? "alerta" : "pending"} label={alert.priority.toUpperCase()} />
                      <span className="text-xs text-muted font-mono">{alert.alert_type}</span>
                    </div>
                    <h4 className="text-[15px] font-bold text-ink">{alert.title}</h4>
                    {alert.message && <p className="text-[13px] text-ink-2">{alert.message}</p>}
                    <span className="text-xs text-muted block">
                      Criado em: {new Date(alert.created_at).toLocaleString("pt-MZ")}
                    </span>
                  </div>
                  <button
                    onClick={() => handleResolveAlert(alert.id)}
                    disabled={resolvingId === alert.id}
                    className="inline-flex items-center justify-center h-9 px-4 text-[13px] font-semibold bg-surface border border-border rounded-md hover:bg-surface-2 transition-colors duration-75 disabled:opacity-50"
                  >
                    {resolvingId === alert.id ? "A resolver..." : "Resolver Alerta"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
