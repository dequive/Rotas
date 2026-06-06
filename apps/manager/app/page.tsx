import {
  AlertTriangle,
  BadgeCheck,
  ClipboardCheck,
  FileClock,
  FileText,
  Link2,
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

        <div className="section-divider">
          <div className="title">
            <span className="eyebrow">Financeiro Operacional</span>
            <h2>Cobrança de transporte</h2>
            <p>Viagens entregues, provas de descarga, contratos e documentos mensais.</p>
          </div>
        </div>

        <div className="topbar">
          <div />
          <div className="toolbar" aria-label="Accoes de cobranca">
            <button className="tool-btn" title="Gerar documento de cobranca">
              <ReceiptText size={18} />
              Gerar
            </button>
            <button className="icon-btn" title="Exportar PDF">
              <FileText size={18} />
            </button>
          </div>
        </div>

        <div className={`data-source ${source}`}>
          <Link2 size={15} />
          <span>{source === "api" ? "Dados carregados da API ROTAS." : message}</span>
        </div>

        <section className="grid" aria-label="Indicadores de cobranca">
          <div className="panel metric red-line">
            <span>Sem contrato</span>
            <strong>{countByStatus(trips, "uncontracted")}</strong>
          </div>
          <div className="panel metric orange-line">
            <span>A validar descarga</span>
            <strong>{countByStatus(trips, "pending_delivery_validation")}</strong>
          </div>
          <div className="panel metric cyan-line">
            <span>Prontas a cobrar</span>
            <strong>{countByStatus(trips, "billable")}</strong>
          </div>
          <div className="panel metric green-line">
            <span>Valor controlado</span>
            <strong>{money(controlledValue)}</strong>
          </div>
        </section>

        <section className="queue-grid" aria-label="Filas de trabalho">
          {statusOrder.map((status) => {
            const meta = statusMeta[status];
            const Icon = meta.icon;
            const statusTrips = trips.filter((trip) => trip.status === status);

            return (
              <article className="queue" key={status}>
                <header>
                  <span className={`queue-icon ${meta.tone}`}>
                    <Icon size={16} />
                  </span>
                  <div>
                    <h2>{meta.label}</h2>
                    <p>{statusTrips.length} viagens</p>
                  </div>
                </header>
                <div className="queue-list">
                  {statusTrips.map((trip) => (
                    <div className="queue-item" key={trip.id}>
                      <strong>{trip.plate}</strong>
                      <span>{trip.route}</span>
                      <small>{money(trip.amount)}</small>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
        </section>

        <div className="content billing-content">
          <section className="panel">
            <div className="section-header">
              <h2 className="section-title">Viagens para cobranca</h2>
              <span>{trips.length} registos</span>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Viatura</th>
                    <th>Cliente/Contrato</th>
                    <th>Rota</th>
                    <th>Carga</th>
                    <th>Descarga</th>
                    <th>Estado</th>
                    <th>Valor</th>
                    <th>Acção</th>
                  </tr>
                </thead>
                <tbody>
                  {trips.map((trip) => {
                    const meta = statusMeta[trip.status];
                    return (
                      <tr key={trip.id}>
                        <td>
                          <span className="plate">
                            <Truck size={15} />
                            {trip.plate}
                          </span>
                        </td>
                        <td>
                          <strong>{trip.client ?? "Por associar"}</strong>
                          <span className="muted-line">
                            {trip.contractReference ?? "Sem contrato"}
                          </span>
                        </td>
                        <td>
                          <span className="route">
                            <Route size={15} />
                            {trip.route}
                          </span>
                        </td>
                        <td>
                          {trip.cargo}
                          <span className="muted-line">{trip.loadState}</span>
                        </td>
                        <td>
                          {trip.deliveredAt}
                          <span className="muted-line">{trip.deliveryProof}</span>
                        </td>
                        <td>
                          <span className={`badge ${meta.tone}`}>{meta.label}</span>
                        </td>
                        <td>{money(trip.amount)}</td>
                        <td>
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

          <section className="panel documents-panel">
            <div className="section-header">
              <h2 className="section-title">Documentos</h2>
              <span>Mensal</span>
            </div>
            <div className="document-list">
              {documents.map((document) => (
                <article className="document" key={document.reference}>
                  <div>
                    <strong>{document.reference}</strong>
                    <span>{document.client}</span>
                  </div>
                  <dl>
                    <div>
                      <dt>Periodo</dt>
                      <dd>{document.period}</dd>
                    </div>
                    <div>
                      <dt>Viagens</dt>
                      <dd>{document.trips}</dd>
                    </div>
                    <div>
                      <dt>Total</dt>
                      <dd>{money(document.amount)}</dd>
                    </div>
                  </dl>
                  <span className={`badge ${document.status === "Emitido" ? "green" : "blue"}`}>
                    {document.status}
                  </span>
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
