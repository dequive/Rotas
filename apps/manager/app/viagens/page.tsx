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

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  planned: { label: "Planeada", tone: "blue" },
  dispatched: { label: "Despachada", tone: "orange" },
  in_progress: { label: "Em curso", tone: "cyan" },
  completed: { label: "Concluída", tone: "green" },
  cancelled: { label: "Cancelada", tone: "red" },
};

const BILLING_LABEL: Record<string, { label: string; tone: string }> = {
  not_billable: { label: "N/A", tone: "blue" },
  pending_delivery_proof: { label: "Sem descarga", tone: "red" },
  billable: { label: "A cobrar", tone: "cyan" },
  billed: { label: "Cobrado", tone: "green" },
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
      <div className="page-header">
        <div>
          <h1>Viagens</h1>
          <p>{trips.length} viagens registadas</p>
        </div>
        <TripFormModal
          vehicles={vehicles}
          drivers={drivers}
          contracts={contracts}
          knownRoutes={knownRoutes}
          despacheTiers={despachoResult.table.tiers}
        />
      </div>

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
                  const statusMeta = STATUS_LABEL[t.status] ?? { label: t.status, tone: "blue" };
                  const billingMeta = BILLING_LABEL[t.billing_status] ?? { label: t.billing_status, tone: "blue" };
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
                        <span className={`badge ${statusMeta.tone}`}>{statusMeta.label}</span>
                      </td>
                      <td>
                        <span className={`badge ${billingMeta.tone}`}>{billingMeta.label}</span>
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
