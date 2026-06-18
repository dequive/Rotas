import { Wrench, Fuel, ClipboardList, AlertTriangle, CheckSquare, Calendar } from "lucide-react";
import Link from "next/link";
import { requireSession } from "@/app/lib/auth";
import { SidebarLayout } from "@/app/components/SidebarLayout";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { apiFetch } from "@/app/lib/api";
import type { VehicleHistoryResponse } from "@/app/lib/workshop-api";

interface PageProps {
  params: { id: string };
}

const EVENT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  maintenance_request: Wrench,
  work_order: ClipboardList,
  fuel: Fuel,
  checklist: CheckSquare,
  incident: AlertTriangle,
  schedule: Calendar,
};

const EVENT_LABELS: Record<string, string> = {
  maintenance_request: "Manutenção",
  work_order: "Ordem de Trabalho",
  fuel: "Abastecimento",
  checklist: "Checklist",
  incident: "Incidente",
  schedule: "Plano Preventivo",
};

function formatEventDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString("pt-MZ", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function VehicleHistoricoPage({ params }: PageProps) {
  await requireSession();

  let history: VehicleHistoryResponse = { events: [], next_cursor: null, total_count: 0 };
  try {
    history = await apiFetch<VehicleHistoryResponse>(
      `/api/v1/vehicles/${params.id}/history?limit=50`,
      { revalidate: 30 }
    );
  } catch {
    // fallback to empty state
  }

  return (
    <SidebarLayout active="viaturas">
      <div className="w-full space-y-6">
        <div className="flex items-center gap-3">
          <Link
            href="/viaturas"
            className="text-sm text-muted hover:text-ink transition-colors"
          >
            ← Viaturas
          </Link>
        </div>

        <PageHeader
          title="Histórico da Viatura"
          description={`${history.total_count} evento${history.total_count !== 1 ? "s" : ""} registado${history.total_count !== 1 ? "s" : ""}`}
        />

        {history.events.length === 0 ? (
          <div className="text-center py-16 text-muted">
            Nenhum evento encontrado para esta viatura.
          </div>
        ) : (
          <div className="relative">
            {/* Vertical timeline line */}
            <div
              className="absolute top-0 bottom-0 w-px"
              style={{ left: "23px", background: "var(--border)" }}
            />

            <div className="space-y-0">
              {history.events.map((event, index) => {
                const IconComponent = EVENT_ICONS[event.event_type] ?? Wrench;
                const label = EVENT_LABELS[event.event_type] ?? event.event_type;

                return (
                  <div
                    key={`${event.reference_id}-${index}`}
                    className="relative flex gap-6 pb-8"
                  >
                    {/* Icon circle */}
                    <div
                      className="relative z-10 flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center text-amber-500"
                      style={{
                        background: "var(--surface)",
                        border: "2px solid var(--amber)",
                      }}
                    >
                      <IconComponent className="w-5 h-5" />
                    </div>

                    {/* Content card */}
                    <div
                      className="flex-1 rounded-lg p-4"
                      style={{
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-4 mb-1">
                        <div>
                          <span
                            className="text-xs font-semibold uppercase tracking-wide"
                            style={{ color: "var(--muted)" }}
                          >
                            {label}
                          </span>
                          <h3
                            className="text-sm font-semibold mt-0.5"
                            style={{ color: "var(--ink)" }}
                          >
                            {event.title}
                          </h3>
                        </div>
                        <span
                          className="font-mono text-xs tabular-nums whitespace-nowrap"
                          style={{ color: "var(--muted)" }}
                        >
                          {formatEventDate(event.event_date)}
                        </span>
                      </div>

                      {event.description && (
                        <p
                          className="text-sm mt-1 line-clamp-2"
                          style={{ color: "var(--ink-2)" }}
                        >
                          {event.description}
                        </p>
                      )}

                      {event.odometer_reading != null && (
                        <p
                          className="text-xs font-mono tabular-nums mt-2"
                          style={{ color: "var(--muted)" }}
                        >
                          Odómetro: {event.odometer_reading.toLocaleString("pt-MZ")} km
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </SidebarLayout>
  );
}
