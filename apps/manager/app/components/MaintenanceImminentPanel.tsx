import { Wrench } from "lucide-react";
import type { ImminentAlert } from "../lib/control-tower-api";
import { StatusBadge } from "./ui/StatusBadge";

interface Props {
  alerts: ImminentAlert[];
}

// Trigger type to marker color mapping (D-06 / UI-SPEC.md)
const TRIGGER_MARKER: Record<string, string> = {
  calendar: "history-marker orange",
  odometer: "history-marker cyan",
  overdue: "history-marker red",
};

const TRIGGER_LABEL: Record<string, string> = {
  calendar: "Por data",
  odometer: "Por odómetro",
  overdue: "Vencida",
};

function formatDueDate(iso: string): string {
  const d = new Date(iso);
  return `Vence em ${d.getUTCDate().toString().padStart(2, "0")}/${(d.getUTCMonth() + 1).toString().padStart(2, "0")}/${d.getUTCFullYear()}`;
}

function formatDueKm(km: number): string {
  return `Vence em ${km.toLocaleString("pt-MZ")} km`;
}

export function MaintenanceImminentPanel({ alerts }: Props) {
  return (
    <div className="fleet-compliance-panel">
      <div className="flex items-center gap-2 mb-1">
        <Wrench size={20} />
        <div>
          <h3 className="text-[14px] font-bold m-0">Manutenção Iminente</h3>
          <p className="text-xs text-muted m-0">
            Viaturas próximas do prazo de intervenção
          </p>
        </div>
        {alerts.length > 0 && (
          <StatusBadge status="alerta" label={String(alerts.length)} className="ml-auto" />
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state">
          <p className="font-bold">Sem manutenções iminentes</p>
          <p className="text-muted">
            Todas as viaturas estão dentro dos limites de intervenção.
          </p>
        </div>
      ) : (
        <ul className="fleet-compliance-list" role="list">
          {alerts.map((alert) => (
            <li className="fleet-compliance-item" key={alert.plan_id} role="listitem">
              <span className={TRIGGER_MARKER[alert.trigger_type] ?? "history-marker"} />
              <div>
                <strong className="text-[14px]">{alert.vehicle_plate}</strong>
                <span className="text-xs text-muted block">
                  {alert.plan_name}
                </span>
                <span className="text-xs text-muted">
                  {alert.trigger_type === "overdue" ? (
                    <StatusBadge status="expired" />
                  ) : alert.trigger_type === "calendar" && alert.next_due_at ? (
                    formatDueDate(alert.next_due_at)
                  ) : alert.next_due_km !== null ? (
                    formatDueKm(alert.next_due_km)
                  ) : null}{" "}
                  <StatusBadge status="pending" label={TRIGGER_LABEL[alert.trigger_type]} />
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
