import { requireSession } from "./lib/auth";
import { ControlTowerCommandCenter } from "./components/ControlTowerCommandCenter";
import { SidebarLayout } from "./components/SidebarLayout";
import { getApiConfig, loadBillingTrips } from "./lib/billing-api";
import { loadControlTower } from "./lib/control-tower-api";
import { loadFleetHistories } from "./lib/fleet-history-api";
import { loadFuelControlBoard } from "./lib/fuel-operations-api";
import { loadPendingTripOrders } from "./lib/trip-orders-api";
import { loadVehicles } from "./lib/vehicles-api";
import { loadDrivers } from "./lib/drivers-api";
import { loadContracts } from "./lib/contracts-api";

export default async function ManagerHome() {
  await requireSession();
  const apiConfig = getApiConfig();

  const [controlTower, fuelControlBoard, fleetHistories, billingData, pendingOrders, vehicles, drivers, contracts] =
    await Promise.all([
      loadControlTower(),
      loadFuelControlBoard(),
      loadFleetHistories(),
      loadBillingTrips(),
      loadPendingTripOrders(),
      loadVehicles(),
      loadDrivers(),
      loadContracts(),
    ]);

  return (
    <SidebarLayout active="operacao">
      <div className="w-full p-6 space-y-8">
        <ControlTowerCommandCenter
          controlTower={controlTower}
          fuelControlBoard={fuelControlBoard}
          fleetHistories={fleetHistories}
          billingTrips={billingData.trips}
          pendingOrders={pendingOrders}
          vehicles={vehicles}
          drivers={drivers}
          contracts={contracts}
          apiConfig={apiConfig}
        />

        {/* Quick Access Shortcuts */}
        <div className="pt-6 border-t border-border">
          <div className="mb-4">
            <span className="block text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-1">
              Acesso Rápido
            </span>
            <h2 className="text-lg font-bold text-foreground">Gestão Integrada</h2>
          </div>

          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <a
              href="/cobranca"
              className="flex flex-col p-4 bg-card border border-border rounded-xl hover:border-amber transition-colors no-underline group shadow-sm"
            >
              <span className="text-sm font-semibold text-foreground group-hover:text-amber-dark transition-colors">
                Faturação &amp; Cobrança
              </span>
              <span className="text-xs text-muted-foreground mt-1">Gerir faturas, documentos e AR</span>
            </a>
            <a
              href="/oficina/ordens-servico"
              className="flex flex-col p-4 bg-card border border-border rounded-xl hover:border-amber transition-colors no-underline group shadow-sm"
            >
              <span className="text-sm font-semibold text-foreground group-hover:text-amber-dark transition-colors">
                Oficina Auto
              </span>
              <span className="text-xs text-muted-foreground mt-1">Ordens de serviço e manutenções</span>
            </a>
            <a
              href="/manutencao"
              className="flex flex-col p-4 bg-card border border-border rounded-xl hover:border-amber transition-colors no-underline group shadow-sm"
            >
              <span className="text-sm font-semibold text-foreground group-hover:text-amber-dark transition-colors">
                Planos Preventivos
              </span>
              <span className="text-xs text-muted-foreground mt-1">Avisos e calendário de revisões</span>
            </a>
            <a
              href="/alertas"
              className="flex flex-col p-4 bg-card border border-border rounded-xl hover:border-amber transition-colors no-underline group shadow-sm"
            >
              <span className="text-sm font-semibold text-foreground group-hover:text-amber-dark transition-colors">
                Alertas de Documentos
              </span>
              <span className="text-xs text-muted-foreground mt-1">Caducidade de cartas e inspeções</span>
            </a>
          </section>
        </div>
      </div>
    </SidebarLayout>
  );
}
