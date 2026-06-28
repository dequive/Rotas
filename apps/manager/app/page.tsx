import {
  AlertTriangle,
  BadgeCheck,
  ClipboardCheck,
  FileClock,
  FileText,
  ReceiptText,
  Route,
  Truck,
} from "lucide-react";

import { requireSession } from "./lib/auth";
import { ControlTowerOverview } from "./components/ControlTowerOverview";
import { CostMarginBoard } from "./components/CostMarginBoard";
import { FleetComplianceBoard } from "./components/FleetComplianceBoard";
import { FleetHistoryBoard } from "./components/FleetHistoryBoard";
import { FuelControlBoard } from "./components/FuelControlBoard";
import { SidebarLayout } from "./components/SidebarLayout";
import { TmsExecutiveDashboard } from "./components/TmsExecutiveDashboard";
import { TransportCargoBoard } from "./components/TransportCargoBoard";
import {
  getApiConfig,
  loadBillingTrips,
} from "./lib/billing-api";
import { loadControlTower } from "./lib/control-tower-api";
import { loadFleetHistories } from "./lib/fleet-history-api";
import { loadFuelControlBoard } from "./lib/fuel-operations-api";
import { loadPendingTripOrders } from "./lib/trip-orders-api";
import { loadVehicles } from "./lib/vehicles-api";
import { loadDrivers } from "./lib/drivers-api";
import { DispatchBoard } from "./components/DispatchBoard";


export default async function ManagerHome() {
  await requireSession();
  const controlTower = await loadControlTower();
  const fuelControlBoard = await loadFuelControlBoard();
  const fleetHistories = await loadFleetHistories();
  const { trips } = await loadBillingTrips();
  const apiConfig = getApiConfig();

  const [pendingOrders, vehicles, drivers] = await Promise.all([
    loadPendingTripOrders(),
    loadVehicles(),
    loadDrivers()
  ]);

  return (
    <SidebarLayout active="operacao">
      <div className="w-full">
        <TmsExecutiveDashboard controlTower={controlTower} billingTrips={trips} />
        <ControlTowerOverview result={controlTower} />
        <DispatchBoard pendingOrders={pendingOrders} vehicles={vehicles} drivers={drivers} />
        <TransportCargoBoard apiConfig={apiConfig} result={controlTower} />
        <FleetComplianceBoard apiConfig={apiConfig} result={controlTower} />
        <FleetHistoryBoard result={fleetHistories} />
        <FuelControlBoard result={fuelControlBoard} />
        <CostMarginBoard apiConfig={apiConfig} result={controlTower} />

        <div className="px-6 mt-8 mb-4 flex items-center justify-between">
          <div>
            <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted mb-1">
              Atalhos
            </span>
            <h2 className="text-[20px] font-bold text-ink">Gestão Completa</h2>
          </div>
        </div>

        <div className="px-6 pb-6">
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <a href="/cobranca" className="flex flex-col p-4 bg-surface border border-border rounded-lg hover:border-amber transition-colors no-underline">
              <span className="text-[13px] font-semibold text-ink">Cobrança</span>
              <span className="text-[12px] text-muted mt-1">Gerir facturas e docs</span>
            </a>
            <a href="/manutencao" className="flex flex-col p-4 bg-surface border border-border rounded-lg hover:border-amber transition-colors no-underline">
              <span className="text-[13px] font-semibold text-ink">Manutenção</span>
              <span className="text-[12px] text-muted mt-1">Avisos e histórico</span>
            </a>
            <a href="/alertas" className="flex flex-col p-4 bg-surface border border-border rounded-lg hover:border-amber transition-colors no-underline">
              <span className="text-[13px] font-semibold text-ink">Alertas</span>
              <span className="text-[12px] text-muted mt-1">Documentos a expirar</span>
            </a>
          </section>
        </div>
      </div>
    </SidebarLayout>
  );
}
