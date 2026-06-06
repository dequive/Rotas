"use client";

import { AlertTriangle, Banknote, Calculator, ReceiptText, Save, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import type {
  ControlTowerLoadResult,
  DriverDespachoPending,
  NegativeMarginTrip,
} from "../lib/control-tower-api";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface CostMarginBoardProps {
  apiConfig: ApiConfig;
  result: ControlTowerLoadResult;
}

export function CostMarginBoard({ apiConfig, result }: CostMarginBoardProps) {
  const { summary, queues } = result.tower;

  return (
    <section className="domain-section cost-margin" aria-labelledby="cost-margin-title">
      <div className="domain-heading">
        <div className="title">
          <span className="eyebrow">Custos e Margem</span>
          <h2 id="cost-margin-title">Margem operacional</h2>
          <p>Custos reais, despacho do motorista e viagens que exigem reconciliação.</p>
        </div>
        <span className="module-state">
          <Calculator size={15} />
          {summary.costsReconciledTrips} reconciliadas
        </span>
      </div>

      <div className="cost-kpis" aria-label="Indicadores de custos e margem">
        <CostKpi icon={ReceiptText} label="Custo real" value={formatMoney(summary.transportCostTotal)} />
        <CostKpi icon={Banknote} label="Receita" value={formatMoney(summary.contractRevenueTotal)} />
        <CostKpi icon={Calculator} label="Margem" tone={summary.marginTotal < 0 ? "red" : "green"} value={formatMoney(summary.marginTotal)} />
        <CostKpi icon={AlertTriangle} label="Por reconciliar" tone="orange" value={summary.closedTripsUnreconciled.toString()} />
      </div>

      <div className="cost-work-grid">
        <article className="cost-panel">
          <div className="section-header">
            <h3 className="section-title">Despacho por lançar</h3>
            <span>{queues.driverDespachoPending.length} viagens</span>
          </div>
          <div className="cost-list">
            {queues.driverDespachoPending.length === 0 ? (
              <p className="empty-state">Sem viagens longas pendentes de despacho.</p>
            ) : null}
            {queues.driverDespachoPending.map((item) => (
              <DespachoPendingItem apiConfig={apiConfig} item={item} key={item.tripId} />
            ))}
          </div>
        </article>

        <article className="cost-panel">
          <div className="section-header">
            <h3 className="section-title">Margem negativa</h3>
            <span>{summary.negativeMarginTrips} viagens</span>
          </div>
          <div className="cost-list">
            {queues.negativeMarginTrips.length === 0 ? (
              <p className="empty-state">Sem viagens reconciliadas com margem negativa.</p>
            ) : null}
            {queues.negativeMarginTrips.map((item) => (
              <NegativeMarginItem apiConfig={apiConfig} item={item} key={item.tripId} />
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function CostKpi({
  icon: Icon,
  label,
  tone = "blue",
  value,
}: {
  icon: typeof Calculator;
  label: string;
  tone?: "blue" | "green" | "orange" | "red";
  value: string;
}) {
  return (
    <article className={`transport-kpi ${tone}-line`}>
      <Icon size={16} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function NegativeMarginItem({ apiConfig, item }: { apiConfig: ApiConfig; item: NegativeMarginTrip }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canUseApi = Boolean(apiConfig.tenantId);

  async function approveNegativeMargin() {
    if (!apiConfig.tenantId) {
      setError("Acção indisponível sem API.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${apiConfig.apiBaseUrl}/api/v1/operations/waivers`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": `negative-margin:${item.tripId}:${item.costsReconciledAt}`,
          "X-Tenant-Id": apiConfig.tenantId,
        },
        body: JSON.stringify({
          entity_type: "trip",
          entity_id: item.tripId,
          waiver_type: "negative_margin_approved",
          risk_level: "high",
          reason: `Margem negativa aprovada em Custos e Margem: ${formatMoney(item.margin)}.`,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nao foi possivel aprovar a margem.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cost-item negative-margin-item">
      <div>
        <strong>{shortReference(item.tripId)}</strong>
        <span>{item.route}</span>
        <small>
          {item.vehiclePlate ?? "Sem viatura"} · {item.driverName ?? "Sem motorista"}
        </small>
      </div>
      <div className="margin-governance">
        <dl>
          <div>
            <dt>Custo</dt>
            <dd>{formatMoney(item.transportCost)}</dd>
          </div>
          <div>
            <dt>Receita</dt>
            <dd>{formatMoney(item.revenue)}</dd>
          </div>
          <div>
            <dt>Margem</dt>
            <dd className="negative">{formatMoney(item.margin)}</dd>
          </div>
        </dl>
        <button
          className="tool-btn primary"
          disabled={busy || !canUseApi}
          onClick={approveNegativeMargin}
          type="button"
        >
          <ShieldCheck size={15} />
          {busy ? "A aprovar" : "Aprovar"}
        </button>
        {error ? <small className="error-text">{error}</small> : null}
      </div>
    </div>
  );
}

function DespachoPendingItem({ apiConfig, item }: { apiConfig: ApiConfig; item: DriverDespachoPending }) {
  const router = useRouter();
  const [distanceKm, setDistanceKm] = useState(item.distanceKm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canUseApi = Boolean(apiConfig.tenantId);

  async function recordDespacho() {
    if (!apiConfig.tenantId) {
      setError("Acção indisponível sem API.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const reference = `driver-despacho:${item.tripId}:${Number(distanceKm).toFixed(2)}`;
      const response = await fetch(`${apiConfig.apiBaseUrl}/api/v1/trips/${item.tripId}/driver-despacho`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": reference,
          "X-Tenant-Id": apiConfig.tenantId,
        },
        body: JSON.stringify({
          distance_km: Number(distanceKm),
          request_reference: reference,
          notes: `Despacho lançado no painel de Custos e Margem para ${Number(distanceKm)} km.`,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nao foi possivel lançar o despacho.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cost-item despacho-cost-item">
      <div>
        <strong>{shortReference(item.tripId)}</strong>
        <span>{item.route}</span>
        <small>
          {item.vehiclePlate ?? "Sem viatura"} · {item.driverName ?? "Sem motorista"} ·{" "}
          {statusLabel(item.status)}
        </small>
      </div>
      <div className="despacho-launch">
        <label>
          Km
          <input
            min={item.minLongCourseKm}
            type="number"
            value={distanceKm}
            onChange={(event) => setDistanceKm(Number(event.target.value || 0))}
          />
        </label>
        <button className="tool-btn primary" disabled={busy || !canUseApi} onClick={recordDespacho} type="button">
          <Save size={15} />
          {busy ? "A lançar" : "Lançar"}
        </button>
        {error ? <small className="error-text">{error}</small> : null}
      </div>
    </div>
  );
}

function formatMoney(value: number) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: "MZN",
    maximumFractionDigits: 0,
  }).format(value);
}

function shortReference(value: string) {
  return value.length > 8 ? value.slice(0, 8).toUpperCase() : value;
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    planned: "Planeada",
    dispatched: "Saida autorizada",
    in_progress: "Em execução",
    delayed: "Atrasada",
    incident: "Com incidente",
    delivered: "Entregue",
    closed: "Fechada",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}
