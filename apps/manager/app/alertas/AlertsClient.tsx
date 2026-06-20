"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Clock, ShieldAlert, CheckCircle } from "lucide-react";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { EmptyState } from "@/app/components/ui/EmptyState";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import type { ExpiryAlert } from "@/app/components/DocumentExpiryBanner";
import type { Alert } from "@/app/lib/alerts-api";
import { resolveAlert, acknowledgeAlert } from "./actions";

interface Props {
  expiryAlerts: ExpiryAlert[];
  systemAlerts: Alert[];
  systemAlertsError: string | null;
}

type SystemView = "ativos" | "reconhecidos" | "resolvidos";

export function AlertsClient({ expiryAlerts, systemAlerts, systemAlertsError }: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"documentos" | "sistema">("documentos");
  const [systemView, setSystemView] = useState<SystemView>("ativos");
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);

  const handleResolveAlert = async (alertId: string) => {
    setResolvingId(alertId);
    setResolveError(null);
    const result = await resolveAlert(alertId);
    if (result.ok) {
      router.refresh();
    } else {
      setResolveError(result.error);
    }
    setResolvingId(null);
  };

  const handleAcknowledgeAlert = async (alertId: string) => {
    setAcknowledgingId(alertId);
    setResolveError(null);
    const result = await acknowledgeAlert(alertId);
    if (result.ok) {
      router.refresh();
    } else {
      setResolveError(result.error);
    }
    setAcknowledgingId(null);
  };

  // Bucket alerts by sub-view
  const ativosAlerts = systemAlerts.filter((a) => a.status === "pending");
  const reconhecidosAlerts = systemAlerts.filter(
    (a) => a.status === "read" || a.status === "dismissed"
  );
  const resolvidosAlerts = systemAlerts.filter((a) => a.status === "resolved");

  const activeSystemAlerts =
    systemView === "ativos"
      ? ativosAlerts
      : systemView === "reconhecidos"
      ? reconhecidosAlerts
      : resolvidosAlerts;

  const pendingCount = ativosAlerts.length;

  const systemViewLabels: Record<SystemView, string> = {
    ativos: `Ativos (${ativosAlerts.length})`,
    reconhecidos: `Reconhecidos (${reconhecidosAlerts.length})`,
    resolvidos: `Resolvidos (${resolvidosAlerts.length})`,
  };

  const emptyMessages: Record<SystemView, { title: string; description: string }> = {
    ativos: {
      title: "Tudo operacional",
      description: "Nenhum alerta crítico ou evento de telemetria pendente de atenção.",
    },
    reconhecidos: {
      title: "Sem alertas reconhecidos",
      description: "Alertas reconhecidos mas não resolvidos aparecem aqui.",
    },
    resolvidos: {
      title: "Sem alertas resolvidos",
      description: "Alertas resolvidos aparecem aqui para histórico.",
    },
  };

  return (
    <div className="space-y-6">
      {/* Outer Tab Selector */}
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
          Alertas de Sistema ({pendingCount})
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
                <div
                  key={i}
                  className="flex flex-col p-4 bg-surface border border-border rounded-lg shadow-sm"
                >
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
                    <strong
                      className={
                        alert.severity === "critical" ? "text-error" : "text-warning"
                      }
                    >
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
          <SectionHeader
            title="Alertas de Sistema"
            count={activeSystemAlerts.length}
          />

          {/* System view filter buttons */}
          <div className="flex gap-1 mt-3 mb-4">
            {(["ativos", "reconhecidos", "resolvidos"] as const).map((view) => (
              <button
                key={view}
                onClick={() => setSystemView(view)}
                className={`px-3 py-1.5 text-[12px] font-semibold rounded-md border transition-colors duration-75 capitalize ${
                  systemView === view
                    ? "bg-amber-light border-amber text-amber-dark"
                    : "bg-surface border-border text-muted hover:text-ink"
                }`}
                style={
                  systemView === view
                    ? {
                        backgroundColor: "var(--amber-light)",
                        borderColor: "var(--amber)",
                        color: "var(--amber-dark)",
                      }
                    : undefined
                }
              >
                {systemViewLabels[view]}
              </button>
            ))}
          </div>

          {/* Error banner */}
          {(systemAlertsError || resolveError) && (
            <div className="mb-4 p-3 bg-error-bg border border-error/30 rounded-md text-xs font-semibold text-error">
              {resolveError ?? systemAlertsError}
            </div>
          )}

          {!systemAlertsError && activeSystemAlerts.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg overflow-hidden">
              <EmptyState
                icon={CheckCircle}
                title={emptyMessages[systemView].title}
                description={emptyMessages[systemView].description}
              />
            </div>
          ) : !systemAlertsError ? (
            <div className="space-y-3">
              {activeSystemAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-surface border border-border rounded-lg shadow-sm gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge
                        status={
                          alert.priority === "critical" || alert.priority === "high"
                            ? "expired"
                            : "alerta"
                        }
                        label={alert.priority.toUpperCase()}
                      />
                      <span className="text-xs text-muted font-mono">{alert.alert_type}</span>
                    </div>
                    <h4 className="text-[13px] font-bold text-ink">{alert.title}</h4>
                    {alert.message && (
                      <p className="text-[12px] text-ink-2">{alert.message}</p>
                    )}
                    <span className="text-xs text-muted block font-mono">
                      {new Date(alert.created_at).toLocaleString("pt-MZ")}
                    </span>
                  </div>

                  {/* Action buttons per sub-view */}
                  <div className="flex items-center gap-2 shrink-0">
                    {systemView === "ativos" && (
                      <button
                        onClick={() => handleAcknowledgeAlert(alert.id)}
                        disabled={
                          resolvingId === alert.id || acknowledgingId === alert.id
                        }
                        className="inline-flex items-center justify-center h-8 px-3 text-[12px] font-semibold bg-surface border border-border rounded-md hover:bg-surface-2 transition-colors duration-75 disabled:opacity-50"
                      >
                        {acknowledgingId === alert.id ? "A reconhecer..." : "Reconhecer"}
                      </button>
                    )}
                    {systemView !== "resolvidos" && (
                      <button
                        onClick={() => handleResolveAlert(alert.id)}
                        disabled={
                          resolvingId === alert.id || acknowledgingId === alert.id
                        }
                        className="inline-flex items-center justify-center h-8 px-3 text-[12px] font-semibold bg-surface border border-border rounded-md hover:bg-surface-2 transition-colors duration-75 disabled:opacity-50"
                      >
                        {resolvingId === alert.id ? "A resolver..." : "Resolver"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      )}
    </div>
  );
}
