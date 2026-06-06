import { CalendarClock, ClipboardList, Fuel, History, ShieldAlert, Truck, UserRound } from "lucide-react";

import type {
  DriverHistory,
  FleetHistoryEvent,
  FleetHistoryLoadResult,
  VehicleHistory,
} from "../lib/fleet-history-api";
import { MonoCell } from "@/app/components/ui/MonoCell";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { DataSourceBadge } from "@/app/components/ui/DataSourceBadge";
import { EmptyStateInline } from "@/app/components/ui/EmptyState";

interface FleetHistoryBoardProps {
  result: FleetHistoryLoadResult;
}

export function FleetHistoryBoard({ result }: FleetHistoryBoardProps) {
  return (
    <section className="mt-6" aria-labelledby="fleet-history-title">
      <PageHeader
        eyebrow="Frota e Pessoas"
        title="Históricos separados"
        description="Trilhas operacionais independentes para viatura e motorista."
        actions={<DataSourceBadge source={result.source} message={result.message ?? undefined} />}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" aria-label="Historicos de frota">
        <VehicleTimeline history={result.vehicleHistory} />
        <DriverTimeline history={result.driverHistory} />
      </div>
    </section>
  );
}

function VehicleTimeline({ history }: { history: VehicleHistory }) {
  return (
    <article className="bg-surface border border-border rounded-lg overflow-hidden">
      <header className="history-header">
        <span className="queue-icon blue">
          <Truck size={16} />
        </span>
        <div>
          <h3><MonoCell size="sm">{history.vehicle.plate}</MonoCell></h3>
          <p>
            {statusLabel(history.vehicle.status)} · {formatNumber(history.vehicle.currentKm)} km
          </p>
        </div>
      </header>
      <Timeline events={history.items} relatedKey="driver_id" />
    </article>
  );
}

function DriverTimeline({ history }: { history: DriverHistory }) {
  return (
    <article className="bg-surface border border-border rounded-lg overflow-hidden">
      <header className="history-header">
        <span className="queue-icon green">
          <UserRound size={16} />
        </span>
        <div>
          <h3>{history.driver.fullName}</h3>
          <p>
            {statusLabel(history.driver.status)} · score {history.driver.score}
          </p>
        </div>
      </header>
      <Timeline events={history.items} relatedKey="vehicle_id" />
    </article>
  );
}

function Timeline({
  events,
  relatedKey,
}: {
  events: FleetHistoryEvent[];
  relatedKey: "driver_id" | "vehicle_id";
}) {
  if (events.length === 0) {
    return <EmptyStateInline label="Sem eventos registados." />;
  }

  return (
    <div className="history-list">
      {events.map((event) => (
        <div
          className="px-4 py-3 flex items-start gap-3 border-b border-border last:border-0"
          key={`${event.referenceType}:${event.referenceId}`}
        >
          <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${sourceToneClass(event.source)}`}>
            <EventIcon event={event} />
          </span>
          <div>
            <div className="flex items-baseline justify-between gap-2">
              <strong className="text-[13px]">{eventTypeLabel(event.eventType)}</strong>
              <time className="flex-none text-muted text-[12px]">{formatDateTime(event.occurredAt)}</time>
            </div>
            <p>{formatSummary(event.summary)}</p>
            <small>
              {sourceLabel(event.source)} · <MonoCell size="xs">{shortReference(event.referenceId)}</MonoCell>
              {typeof event.details[relatedKey] === "string"
                ? ` · ${relatedLabel(relatedKey)} ${shortReference(event.details[relatedKey])}`
                : ""}
            </small>
          </div>
        </div>
      ))}
    </div>
  );
}

function EventIcon({ event }: { event: FleetHistoryEvent }) {
  if (event.source.includes("fuel")) return <Fuel size={14} />;
  if (event.source === "checklists") return <ClipboardList size={14} />;
  if (event.source === "incidents" || event.source === "operations") {
    return <ShieldAlert size={14} />;
  }
  return <CalendarClock size={14} />;
}

function sourceToneClass(source: string) {
  if (source.includes("fuel")) return "bg-info";
  if (source === "checklists") return "bg-success";
  if (source === "incidents" || source === "operations") return "bg-warning";
  if (source === "audit") return "bg-info";
  return "bg-error";
}

function sourceLabel(source: string) {
  const labels: Record<string, string> = {
    audit: "Auditoria",
    checklists: "Checklist",
    fuel: "Combustível",
    fuel_operations: "Combustível interno",
    incidents: "Incidente",
    operations: "Operação",
    trips: "Viagem",
    workshop: "Oficina",
  };
  return labels[source] ?? source;
}

function eventTypeLabel(value: string) {
  return value
    .split(".")
    .slice(-1)[0]
    .replaceAll("_", " ")
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

function formatSummary(value: string) {
  return value.replaceAll("_", " ");
}

function relatedLabel(key: "driver_id" | "vehicle_id") {
  return key === "driver_id" ? "motorista" : "viatura";
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    active: "Activo",
    inactive: "Inactivo",
    maintenance: "Manutenção",
    retired: "Retirado",
    suspended: "Suspenso",
  };
  return labels[value] ?? value;
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Africa/Maputo",
  }).format(new Date(value));
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("pt-MZ", { maximumFractionDigits: 0 }).format(value);
}

function shortReference(value: unknown) {
  if (typeof value !== "string") return "-";
  return value.length > 12 ? value.slice(0, 8) : value;
}
