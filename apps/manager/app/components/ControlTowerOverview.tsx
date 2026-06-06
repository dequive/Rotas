import {
  AlertOctagon,
  ClipboardCheck,
  FileWarning,
  ReceiptText,
  ShieldAlert,
  ShieldCheck,
  Truck,
  Users,
} from "lucide-react";

import { DataSourceBadge } from "@/app/components/ui/DataSourceBadge";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { WorkQueue } from "@/app/components/ui/WorkQueue";

import type { ControlTower, ControlTowerLoadResult } from "../lib/control-tower-api";

interface ControlTowerOverviewProps {
  result: ControlTowerLoadResult;
}

export function ControlTowerOverview({ result }: ControlTowerOverviewProps) {
  const { tower } = result;
  const summary = tower.summary;

  return (
    <>
      <PageHeader
        eyebrow="Torre de Controlo"
        title="Operação diária"
        description="Autorizações de saída, viagens activas, incidentes e validações que exigem decisão."
        meta={
          <span className="text-[12px] text-muted">
            Data operacional: <strong className="text-ink">{formatDate(tower.date)}</strong>
          </span>
        }
      />

      <DataSourceBadge
        source={result.source}
        message={result.source !== "api" ? (result.message ?? undefined) : undefined}
      />

      <section
        className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3"
        aria-label="Indicadores da operação"
      >
        <KpiCard
          label="Ordens abertas"
          value={summary.tripOrdersOpen}
          icon={<ClipboardCheck size={16} />}
          semantic="info"
        />
        <KpiCard
          label="Autorizações pendentes"
          value={summary.dispatchPending}
          icon={<ShieldCheck size={16} />}
          semantic="warning"
        />
        <KpiCard
          label="Em execução"
          value={summary.tripsInExecution}
          icon={<Truck size={16} />}
          semantic="success"
        />
        <KpiCard
          label="Incidentes abertos"
          value={summary.incidentsOpen}
          icon={<AlertOctagon size={16} />}
          semantic="error"
        />
        <KpiCard
          label="Descargas a validar"
          value={summary.deliveryProofsPendingValidation}
          icon={<FileWarning size={16} />}
          semantic="warning"
        />
        <KpiCard
          label="Prontas a cobrar"
          value={summary.billingReady}
          icon={<ReceiptText size={16} />}
          semantic="info"
        />
      </section>

      <section
        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-[14px]"
        aria-label="Excepções operacionais"
      >
        <WorkQueue
          emptyLabel="Sem autorizações bloqueadas."
          icon={ShieldAlert}
          title="Autorização bloqueada"
          tone="red"
          items={tower.queues.blockedDispatch.map((item) => ({
            id: item.clearanceId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: item.blockedReason,
            meta: formatDateTime(item.updatedAt),
          }))}
        />
        <WorkQueue
          emptyLabel="Sem incidentes abertos."
          icon={AlertOctagon}
          title="Incidentes abertos"
          tone="orange"
          items={tower.queues.openIncidents.map((item) => ({
            id: item.incidentId,
            reference: `${shortReference(item.tripId)} · ${item.incidentType}`,
            title: item.route,
            detail: item.description,
            meta: `${severityLabel(item.severity)} · ${formatDateTime(item.occurredAt)}`,
          }))}
        />
        <WorkQueue
          emptyLabel="Sem provas pendentes."
          icon={FileWarning}
          title="Descargas por validar"
          tone="blue"
          items={tower.queues.pendingDeliveryValidation.map((item) => ({
            id: item.deliveryProofId,
            reference: item.documentNumber ?? shortReference(item.tripId),
            title: item.route,
            detail: "Prova recebida, aguarda validação do gestor.",
            meta: formatDateTime(item.deliveredAt),
          }))}
        />
        <WorkQueue
          emptyLabel="Sem excepções operacionais activas."
          icon={AlertOctagon}
          title="Excepções persistidas"
          tone="red"
          items={tower.queues.operationalExceptions.map((item) => ({
            id: item.exceptionId,
            reference: exceptionTypeLabel(item.exceptionType),
            title: item.title,
            detail: item.message,
            meta: `${severityLabel(item.severity)} · ${formatDateTime(item.createdAt)}`,
          }))}
        />
      </section>

      <section
        className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 px-3 py-2.5 bg-surface-2 border border-border rounded-md"
        aria-label="Capacidade operacional"
      >
        <FleetFact icon={Truck} label="Viaturas activas" value={summary.vehiclesActive} />
        <FleetFact icon={Users} label="Motoristas activos" value={summary.driversActive} />
        <FleetFact icon={ClipboardCheck} label="Viagens abertas hoje" value={summary.tripsCreatedToday} />
        <FleetFact icon={ShieldAlert} label="Dispensas activas" value={summary.activeWaivers} />
        <FleetFact icon={AlertOctagon} label="Autorizações bloqueadas" value={summary.dispatchBlocked} />
        <FleetFact
          icon={FileWarning}
          label="Docs viatura"
          value={summary.vehicleDocumentsExpiring}
        />
        <FleetFact
          icon={FileWarning}
          label="Docs motorista"
          value={summary.driverDocumentsExpiring}
        />
        <FleetFact
          icon={AlertOctagon}
          label="Excepções activas"
          value={summary.operationalExceptionsOpen}
        />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3" aria-label="Compliance documental">
        <WorkQueue
          emptyLabel="Sem documentos de viatura perto do vencimento."
          icon={Truck}
          title="Documentos de viatura"
          tone="orange"
          items={tower.queues.vehicleDocumentsExpiring.map((item) => ({
            id: item.id,
            reference: item.entityLabel,
            title: documentTypeLabel(item.documentType),
            detail: `Vence em ${item.daysUntilExpiry} dias.`,
            meta: formatDateOnly(item.validUntil),
          }))}
        />
        <WorkQueue
          emptyLabel="Sem documentos de motorista perto do vencimento."
          icon={Users}
          title="Documentos de motorista"
          tone="orange"
          items={tower.queues.driverDocumentsExpiring.map((item) => ({
            id: item.id,
            reference: item.entityLabel,
            title: documentTypeLabel(item.documentType),
            detail: `Vence em ${item.daysUntilExpiry} dias.`,
            meta: formatDateOnly(item.validUntil),
          }))}
        />
      </section>
    </>
  );
}

interface FleetFactProps {
  icon: typeof Truck;
  label: string;
  value: number;
}

function FleetFact({ icon: Icon, label, value }: FleetFactProps) {
  return (
    <div className="flex items-center gap-[6px] text-muted text-[12px]">
      <Icon size={16} />
      <span>{label}</span>
      <strong className="text-ink">{value}</strong>
    </div>
  );
}

function shortReference(value: string) {
  return value.length > 12 ? `TRP-${value.slice(0, 8)}` : value;
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

function exceptionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    fuel_low_stock: "Stock baixo",
    fuel_stock_variance: "Divergência de stock",
    vehicle_refuel_without_trip: "Abastecimento sem viagem",
  };
  return labels[value] ?? value;
}

function documentTypeLabel(value: string) {
  const labels: Record<string, string> = {
    driving_license: "Carta de condução",
    passport: "Passaporte",
    bi: "Bilhete de Identidade",
    inspection: "Inspecção",
    insurance: "Seguro",
    iav: "IAV",
    sign_tax: "Taxa de Letreiro",
    cargo_book: "Caderneta de Carga",
    international_license: "Licença Internacional",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatDateOnly(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Africa/Maputo",
  }).format(new Date(value));
}
