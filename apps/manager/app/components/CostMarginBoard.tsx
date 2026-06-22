"use client";

import { AlertTriangle, Banknote, Calculator, ReceiptText, Save, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/app/components/ui/Button";

import type {
  ControlTowerLoadResult,
  DriverDespachoPending,
  NegativeMarginTrip,
} from "../lib/control-tower-api";
import { KpiCard } from "@/app/components/ui/KpiCard";
import { PageHeader } from "@/app/components/ui/PageHeader";
import { SectionHeader } from "@/app/components/ui/SectionHeader";
import { MonoCell, MoneyCell } from "@/app/components/ui/MonoCell";
import { EmptyStateInline } from "@/app/components/ui/EmptyState";

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
    <section className="mt-6" aria-labelledby="cost-margin-title">
      <PageHeader
        eyebrow="Custos e Margem"
        title="Margem operacional"
        description="Custos reais, despacho do motorista e viagens que exigem reconciliação."
        actions={
          <span className="flex items-center gap-1.5 text-[12px] text-muted">
            <Calculator size={14} />
            {summary.costsReconciledTrips} reconciliadas
          </span>
        }
      />

      <div
        className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3 mb-4"
        aria-label="Indicadores de custos e margem"
      >
        <KpiCard
          icon={<ReceiptText size={16} />}
          label="Custo real"
          value={formatMoney(summary.transportCostTotal)}
          semantic="default"
        />
        <KpiCard
          icon={<Banknote size={16} />}
          label="Receita"
          value={formatMoney(summary.contractRevenueTotal)}
          semantic="success"
        />
        <KpiCard
          icon={<Calculator size={16} />}
          label="Margem"
          value={formatMoney(summary.marginTotal)}
          semantic={summary.marginTotal < 0 ? "error" : "success"}
        />
        <KpiCard
          icon={<AlertTriangle size={16} />}
          label="Por reconciliar"
          value={summary.closedTripsUnreconciled.toString()}
          semantic="warning"
        />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)] gap-[14px]">
        <article className="min-w-0 bg-surface border border-border rounded-lg overflow-hidden">
          <SectionHeader
            title="Despacho por lançar"
            count={queues.driverDespachoPending.length}
          />
          <div className="cost-list p-[14px]">
            {queues.driverDespachoPending.length === 0 ? (
              <EmptyStateInline label="Sem viagens longas pendentes de despacho." />
            ) : null}
            {queues.driverDespachoPending.map((item) => (
              <DespachoPendingItem apiConfig={apiConfig} item={item} key={item.tripId} />
            ))}
          </div>
        </article>

        <article className="min-w-0 bg-surface border border-border rounded-lg overflow-hidden">
          <SectionHeader
            title="Margem negativa"
            count={summary.negativeMarginTrips}
          />
          <div className="cost-list p-[14px]">
            {queues.negativeMarginTrips.length === 0 ? (
              <EmptyStateInline label="Sem viagens reconciliadas com margem negativa." />
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
    <div className="min-w-0 grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center p-[10px] border border-border rounded-lg bg-surface mb-2 last:mb-0">
      <div>
        <MonoCell size="xs" className="block font-semibold [overflow-wrap:anywhere]">{shortReference(item.tripId)}</MonoCell>
        <span className="block [overflow-wrap:anywhere] text-muted text-[12px]">{item.route}</span>
        <small className="block [overflow-wrap:anywhere] text-muted text-[12px]">
          {item.vehiclePlate ? <MonoCell size="xs">{item.vehiclePlate}</MonoCell> : "Sem viatura"} · {item.driverName ?? "Sem motorista"}
        </small>
      </div>
      <div className="grid gap-2 justify-items-end">
        <dl className="grid grid-cols-3 gap-2 m-0 min-w-[240px]">
          <div>
            <dt className="text-[12px] text-muted m-0">Custo</dt>
            <dd className="mt-[3px] m-0"><MoneyCell value={item.transportCost} semantic="cost" /></dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted m-0">Receita</dt>
            <dd className="mt-[3px] m-0"><MoneyCell value={item.revenue} semantic="revenue" /></dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted m-0">Margem</dt>
            <dd className="mt-[3px] m-0"><MoneyCell value={item.margin} semantic="error" /></dd>
          </div>
        </dl>
        <Button
          variant="primary"
          disabled={busy || !canUseApi}
          onClick={approveNegativeMargin}
          type="button"
        >
          <ShieldCheck size={15} />
          {busy ? "A aprovar" : "Aprovar"}
        </Button>
        {error ? <small className="text-error text-xs font-bold [overflow-wrap:anywhere]">{error}</small> : null}
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
    <div className="min-w-0 grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center p-[10px] border border-border rounded-lg bg-surface mb-2 last:mb-0">
      <div>
        <MonoCell size="xs" className="block font-semibold [overflow-wrap:anywhere]">{shortReference(item.tripId)}</MonoCell>
        <span className="block [overflow-wrap:anywhere] text-muted text-[12px]">{item.route}</span>
        <small className="block [overflow-wrap:anywhere] text-muted text-[12px]">
          {item.vehiclePlate ? <MonoCell size="xs">{item.vehiclePlate}</MonoCell> : "Sem viatura"} · {item.driverName ?? "Sem motorista"} ·{" "}
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
        <Button variant="primary" disabled={busy || !canUseApi} onClick={recordDespacho} type="button">
          <Save size={15} />
          {busy ? "A lançar" : "Lançar"}
        </Button>
        {error ? <small className="text-error text-xs font-bold [overflow-wrap:anywhere]">{error}</small> : null}
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
