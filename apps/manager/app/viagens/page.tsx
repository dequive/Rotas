import { Route } from "lucide-react";
import { requireSession } from "../lib/auth";
import { loadTrips } from "../lib/trips-api";
import { loadVehicles } from "../lib/vehicles-api";
import { loadDrivers } from "../lib/drivers-api";
import { loadContracts } from "../lib/contracts-api";
import { loadKnownRoutes } from "../lib/known-routes-api";
import { loadDriverDespachoTable } from "../lib/operations-admin-api";
import { SidebarLayout } from "../components/SidebarLayout";
import { TripFormModal } from "../components/TripFormModal";
import { TripActionButton } from "../components/TripActionButton";
import { StatusBadge } from "../components/ui/StatusBadge";
import { PageHeader } from "../components/ui/PageHeader";

// Map API trip status to StatusBadge status key
const TRIP_STATUS_MAP: Record<string, string> = {
  planned: "planeada",
  dispatched: "aguarda",
  in_progress: "in_progress",
  completed: "concluida",
  cancelled: "cancelada",
};

// Map billing status to StatusBadge status key
const BILLING_STATUS_MAP: Record<string, string> = {
  not_billable: "not_billable",
  pending_delivery_proof: "blocked",
  billable: "billable",
  billed: "billed",
};

// Labels for statuses not in StatusBadge defaults
const BILLING_LABEL_MAP: Record<string, string> = {
  pending_delivery_proof: "Sem descarga",
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("pt-MZ", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default async function ViagensPage() {
  await requireSession();
  const [trips, vehicles, drivers, contracts, knownRoutes, despachoResult] = await Promise.all([
    loadTrips(),
    loadVehicles(),
    loadDrivers(),
    loadContracts(),
    loadKnownRoutes(),
    loadDriverDespachoTable(),
  ]);

  return (
    <SidebarLayout active="viagens">
      <PageHeader
        eyebrow="Operações"
        title="Viagens"
        description={`${trips.length} viagens registadas`}
        actions={
          <TripFormModal
            vehicles={vehicles}
            drivers={drivers}
            contracts={contracts}
            knownRoutes={knownRoutes}
            despacheTiers={despachoResult.table.tiers}
          />
        }
      />

      <section className="panel">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Viatura</th>
                <th>Motorista</th>
                <th>Rota</th>
                <th>Carga</th>
                <th>Partida</th>
                <th>Estado</th>
                <th>Cobrança</th>
                <th>Acções</th>
              </tr>
            </thead>
            <tbody>
              {trips.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-row">Sem viagens registadas.</td>
                </tr>
              ) : (
                trips.map((t) => {
                  return (
                    <tr key={t.id}>
                      <td>
                        <strong>{t.vehicle_plate ?? "-"}</strong>
                      </td>
                      <td>{t.driver_name ?? "-"}</td>
                      <td>
                        <span className="route">
                          <Route size={14} />
                          {t.origin} → {t.destination}
                        </span>
                      </td>
                      <td>
                        {t.cargo_type ?? "-"}
                        <span className="muted-line">{t.load_state ?? ""}</span>
                      </td>
                      <td>{formatDate(t.actual_departure)}</td>
                      <td>
                        <StatusBadge status={TRIP_STATUS_MAP[t.status] ?? t.status} />
                      </td>
                      <td>
                        <StatusBadge
                          status={BILLING_STATUS_MAP[t.billing_status] ?? t.billing_status}
                          label={BILLING_LABEL_MAP[t.billing_status]}
                        />
                      </td>
                      <td className="action-cell">
                        <TripActionButton trip={t} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </SidebarLayout>
  );
}
