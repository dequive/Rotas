import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  MapPin,
  Navigation,
  PackageCheck,
  Route,
  ShieldAlert,
  Truck,
  Users,
  Wrench,
} from "lucide-react";

import type { BillingTrip } from "@/app/lib/billing-api";
import type { ControlTowerLoadResult } from "@/app/lib/control-tower-api";

interface TmsExecutiveDashboardProps {
  controlTower: ControlTowerLoadResult;
  billingTrips: BillingTrip[];
}

export function TmsExecutiveDashboard({
  controlTower,
  billingTrips,
}: TmsExecutiveDashboardProps) {
  const { tower } = controlTower;
  const summary = tower.summary;
  const activeTrips = [
    ...tower.queues.delayedTrips.map((trip) => ({
      id: trip.tripId,
      route: trip.route,
      vehiclePlate: trip.vehiclePlate,
      driverName: trip.driverName,
    })),
    ...tower.queues.operationalCloseCandidates.map((trip) => ({
      id: trip.tripId,
      route: trip.route,
      vehiclePlate: trip.vehiclePlate,
      driverName: trip.driverName,
    })),
    ...tower.queues.pendingDispatch.map((trip) => ({
      id: trip.tripId,
      route: trip.route,
      vehiclePlate: null,
      driverName: null,
    })),
  ].slice(0, 4);
  const recentActivities = [
    ...tower.queues.openIncidents.map((item) => ({
      id: item.incidentId,
      icon: ShieldAlert,
      tone: "red" as const,
      title: item.incidentType,
      detail: item.route,
      meta: formatDateTime(item.occurredAt),
    })),
    ...tower.queues.pendingDeliveryValidation.map((item) => ({
      id: item.deliveryProofId,
      icon: PackageCheck,
      tone: "blue" as const,
      title: "Descarga recebida",
      detail: item.route,
      meta: formatDateTime(item.deliveredAt),
    })),
    ...tower.queues.operationalExceptions.map((item) => ({
      id: item.exceptionId,
      icon: AlertTriangle,
      tone: "orange" as const,
      title: item.title,
      detail: item.message,
      meta: formatDateTime(item.createdAt),
    })),
  ].slice(0, 5);
  const delivered = billingTrips.filter((trip) => trip.status === "billed").length;
  const inTransit = summary.tripsInExecution + tower.queues.delayedTrips.length;
  const pending =
    summary.dispatchPending +
    summary.deliveryProofsPendingValidation +
    summary.closedTripsUnreconciled;
  const blocked =
    summary.dispatchBlocked +
    summary.incidentsOpen +
    summary.operationalExceptionsOpen +
    summary.negativeMarginTrips;
  const shipmentTotal = Math.max(delivered + inTransit + pending + blocked, 1);
  const pressureBars = [
    { label: "Ordens", value: summary.tripOrdersOpen },
    { label: "Despacho", value: summary.dispatchPending },
    { label: "Em rota", value: summary.tripsInExecution },
    { label: "Atrasos", value: tower.queues.delayedTrips.length },
    { label: "Descarga", value: summary.deliveryProofsPendingValidation },
    { label: "Cobrança", value: summary.billingReady },
    { label: "Incidentes", value: summary.incidentsOpen },
    { label: "Exceções", value: summary.operationalExceptionsOpen },
  ];
  const pressureMax = Math.max(...pressureBars.map((item) => item.value), 1);

  return (
    <section className="tms-executive" aria-label="Resumo executivo TMS">
      <div className="tms-hero">
        <div className="tms-hero-copy">
          <span>Transport Management System</span>
          <h1>Centro operacional para frota, carga, custos e cobrança</h1>
          <p>
            Visão consolidada das viagens em execução, autorizações, provas de descarga,
            incidentes, compliance documental e margem operacional.
          </p>
        </div>
        <div className="tms-hero-strip">
          <MetricPill icon={Truck} label="Viaturas" value={summary.vehiclesActive} />
          <MetricPill icon={Users} label="Motoristas" value={summary.driversActive} />
          <MetricPill icon={Route} label="Viagens hoje" value={summary.tripsCreatedToday} />
        </div>
      </div>

      <div className="tms-metrics">
        <ExecutiveMetric
          icon={Truck}
          label="Viaturas activas"
          value={summary.vehiclesActive}
          delta={`${summary.vehicleDocumentsExpiring} docs a expirar`}
          tone="blue"
        />
        <ExecutiveMetric
          icon={Activity}
          label="Em execução"
          value={summary.tripsInExecution}
          delta={`${tower.queues.delayedTrips.length} atrasadas`}
          tone="green"
        />
        <ExecutiveMetric
          icon={PackageCheck}
          label="Prontas a cobrar"
          value={summary.billingReady}
          delta={`${summary.deliveryProofsPendingValidation} descargas a validar`}
          tone="purple"
        />
        <ExecutiveMetric
          icon={Clock3}
          label="Bloqueios"
          value={blocked}
          delta={`${summary.dispatchBlocked} autorizações bloqueadas`}
          tone="amber"
        />
      </div>

      <div className="tms-grid">
        <div className="tms-panel tms-chart-panel">
          <PanelTitle
            title="Pressão operacional"
            meta={formatDate(tower.date)}
            icon={Activity}
          />
          <div className="tms-line-chart" aria-hidden="true">
            {pressureBars.map((item) => (
              <span
                key={item.label}
                title={`${item.label}: ${item.value}`}
                style={{ height: `${Math.max(18, Math.round((item.value / pressureMax) * 104))}px` }}
              />
            ))}
          </div>
          <div className="tms-chart-legend">
            <span>Pressão total: {pressureBars.reduce((total, item) => total + item.value, 0)}</span>
            <span>Receita controlada: {formatMoney(summary.contractRevenueTotal)}</span>
          </div>
        </div>

        <div className="tms-panel">
          <PanelTitle title="Estado das viagens" meta={`${shipmentTotal} itens`} icon={CheckCircle2} />
          <div className="tms-status">
            <div
              className="tms-donut"
              style={{
                background: `conic-gradient(#16a34a 0 ${percent(delivered, shipmentTotal)}%, #2563eb 0 ${percent(delivered + inTransit, shipmentTotal)}%, #f59e0b 0 ${percent(delivered + inTransit + pending, shipmentTotal)}%, #dc2626 0 100%)`,
              }}
            >
              <strong>{shipmentTotal}</strong>
              <span>Total</span>
            </div>
            <div className="tms-status-list">
              <StatusLine color="green" label="Entregue/cobrado" value={delivered} total={shipmentTotal} />
              <StatusLine color="blue" label="Em trânsito" value={inTransit} total={shipmentTotal} />
              <StatusLine color="amber" label="Pendente" value={pending} total={shipmentTotal} />
              <StatusLine color="red" label="Bloqueado" value={blocked} total={shipmentTotal} />
            </div>
          </div>
        </div>

        <div className="tms-panel tms-activity-panel">
          <PanelTitle title="Atividades recentes" meta="Operação" icon={Clock3} />
          <div className="tms-activity-list">
            {recentActivities.length > 0 ? (
              recentActivities.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.id} className="tms-activity">
                    <span className={`tms-activity-icon ${item.tone}`}>
                      <Icon size={15} />
                    </span>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.detail}</span>
                      <small>{item.meta}</small>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="tms-empty">Sem atividades críticas recentes.</p>
            )}
          </div>
        </div>
      </div>

      <div className="tms-grid tms-grid-bottom">
        <div className="tms-panel tms-map-panel">
          <PanelTitle title="Live fleet tracking" meta="Rotas críticas" icon={Navigation} />
          <div className="tms-map">
            <span className="tms-map-node origin"><MapPin size={15} /> Maputo</span>
            <span className="tms-map-node mid"><Truck size={15} /> Beira</span>
            <span className="tms-map-node dest"><MapPin size={15} /> Nacala</span>
            <span className="tms-map-route route-a" />
            <span className="tms-map-route route-b" />
          </div>
        </div>

        <div className="tms-panel">
          <PanelTitle title="Viagens monitoradas" meta={`${activeTrips.length} em foco`} icon={Route} />
          <div className="tms-trip-list">
            {activeTrips.length > 0 ? (
              activeTrips.map((trip) => (
                <div key={trip.id} className="tms-trip">
                  <strong>{trip.route}</strong>
                  <span>{trip.vehiclePlate ?? "Viatura por atribuir"} · {trip.driverName ?? "Motorista por atribuir"}</span>
                </div>
              ))
            ) : (
              <p className="tms-empty">Sem viagens críticas em foco.</p>
            )}
          </div>
        </div>

        <div className="tms-panel">
          <PanelTitle title="Saúde operacional" meta="Hoje" icon={Wrench} />
          <div className="tms-health">
            <HealthRow label="Margem" value={formatMoney(summary.marginTotal)} />
            <HealthRow label="Incidentes" value={summary.incidentsOpen} />
            <HealthRow label="Exceções" value={summary.operationalExceptionsOpen} />
            <HealthRow label="Docs a expirar" value={summary.vehicleDocumentsExpiring + summary.driverDocumentsExpiring} />
          </div>
        </div>
      </div>
    </section>
  );
}

function ExecutiveMetric({
  icon: Icon,
  label,
  value,
  delta,
  tone,
}: {
  icon: typeof Truck;
  label: string;
  value: number;
  delta: string;
  tone: "blue" | "green" | "purple" | "amber";
}) {
  return (
    <div className="tms-metric">
      <span className={`tms-metric-icon ${tone}`}>
        <Icon size={18} />
      </span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{delta}</small>
      </div>
    </div>
  );
}

function MetricPill({ icon: Icon, label, value }: { icon: typeof Truck; label: string; value: number }) {
  return (
    <div>
      <Icon size={15} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelTitle({ title, meta, icon: Icon }: { title: string; meta: string; icon: typeof Truck }) {
  return (
    <header className="tms-panel-title">
      <div>
        <Icon size={16} />
        <strong>{title}</strong>
      </div>
      <span>{meta}</span>
    </header>
  );
}

function StatusLine({
  color,
  label,
  value,
  total,
}: {
  color: "green" | "blue" | "amber" | "red";
  label: string;
  value: number;
  total: number;
}) {
  return (
    <div className="tms-status-line">
      <span className={`tms-dot ${color}`} />
      <strong>{label}</strong>
      <small>{value} ({percent(value, total)}%)</small>
    </div>
  );
}

function HealthRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function percent(value: number, total: number) {
  return Math.round((value / Math.max(total, 1)) * 100);
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string) {
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
