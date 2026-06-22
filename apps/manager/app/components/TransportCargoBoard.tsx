import {
  AlertOctagon,
  ClipboardCheck,
  FileWarning,
  LucideIcon,
  Route,
  ShieldAlert,
  Truck,
} from "lucide-react";
import type { ReactNode } from "react";

import type { ControlTowerLoadResult } from "../lib/control-tower-api";
import { TransportCargoActions } from "./TransportCargoActions";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { EmptyStateInline } from "@/app/components/ui/EmptyState";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface TransportCargoBoardProps {
  apiConfig: ApiConfig;
  result: ControlTowerLoadResult;
}

export function TransportCargoBoard({ apiConfig, result }: TransportCargoBoardProps) {
  const { summary, queues } = result.tower;

  return (
    <section className="mt-6" aria-labelledby="transport-cargo-title">
      <PageHeader
        eyebrow="Transporte e Carga"
        title="Execução de transporte"
        description="Ordens, autorizações de saída, viagens, incidentes e prova de entrega no mesmo circuito."
        actions={
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-[12px] text-muted">
              <Route size={14} />
              Em fechamento
            </span>
            {apiConfig.tenantId ? (
              <TransportCargoActions
                action={{ kind: "evaluate-delivery-sla" }}
                apiConfig={apiConfig}
                label="Avaliar SLA"
              />
            ) : null}
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <KpiCard
          icon={<ClipboardCheck size={16} />}
          label="Ordens abertas"
          value={summary.tripOrdersOpen}
          semantic="default"
        />
        <KpiCard
          icon={<ShieldAlert size={16} />}
          label="Autorização pendente"
          value={summary.dispatchPending}
          semantic={summary.dispatchPending > 0 ? "warning" : "default"}
        />
        <KpiCard
          icon={<Truck size={16} />}
          label="Em execução"
          value={summary.tripsInExecution}
          semantic="info"
        />
        <KpiCard
          icon={<AlertOctagon size={16} />}
          label="Incidentes"
          value={summary.incidentsOpen}
          semantic={summary.incidentsOpen > 0 ? "error" : "default"}
        />
        <KpiCard
          icon={<FileWarning size={16} />}
          label="Descargas a validar"
          value={summary.deliveryProofsPendingValidation}
          semantic={summary.deliveryProofsPendingValidation > 0 ? "warning" : "default"}
        />
        <KpiCard
          icon={<FileWarning size={16} />}
          label="Em disputa"
          value={queues.disputedDeliveryProofs.length}
          semantic={queues.disputedDeliveryProofs.length > 0 ? "error" : "default"}
        />
      </div>

      <div className="grid gap-3 mt-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }} aria-label="Filas de trabalho de transporte">
        <TransportQueue
          emptyLabel="Sem autorizações pendentes."
          icon={ShieldAlert}
          title="Autorização pendente"
          tone="orange"
          items={queues.pendingDispatch.map((item) => ({
            id: item.clearanceId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: dispatchStatusLabel(item.clearanceStatus),
            meta: formatDateTime(item.updatedAt),
            action:
              item.clearanceStatus === "approved" ? (
                <TransportCargoActions
                  action={{ kind: "dispatch-trip", tripId: item.tripId }}
                  apiConfig={apiConfig}
                  label="Iniciar saída"
                />
              ) : (
                <TransportCargoActions
                  action={{ kind: "approve-dispatch-clearance", tripId: item.tripId }}
                  apiConfig={apiConfig}
                  label="Aprovar saída"
                />
              ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem autorizações bloqueadas."
          icon={ShieldAlert}
          title="Autorização bloqueada"
          tone="red"
          items={queues.blockedDispatch.map((item) => ({
            id: item.clearanceId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: item.blockedReason,
            meta: formatDateTime(item.updatedAt),
            action: (
              <TransportCargoActions
                action={{ kind: "approve-dispatch-clearance", tripId: item.tripId }}
                apiConfig={apiConfig}
                label="Reavaliar saída"
              />
            ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem checklists falhados."
          icon={ClipboardCheck}
          title="Checklists falhados"
          tone="orange"
          items={queues.failedChecklists.map((item) => ({
            id: item.checklistId,
            reference: checklistTypeLabel(item.type),
            title: item.vehiclePlate ?? item.driverName ?? "Recurso não indicado",
            detail: compactPair("Motorista", item.driverName),
            meta: item.completedAt ? formatDateTime(item.completedAt) : "Sem data de conclusão",
            action: (
              <TransportCargoActions
                action={{ kind: "resolve-checklist-failure", checklistId: item.checklistId }}
                apiConfig={apiConfig}
                label="Resolver checklist"
              />
            ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem incidentes abertos."
          icon={AlertOctagon}
          title="Incidentes abertos"
          tone="red"
          items={queues.openIncidents.map((item) => ({
            id: item.incidentId,
            reference: `${shortReference(item.tripId)} · ${incidentTypeLabel(item.incidentType)}`,
            title: item.route,
            detail: item.description,
            meta: `${severityLabel(item.severity)} · ${formatDateTime(item.occurredAt)}`,
            action: (
              <TransportCargoActions
                action={{
                  kind: "resolve-incident",
                  tripId: item.tripId,
                  incidentId: item.incidentId,
                }}
                apiConfig={apiConfig}
                label="Resolver incidente"
              />
            ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem atrasos de entrega."
          icon={AlertOctagon}
          title="Atrasos SLA"
          tone="red"
          items={queues.delayedTrips.map((item) => ({
            id: item.tripId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: compactPair("Motorista", item.driverName),
            meta: `${delayLabel(item.delayMinutes)} · ${formatDateTime(item.plannedArrival)}`,
          }))}
        />
        <TransportQueue
          emptyLabel="Sem provas pendentes."
          icon={FileWarning}
          title="Descargas por validar"
          tone="blue"
          items={queues.pendingDeliveryValidation.map((item) => ({
            id: item.deliveryProofId,
            reference: item.documentNumber ?? shortReference(item.tripId),
            title: item.route,
            detail: "Prova recebida, aguarda validação.",
            meta: formatDateTime(item.deliveredAt),
            action: (
              <TransportCargoActions
                action={{
                  kind: "validate-delivery-proof",
                  tripId: item.tripId,
                  deliveryProofId: item.deliveryProofId,
                }}
                apiConfig={apiConfig}
                label="Validar descarga"
              />
            ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem descargas em disputa."
          icon={FileWarning}
          title="Descargas em disputa"
          tone="orange"
          items={queues.disputedDeliveryProofs.map((item) => ({
            id: item.deliveryProofId,
            reference: item.documentNumber ?? shortReference(item.tripId),
            title: item.route,
            detail: billingStatusLabel(item.billingStatus),
            meta: formatDateTime(item.deliveredAt),
            action: apiConfig.tenantId ? (
              <div className="flex items-center gap-2">
                <TransportCargoActions
                  action={{
                    kind: "resolve-delivery-dispute",
                    tripId: item.tripId,
                    deliveryProofId: item.deliveryProofId,
                    outcome: "validated",
                  }}
                  apiConfig={apiConfig}
                  label="Aceitar"
                />
                <TransportCargoActions
                  action={{
                    kind: "resolve-delivery-dispute",
                    tripId: item.tripId,
                    deliveryProofId: item.deliveryProofId,
                    outcome: "rejected",
                  }}
                  apiConfig={apiConfig}
                  label="Rejeitar"
                />
              </div>
            ) : (
              <small className="text-muted text-sm">Acções indisponíveis sem API</small>
            ),
          }))}
        />
        <TransportQueue
          emptyLabel="Sem viagens prontas para fecho."
          icon={Route}
          title="Fecho operacional"
          tone="green"
          items={queues.operationalCloseCandidates.map((item) => ({
            id: item.tripId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: closeReadinessLabel(item.readiness),
            meta: `${tripStatusLabel(item.status)} · ${formatDateTime(item.updatedAt)}`,
            action:
              item.readiness === "ready" ? (
                <TransportCargoActions
                  action={{ kind: "operational-close", tripId: item.tripId }}
                  apiConfig={apiConfig}
                  label="Fechar viagem"
                />
              ) : (
                <small className="text-muted text-sm">Resolva bloqueios antes do fecho</small>
              ),
          }))}
        />
      </div>
    </section>
  );
}

interface TransportQueueItem {
  action?: ReactNode;
  id: string;
  reference: string;
  title: string;
  detail: string;
  meta: string;
}

interface TransportQueueProps {
  emptyLabel: string;
  icon: LucideIcon;
  items: TransportQueueItem[];
  title: string;
  tone: string;
}

const queueIconCls: Record<string, string> = {
  orange: "w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-warning-bg text-warning",
  red: "w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-error-bg text-error",
  blue: "w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-[#dbeafe] text-[#2563eb]",
  green: "w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-success-bg text-success",
};

function TransportQueue({ emptyLabel, icon: Icon, items, title, tone }: TransportQueueProps) {
  const iconCls = queueIconCls[tone] ?? "w-[30px] h-[30px] rounded-md inline-flex items-center justify-center flex-shrink-0 bg-surface-2 text-muted";
  return (
    <article className="bg-surface border border-border rounded-lg overflow-hidden">
      <header className="flex items-center gap-2.5 px-3.5 py-3 border-b border-border">
        <span className={iconCls}>
          <Icon size={16} />
        </span>
        <div>
          <h2 className="text-[14px] font-semibold m-0">{title}</h2>
          <p className="mt-0.5 text-muted text-[12px] m-0">{items.length} pendentes</p>
        </div>
      </header>
      <div>
        {items.length === 0 ? (
          <EmptyStateInline label={emptyLabel} />
        ) : null}
        {items.map((item) => (
          <div className="grid gap-0.5 py-2 border-t border-border px-3.5 first:border-t-0" key={item.id}>
            <strong className="text-[#2563eb] text-[12px] [overflow-wrap:anywhere]">{item.reference}</strong>
            <span className="text-[13px] font-bold [overflow-wrap:anywhere]">{item.title}</span>
            <small className="text-muted text-[12px] [overflow-wrap:anywhere]">{item.detail}</small>
            <em className="text-muted text-[12px] [overflow-wrap:anywhere] not-italic">{item.meta}</em>
            {item.action}
          </div>
        ))}
      </div>
    </article>
  );
}

function shortReference(value: string) {
  return value.length > 12 ? `TRP-${value.slice(0, 8)}` : value;
}

function compactPair(label: string, value: string | null) {
  return value ? `${label}: ${value}` : `${label} não indicado`;
}

function delayLabel(minutes: number) {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remaining = minutes % 60;
    return remaining > 0 ? `${hours}h ${remaining}min de atraso` : `${hours}h de atraso`;
  }
  return `${minutes}min de atraso`;
}

function dispatchStatusLabel(value: string) {
  const labels: Record<string, string> = {
    pending: "Aguarda autorização de saída",
    approved: "Autorização aprovada, aguarda saída",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function severityLabel(value: string) {
  const labels: Record<string, string> = {
    critical: "Crítico",
    high: "Alto",
    medium: "Médio",
    low: "Baixo",
  };
  return labels[value] ?? value;
}

function incidentTypeLabel(value: string) {
  const labels: Record<string, string> = {
    breakdown: "Avaria",
    delay: "Atraso",
    accident: "Acidente",
    cargo_issue: "Carga",
  };
  return labels[value] ?? value;
}

function tripStatusLabel(value: string) {
  const labels: Record<string, string> = {
    arrived: "Chegada registada",
    delivered: "Entregue",
    incident: "Em incidente",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function closeReadinessLabel(value: string) {
  const labels: Record<string, string> = {
    ready: "Pronta para fecho operacional",
    blocked_incident: "Incidente alto/crítico ainda aberto",
    needs_validated_pod_or_waiver: "Exige POD validado ou dispensa activa",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function checklistTypeLabel(value: string) {
  const labels: Record<string, string> = {
    pre_trip: "Pré-viagem",
    post_trip: "Pós-viagem",
    safety: "Segurança",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function billingStatusLabel(value: string) {
  const labels: Record<string, string> = {
    pending_delivery_proof: "Sem prova de descarga validada",
    pending_delivery_validation: "Descarga em validação",
    billable: "Pode seguir para cobrança após resolução",
    billed: "Já consta em cobrança",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Africa/Maputo",
  }).format(new Date(value));
}
