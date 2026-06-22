"use client";

import { Plus, Save, Trash2, WalletCards } from "lucide-react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

import type {
  DriverDespachoTable,
  DriverDespachoTableLoadResult,
  DriverDespachoTier,
} from "../lib/operations-admin-api";

interface ApiConfig {
  apiBaseUrl: string;
  tenantId: string | null;
  token: string;
}

interface DriverDespachoTableAdminProps {
  apiConfig: ApiConfig;
  result: DriverDespachoTableLoadResult;
}

export function DriverDespachoTableAdmin({ apiConfig, result }: DriverDespachoTableAdminProps) {
  const router = useRouter();
  const [table, setTable] = useState<DriverDespachoTable>(result.table);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const canUseApi = Boolean(apiConfig.tenantId);
  const totalTiers = table.tiers.length;
  const highestAmount = useMemo(
    () => Math.max(0, ...table.tiers.map((tier) => Number(tier.amount || 0))),
    [table.tiers],
  );

  function updateTable(field: keyof DriverDespachoTable, value: string | boolean | number | null) {
    setSaved(false);
    setTable((current) => ({ ...current, [field]: value }));
  }

  function updateTier(index: number, field: keyof DriverDespachoTier, value: string | number | null) {
    setSaved(false);
    setTable((current) => ({
      ...current,
      tiers: current.tiers.map((tier, tierIndex) =>
        tierIndex === index ? { ...tier, [field]: value } : tier,
      ),
    }));
  }

  function addTier() {
    const last = table.tiers.at(-1);
    const min = last?.max_km ?? (last ? last.min_km + 100 : table.min_long_course_km);
    setSaved(false);
    setTable((current) => ({
      ...current,
      tiers: [
        ...current.tiers,
        {
          min_km: min,
          max_km: null,
          amount: 0,
          label: "",
          code: "",
        },
      ],
    }));
  }

  function removeTier(index: number) {
    setSaved(false);
    setTable((current) => ({
      ...current,
      tiers: current.tiers.filter((_, tierIndex) => tierIndex !== index),
    }));
  }

  async function saveTable() {
    if (!apiConfig.tenantId) {
      setError("Configure ROTAS_TENANT_ID para gravar a tabela.");
      return;
    }
    if (table.tiers.length === 0) {
      setError("A tabela precisa de pelo menos uma faixa.");
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const response = await fetch(`${apiConfig.apiBaseUrl}/api/v1/tenants/me/driver-despacho-table`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${apiConfig.token}`,
          "Content-Type": "application/json",
          "X-Tenant-Id": apiConfig.tenantId,
        },
        body: JSON.stringify({
          ...table,
          currency: table.currency.toUpperCase(),
          tiers: table.tiers.map((tier) => ({
            min_km: Number(tier.min_km),
            max_km: tier.max_km === null || tier.max_km === undefined ? null : Number(tier.max_km),
            amount: Number(tier.amount),
            label: tier.label || null,
            code: tier.code || null,
          })),
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const message =
          payload?.error?.message ?? payload?.detail ?? `API respondeu HTTP ${response.status}`;
        throw new Error(message);
      }
      setSaved(true);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Nao foi possivel gravar a tabela.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pt-6 mt-5 border-t border-border" aria-labelledby="driver-despacho-title">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div className="min-w-0">
          <span className="text-amber text-[11px] font-black uppercase">Administracao Operacional</span>
          <h2 id="driver-despacho-title" className="m-0 mt-0.5 text-[21px]">Tabela manual de despacho</h2>
          <p className="m-0 mt-1 text-muted">Faixas de subsidio de viagem preenchidas manualmente pelo transportador.</p>
        </div>
        <span className="flex-none inline-flex items-center gap-[7px] px-2.5 py-2 text-[#2563eb] bg-[#eff6ff] border border-[#bfdbfe] rounded-md text-[12px] font-black">
          <WalletCards size={15} />
          {result.configured ? "Configurada" : "Por preencher"}
        </span>
      </div>

      <div className={result.source === "api"
        ? "border rounded-md min-h-[36px] inline-flex items-center gap-2 px-2.5 py-[7px] mb-3.5 text-[13px] max-w-full bg-success-bg text-success border-success-border"
        : "border rounded-md min-h-[36px] inline-flex items-center gap-2 px-2.5 py-[7px] mb-3.5 text-[13px] max-w-full bg-warning-bg text-warning border-warning-border"
      }>
        <WalletCards size={15} />
        <span className="flex-1 min-w-0 [overflow-wrap:anywhere]">
          {result.source === "api"
            ? "Tabela carregada da API ROTAS."
            : result.message}
        </span>
      </div>

      <div className="grid gap-3.5" style={{ gridTemplateColumns: "minmax(280px,0.45fr) minmax(0,1fr)" }}>
        <article className="min-w-0 p-3.5 bg-surface border border-border rounded-lg">
          <div className="grid gap-2 mb-3" style={{ gridTemplateColumns: "repeat(2,minmax(0,1fr)) minmax(92px,auto)" }}>
            <div className="min-h-[48px] p-2 border border-border rounded-md bg-surface">
              <span className="block text-muted text-[12px]">Faixas</span>
              <strong className="block mt-0.5 text-[14px]">{totalTiers}</strong>
            </div>
            <div className="min-h-[48px] p-2 border border-border rounded-md bg-surface">
              <span className="block text-muted text-[12px]">Valor maior</span>
              <strong className="block mt-0.5 text-[14px]">{formatMoney(highestAmount, table.currency)}</strong>
            </div>
            <label className="min-h-[48px] p-2 border border-border rounded-md bg-surface inline-flex items-center justify-center gap-2 text-[13px] font-black cursor-pointer">
              <input
                checked={table.enabled}
                onChange={(event) => updateTable("enabled", event.target.checked)}
                type="checkbox"
                className="w-4 h-4 accent-amber"
              />
              Activa
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
              Nome da tabela
              <input
                value={table.table_name}
                onChange={(event) => updateTable("table_name", event.target.value)}
                className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
              />
            </label>
            <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
              Referencia
              <input
                value={table.table_reference ?? ""}
                onChange={(event) => updateTable("table_reference", event.target.value)}
                className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
              />
            </label>
            <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
              Moeda
              <input
                maxLength={3}
                value={table.currency}
                onChange={(event) => updateTable("currency", event.target.value.toUpperCase())}
                className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20 font-mono"
              />
            </label>
            <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
              Vigencia
              <input
                type="date"
                value={table.effective_from ?? ""}
                onChange={(event) => updateTable("effective_from", event.target.value || null)}
                className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
              />
            </label>
            <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
              Minimo longo curso
              <input
                min={0}
                type="number"
                value={table.min_long_course_km}
                onChange={(event) =>
                  updateTable("min_long_course_km", Number(event.target.value || 0))
                }
                className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
              />
            </label>
          </div>
        </article>

        <article className="min-w-0 p-3.5 bg-surface border border-border rounded-lg">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h3 className="text-base font-semibold m-0">Faixas de distancia</h3>
            <Button
              className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md bg-surface hover:bg-surface-2"
              onClick={addTier}
              type="button"
              variant="outline"
              size="sm"
            >
              <Plus size={16} />
              Faixa
            </Button>
          </div>

          <div className="grid gap-2">
            {table.tiers.map((tier, index) => (
              <div
                className="grid gap-2 items-end p-2.5 border border-border rounded-lg bg-surface"
                style={{ gridTemplateColumns: "minmax(72px,0.65fr) minmax(72px,0.65fr) minmax(88px,0.8fr) minmax(82px,0.75fr) minmax(140px,1.2fr) 38px" }}
                key={`${tier.code ?? "tier"}-${index}`}
              >
                <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
                  Min km
                  <input
                    min={0}
                    type="number"
                    value={tier.min_km}
                    onChange={(event) => updateTier(index, "min_km", Number(event.target.value || 0))}
                    className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
                  />
                </label>
                <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
                  Max km
                  <input
                    min={0}
                    type="number"
                    value={tier.max_km ?? ""}
                    onChange={(event) =>
                      updateTier(
                        index,
                        "max_km",
                        event.target.value === "" ? null : Number(event.target.value),
                      )
                    }
                    className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
                  />
                </label>
                <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
                  Valor
                  <input
                    min={0}
                    type="number"
                    value={tier.amount}
                    onChange={(event) => updateTier(index, "amount", Number(event.target.value || 0))}
                    className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
                  />
                </label>
                <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
                  Codigo
                  <input
                    value={tier.code ?? ""}
                    onChange={(event) => updateTier(index, "code", event.target.value)}
                    className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
                  />
                </label>
                <label className="min-w-0 grid gap-1 text-[12px] font-bold text-muted">
                  Nome
                  <input
                    value={tier.label ?? ""}
                    onChange={(event) => updateTier(index, "label", event.target.value)}
                    className="w-full min-w-0 min-h-[34px] px-2 border border-border rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20"
                  />
                </label>
                <Button
                  className="text-error hover:text-error"
                  disabled={table.tiers.length === 1}
                  onClick={() => removeTier(index)}
                  title="Remover faixa"
                  type="button"
                  variant="ghost"
                  size="sm"
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            ))}
          </div>

          <div className="flex items-center flex-wrap gap-2.5 mt-3">
            <Button
              className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md bg-surface hover:bg-surface-2"
              disabled={busy || !canUseApi}
              onClick={saveTable}
              type="button"
              variant="outline"
              size="sm"
            >
              <Save size={16} />
              {busy ? "A gravar" : "Gravar tabela"}
            </Button>
            {saved ? <small className="text-success text-xs">Tabela gravada.</small> : null}
            {error ? <small className="text-error text-xs">{error}</small> : null}
          </div>
        </article>
      </div>
    </section>
  );
}

function formatMoney(value: number, currency: string) {
  return new Intl.NumberFormat("pt-MZ", {
    style: "currency",
    currency: currency || "MZN",
    maximumFractionDigits: 0,
  }).format(value);
}
