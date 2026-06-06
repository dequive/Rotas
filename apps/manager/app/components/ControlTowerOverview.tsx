import {
  AlertOctagon,
  ClipboardCheck,
  FileWarning,
  Gauge,
  ReceiptText,
  ShieldAlert,
  ShieldCheck,
  Truck,
  Users,
} from "lucide-react";

import type { ControlTower, ControlTowerLoadResult } from "../lib/control-tower-api";

interface ControlTowerOverviewProps {
  result: ControlTowerLoadResult;
}

export function ControlTowerOverview({ result }: ControlTowerOverviewProps) {
  const { tower } = result;
  const summary = tower.summary;

  return (
    <>
      <div className="operational-heading">
        <div>
          <span className="eyebrow">Torre de Controlo</span>
          <h1>Operação diária</h1>
          <p>Autorizações de saída, viagens activas, incidentes e validações que exigem decisão.</p>
        </div>
        <div className="operation-date">
          <span>Data operacional</span>
          <strong>{formatDate(tower.date)}</strong>
        </div>
      </div>

      <div className={`data-source ${result.source}`}>
        <Gauge size={15} />
        <span>
          {result.source === "api"
            ? "Control Tower carregada da API ROTAS."
            : result.message}
        </span>
      </div>

      <section
        className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3"
        aria-label="Indicadores da operação"
      >
        <TowerMetric
          icon={ClipboardCheck}
          label="Ordens abertas"
          tone="blue"
          value={summary.tripOrdersOpen}
        />
        <TowerMetric
          icon={ShieldCheck}
          label="Autorizações pendentes"
          tone="orange"
          value={summary.dispatchPending}
        />
        <TowerMetric
          icon={Truck}
          label="Em execução"
          tone="green"
          value={summary.tripsInExecution}
        />
        <TowerMetric
          icon={AlertOctagon}
          label="Incidentes abertos"
          tone="red"
          value={summary.incidentsOpen}
        />
        <TowerMetric
          icon={FileWarning}
          label="Descargas a validar"
          tone="orange"
          value={summary.deliveryProofsPendingValidation}
        />
        <TowerMetric
          icon={ReceiptText}
          label="Prontas a cobrar"
          tone="cyan"
          value={summary.billingReady}
        />
      </section>

      <section
        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-[14px]"
        aria-label="Excepções operacionais"
      >
        <Worklist
          emptyLabel="Sem autorizações bloqueadas."
          icon={ShieldAlert}
          title="Autorização bloqueada"
          tone="red"
          items={tower.queues.blockedDispatch.map((item) => ({
            id: item.clearanceId,
            reference: shortReference(item.tripId),
            title: item.route,
            detail: item.blockedReason,
            meta: formatDateTime(item.updatedAt),
          }))}
        />
        <Worklist
          emptyLabel="Sem incidentes abertos."
          icon={AlertOctagon}
          title="Incidentes abertos"
          tone="orange"
          items={tower.queues.openIncidents.map((item) => ({
            id: item.incidentId,
            reference: `${shortReference(item.tripId)} · ${item.incidentType}`,
            title: item.route,
            detail: item.description,
            meta: `${severityLabel(item.severity)} · ${formatDateTime(item.occurredAt)}`,
          }))}
        />
        <Worklist
          emptyLabel="Sem provas pendentes."
          icon={FileWarning}
          title="Descargas por validar"
          tone="blue"
          items={tower.queues.pendingDeliveryValidation.map((item) => ({
            id: item.deliveryProofId,
            reference: item.documentNumber ?? shortReference(item.tripId),
            title: item.route,
            detail: "Prova recebida, aguarda validação do gestor.",
            meta: formatDateTime(item.deliveredAt),
          }))}
        />
        <Worklist
          emptyLabel="Sem excepções operacionais activas."
          icon={AlertOctagon}
          title="Excepções persistidas"
          tone="red"
          items={tower.queues.operationalExceptions.map((item) => ({
            id: item.exceptionId,
            reference: exceptionTypeLabel(item.exceptionType),
            title: item.title,
            detail: item.message,
            meta: `${severityLabel(item.severity)} · ${formatDateTime(item.createdAt)}`,
          }))}
        />
      </section>

      <section
        className="flex flex-wrap gap-x-[18px] gap-y-[6px] mt-3 px-3 py-[10px] bg-[#edf2f7] border border-line rounded-md"
        aria-label="Capacidade operacional"
      >
        <FleetFact icon={Truck} label="Viaturas activas" value={summary.vehiclesActive} />
        <FleetFact icon={Users} label="Motoristas activos" value={summary.driversActive} />
        <FleetFact icon={ClipboardCheck} label="Viagens abertas hoje" value={summary.tripsCreatedToday} />
        <FleetFact icon={ShieldAlert} label="Dispensas activas" value={summary.activeWaivers} />
        <FleetFact icon={AlertOctagon} label="Autorizações bloqueadas" value={summary.dispatchBlocked} />
        <FleetFact
          icon={FileWarning}
          label="Docs viatura"
          value={summary.vehicleDocumentsExpiring}
        />
        <FleetFact
          icon={FileWarning}
          label="Docs motorista"
          value={summary.driverDocumentsExpiring}
        />
        <FleetFact
          icon={AlertOctagon}
          label="Excepções activas"
          value={summary.operationalExceptionsOpen}
        />
      </section>

      <section className="compliance-grid" aria-label="Compliance documental">
        <Worklist
          emptyLabel="Sem documentos de viatura perto do vencimento."
          icon={Truck}
          title="Documentos de viatura"
          tone="orange"
          items={tower.queues.vehicleDocumentsExpiring.map((item) => ({
            id: item.id,
            reference: item.entityLabel,
            title: documentTypeLabel(item.documentType),
            detail: `Vence em ${item.daysUntilExpiry} dias.`,
            meta: formatDateOnly(item.validUntil),
          }))}
        />
        <Worklist
          emptyLabel="Sem documentos de motorista perto do vencimento."
          icon={Users}
          title="Documentos de motorista"
          tone="orange"
          items={tower.queues.driverDocumentsExpiring.map((item) => ({
            id: item.id,
            reference: item.entityLabel,
            title: documentTypeLabel(item.documentType),
            detail: `Vence em ${item.daysUntilExpiry} dias.`,
            meta: formatDateOnly(item.validUntil),
          }))}
        />
      </section>
    </>
  );
}

interface TowerMetricProps {
  icon: typeof ClipboardCheck;
  label: string;
  tone: string;
  value: number;
}

function TowerMetric({ icon: Icon, label, tone, value }: TowerMetricProps) {
  return (
    <article
      className={`min-h-[86px] p-3 flex items-center gap-[10px] bg-panel border border-line rounded-lg border-l-[4px] border-l-${tone} overflow-hidden`}
    >
      <span className={`queue-icon ${tone}`}>
        <Icon size={16} />
      </span>
      <div className="min-w-0">
        <span className="text-muted text-[12px] [overflow-wrap:anywhere]">{label}</span>
        <strong className="block mt-1 text-[22px] text-ink">{value}</strong>
      </div>
    </article>
  );
}

interface WorklistItem {
  id: string;
  reference: string;
  title: string;
  detail: string;
  meta: string;
}

interface WorklistProps {
  emptyLabel: string;
  icon: typeof ClipboardCheck;
  items: WorklistItem[];
  title: string;
  tone: string;
}

function Worklist({ emptyLabel, icon: Icon, items, title, tone }: WorklistProps) {
  return (
    <article className="min-w-0 p-[14px] bg-panel border border-line rounded-lg">
      <header className="flex items-center gap-[10px] mb-[10px]">
        <span className={`queue-icon ${tone}`}>
          <Icon size={16} />
        </span>
        <div>
          <h2 className="m-0 text-[14px]">{title}</h2>
          <p className="m-0 mt-[2px] text-muted text-[12px]">{items.length} pendentes</p>
        </div>
      </header>
      <div className="grid gap-[7px]">
        {items.length === 0 ? <p className="empty-state">{emptyLabel}</p> : null}
        {items.map((item) => (
          <div className="grid gap-[3px] pt-2 border-t border-line [overflow-wrap:anywhere]" key={item.id}>
            <strong className="text-blue text-[12px]">{item.reference}</strong>
            <span className="text-[13px] font-bold">{item.title}</span>
            <small className="text-muted text-[12px]">{item.detail}</small>
            <em className="text-muted text-[12px] not-italic">{item.meta}</em>
          </div>
        ))}
      </div>
    </article>
  );
}

interface FleetFactProps {
  icon: typeof Truck;
  label: string;
  value: number;
}

function FleetFact({ icon: Icon, label, value }: FleetFactProps) {
  return (
    <div className="flex items-center gap-[6px] text-muted text-[12px]">
      <Icon size={16} />
      <span>{label}</span>
      <strong className="text-ink">{value}</strong>
    </div>
  );
}

function shortReference(value: string) {
  return value.length > 12 ? `TRP-${value.slice(0, 8)}` : value;
}

function severityLabel(value: string) {
  const labels: Record<string, string> = {
    critical: "Crítico",
    high: "Alto",
    medium: "Médio",
    low: "Baixo",
  };
  return labels[value] ?? value;
}

function exceptionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    fuel_low_stock: "Stock baixo",
    fuel_stock_variance: "Divergência de stock",
    vehicle_refuel_without_trip: "Abastecimento sem viagem",
  };
  return labels[value] ?? value;
}

function documentTypeLabel(value: string) {
  const labels: Record<string, string> = {
    driving_license: "Carta de condução",
    inatter_license: "Licença INATTER",
    inspection: "Inspecção",
    insurance: "Seguro",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-MZ", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatDateOnly(value: string) {
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
