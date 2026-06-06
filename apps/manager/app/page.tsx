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
import { BillingTripActions } from "./components/BillingTripActions";
import { ControlTowerOverview } from "./components/ControlTowerOverview";
import { CostMarginBoard } from "./components/CostMarginBoard";
import { DriverDespachoTableAdmin } from "./components/DriverDespachoTableAdmin";
import { FleetComplianceBoard } from "./components/FleetComplianceBoard";
import { FleetHistoryBoard } from "./components/FleetHistoryBoard";
import { MaintenanceImminentPanel } from "./components/MaintenanceImminentPanel";
import { FuelControlBoard } from "./components/FuelControlBoard";
import { SidebarLayout } from "./components/SidebarLayout";
import { TransportCargoBoard } from "./components/TransportCargoBoard";
import { KpiCard } from "./components/ui/KpiCard";
import { WorkQueue } from "./components/ui/WorkQueue";
import { SectionHeader } from "./components/ui/SectionHeader";
import { StatusBadge } from "./components/ui/StatusBadge";
import { MonoCell, MoneyCell } from "./components/ui/MonoCell";
import { DataSourceBadge } from "./components/ui/DataSourceBadge";
import {
  type BillingStatus,
  getApiConfig,
  loadBillingDocuments,
  loadBillingTrips,
  loadContracts,
} from "./lib/billing-api";
import { loadControlTower, loadImminentMaintenanceAlerts } from "./lib/control-tower-api";
import { loadFleetHistories } from "./lib/fleet-history-api";
import { loadFuelControlBoard } from "./lib/fuel-operations-api";
import { loadDriverDespachoTable } from "./lib/operations-admin-api";

const statusMeta: Record<
  BillingStatus,
  {
    label: string;
    tone: string;
    icon: typeof AlertTriangle;
  }
> = {
  pending_delivery_proof: {
    label: "Sem descarga",
    tone: "red",
    icon: AlertTriangle,
  },
  uncontracted: {
    label: "Sem contrato",
    tone: "red",
    icon: AlertTriangle,
  },
  pending_delivery_validation: {
    label: "Validacao descarga",
    tone: "orange",
    icon: ClipboardCheck,
  },
  billable: {
    label: "Pronto a cobrar",
    tone: "cyan",
    icon: ReceiptText,
  },
  billing_draft: {
    label: "Em documento",
    tone: "blue",
    icon: FileClock,
  },
  billed: {
    label: "Cobrado",
    tone: "green",
    icon: BadgeCheck,
  },
};

const statusOrder: BillingStatus[] = [
  "uncontracted",
  "pending_delivery_validation",
  "billable",
  "billing_draft",
  "billed",
];

function money(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    maximumFractionDigits: 0,
  }).format(value);
}

function countByStatus(trips: { status: BillingStatus }[], status: BillingStatus) {
  return trips.filter((trip) => trip.status === status).length;
}

function sumByStatus(
  trips: { status: BillingStatus; amount: number | null }[],
  status: BillingStatus,
) {
  return trips
    .filter((trip) => trip.status === status)
    .reduce((total, trip) => total + (trip.amount ?? 0), 0);
}

export default async function ManagerHome() {
  await requireSession();
  const controlTower = await loadControlTower();
  const imminentAlerts = await loadImminentMaintenanceAlerts();
  const fuelControlBoard = await loadFuelControlBoard();
  const fleetHistories = await loadFleetHistories();
  const { trips, source, message } = await loadBillingTrips();
  const documents = await loadBillingDocuments();
  const contracts = await loadContracts();
  const driverDespachoTable = await loadDriverDespachoTable();
  const apiConfig = getApiConfig();
  const controlledValue =
    sumByStatus(trips, "billable") +
    sumByStatus(trips, "billing_draft") +
    sumByStatus(trips, "billed");

  return (
    <SidebarLayout active="operacao">
      <div className="w-full">
        <ControlTowerOverview result={controlTower} />
        <TransportCargoBoard apiConfig={apiConfig} result={controlTower} />
        <FleetComplianceBoard apiConfig={apiConfig} result={controlTower} />
        <div style={{ padding: "0 24px 24px" }}>
          <MaintenanceImminentPanel alerts={imminentAlerts} />
        </div>
        <FleetHistoryBoard result={fleetHistories} />
        <FuelControlBoard result={fuelControlBoard} />
        <CostMarginBoard apiConfig={apiConfig} result={controlTower} />

        <div className="px-6 mt-8 mb-4">
          <span className="block text-[11px] font-semibold uppercase tracking-widest text-muted mb-1">
            Financeiro Operacional
          </span>
          <h2 className="text-[20px] font-bold text-ink">Cobrança de transporte</h2>
          <p className="text-[13px] text-muted mt-1">
            Viagens entregues, provas de descarga, contratos e documentos mensais.
          </p>
        </div>

        <div className="px-6 flex items-center justify-end gap-2 mb-3">
          <button
            className="inline-flex items-center gap-1.5 h-8 px-3 text-[13px] font-medium bg-surface border border-border rounded-md hover:bg-surface-2 transition-colors duration-75"
            title="Gerar documento de cobrança"
          >
            <ReceiptText size={15} />
            Gerar
          </button>
          <button
            className="inline-flex items-center justify-center h-8 w-8 bg-surface border border-border rounded-md hover:bg-surface-2 transition-colors duration-75"
            title="Exportar PDF"
          >
            <FileText size={15} />
          </button>
        </div>

        <div className="px-6 mb-3">
          <DataSourceBadge source={source} message={source !== "api" ? (message ?? undefined) : undefined} />
        </div>

        <div className="px-6">
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" aria-label="Indicadores de cobrança">
            <KpiCard
              label="Sem contrato"
              value={countByStatus(trips, "uncontracted")}
              semantic={countByStatus(trips, "uncontracted") > 0 ? "error" : "default"}
            />
            <KpiCard
              label="A validar descarga"
              value={countByStatus(trips, "pending_delivery_validation")}
              semantic="warning"
            />
            <KpiCard
              label="Prontas a cobrar"
              value={countByStatus(trips, "billable")}
              semantic="info"
            />
            <KpiCard
              label="Valor controlado"
              value={money(controlledValue)}
              semantic="success"
            />
          </section>

          <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3 mb-6" aria-label="Filas de trabalho">
            {statusOrder.map((status) => {
              const meta = statusMeta[status];
              const Icon = meta.icon;
              const statusTrips = trips.filter((trip) => trip.status === status);
              return (
                <WorkQueue
                  key={status}
                  icon={Icon}
                  title={meta.label}
                  tone={meta.tone as "blue" | "orange" | "red" | "green" | "cyan" | "amber"}
                  emptyLabel="Sem viagens."
                  items={statusTrips.map((trip) => ({
                    id: trip.id,
                    reference: trip.plate,
                    title: trip.route,
                    meta: money(trip.amount),
                  }))}
                />
              );
            })}
          </section>

          <section className="bg-surface border border-border rounded-lg overflow-hidden mb-4">
            <SectionHeader title="Viagens para cobrança" count={trips.length} />
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead className="bg-surface-2 border-b border-border">
                  <tr>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Viatura</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Cliente/Contrato</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Rota</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Carga</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Descarga</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Estado</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Valor</th>
                    <th className="text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Acção</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {trips.map((trip) => {
                    const meta = statusMeta[trip.status];
                    return (
                      <tr key={trip.id} className="hover:bg-surface-2 transition-colors duration-75">
                        <td className="px-3 py-2.5">
                          <span className="inline-flex items-center gap-1.5">
                            <Truck size={13} className="text-muted flex-shrink-0" />
                            <MonoCell size="sm">{trip.plate}</MonoCell>
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-col">
                            <strong className="text-[13px] font-medium text-ink">{trip.client ?? "Por associar"}</strong>
                            <span className="text-[12px] text-muted">{trip.contractReference ?? "Sem contrato"}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-2">
                            <Route size={13} className="text-muted flex-shrink-0" />
                            {trip.route}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-col">
                            <span className="text-[13px] text-ink">{trip.cargo}</span>
                            <span className="text-[12px] text-muted">{trip.loadState}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-col">
                            <span className="text-[13px] text-ink">{trip.deliveredAt}</span>
                            <span className="text-[12px] text-muted">{trip.deliveryProof}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={trip.status} label={meta.label} />
                        </td>
                        <td className="px-3 py-2.5">
                          <MoneyCell value={trip.amount ?? 0} semantic={trip.amount && trip.amount > 0 ? "revenue" : "default"} />
                        </td>
                        <td className="px-3 py-2 sticky right-0 bg-surface shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)]">
                          <BillingTripActions
                            apiConfig={apiConfig}
                            contracts={contracts}
                            trip={trip}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border rounded-lg overflow-hidden mb-4">
            <SectionHeader title="Documentos" description="Mensal" />
            <div className="divide-y divide-border">
              {documents.map((document) => (
                <article key={document.reference} className="px-4 py-3 flex items-center justify-between gap-4 hover:bg-surface-2 transition-colors duration-75">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <MonoCell size="sm" className="font-medium text-ink">{document.reference}</MonoCell>
                      <StatusBadge
                        status={document.status === "Emitido" ? "issued" : "draft"}
                        label={document.status}
                      />
                    </div>
                    <span className="text-[12px] text-muted">{document.client}</span>
                  </div>
                  <dl className="flex gap-4 text-[12px] text-muted flex-shrink-0">
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide font-semibold">Período</dt>
                      <dd className="text-ink">{document.period}</dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide font-semibold">Viagens</dt>
                      <dd className="text-ink">{document.trips}</dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase tracking-wide font-semibold">Total</dt>
                      <dd><MoneyCell value={document.amount ?? 0} semantic="revenue" /></dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        </div>

        <DriverDespachoTableAdmin apiConfig={apiConfig} result={driverDespachoTable} />
      </div>
    </SidebarLayout>
  );
}
