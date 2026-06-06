"use client";

import { Plus, Save, Trash2, WalletCards } from "lucide-react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

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
    <section className="domain-section admin-despacho" aria-labelledby="driver-despacho-title">
      <div className="domain-heading">
        <div className="title">
          <span className="eyebrow">Administracao Operacional</span>
          <h2 id="driver-despacho-title">Tabela manual de despacho</h2>
          <p>Faixas de subsidio de viagem preenchidas manualmente pelo transportador.</p>
        </div>
        <span className="module-state">
          <WalletCards size={15} />
          {result.configured ? "Configurada" : "Por preencher"}
        </span>
      </div>

      <div className={`data-source ${result.source}`}>
        <WalletCards size={15} />
        <span>
          {result.source === "api"
            ? "Tabela carregada da API ROTAS."
            : result.message}
        </span>
      </div>

      <div className="despacho-admin-grid">
        <article className="despacho-admin-panel">
          <div className="despacho-summary">
            <div>
              <span>Faixas</span>
              <strong>{totalTiers}</strong>
            </div>
            <div>
              <span>Valor maior</span>
              <strong>{formatMoney(highestAmount, table.currency)}</strong>
            </div>
            <label className="switch-row">
              <input
                checked={table.enabled}
                onChange={(event) => updateTable("enabled", event.target.checked)}
                type="checkbox"
              />
              Activa
            </label>
          </div>

          <div className="despacho-form-grid">
            <label>
              Nome da tabela
              <input
                value={table.table_name}
                onChange={(event) => updateTable("table_name", event.target.value)}
              />
            </label>
            <label>
              Referencia
              <input
                value={table.table_reference ?? ""}
                onChange={(event) => updateTable("table_reference", event.target.value)}
              />
            </label>
            <label>
              Moeda
              <input
                maxLength={3}
                value={table.currency}
                onChange={(event) => updateTable("currency", event.target.value.toUpperCase())}
              />
            </label>
            <label>
              Vigencia
              <input
                type="date"
                value={table.effective_from ?? ""}
                onChange={(event) => updateTable("effective_from", event.target.value || null)}
              />
            </label>
            <label>
              Minimo longo curso
              <input
                min={0}
                type="number"
                value={table.min_long_course_km}
                onChange={(event) =>
                  updateTable("min_long_course_km", Number(event.target.value || 0))
                }
              />
            </label>
          </div>
        </article>

        <article className="despacho-admin-panel">
          <div className="section-header">
            <h3 className="section-title">Faixas de distancia</h3>
            <button className="tool-btn" onClick={addTier} type="button">
              <Plus size={16} />
              Faixa
            </button>
          </div>

          <div className="despacho-tier-list">
            {table.tiers.map((tier, index) => (
              <div className="despacho-tier-row" key={`${tier.code ?? "tier"}-${index}`}>
                <label>
                  Min km
                  <input
                    min={0}
                    type="number"
                    value={tier.min_km}
                    onChange={(event) => updateTier(index, "min_km", Number(event.target.value || 0))}
                  />
                </label>
                <label>
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
                  />
                </label>
                <label>
                  Valor
                  <input
                    min={0}
                    type="number"
                    value={tier.amount}
                    onChange={(event) => updateTier(index, "amount", Number(event.target.value || 0))}
                  />
                </label>
                <label>
                  Codigo
                  <input
                    value={tier.code ?? ""}
                    onChange={(event) => updateTier(index, "code", event.target.value)}
                  />
                </label>
                <label className="tier-label">
                  Nome
                  <input
                    value={tier.label ?? ""}
                    onChange={(event) => updateTier(index, "label", event.target.value)}
                  />
                </label>
                <button
                  className="icon-btn danger"
                  disabled={table.tiers.length === 1}
                  onClick={() => removeTier(index)}
                  title="Remover faixa"
                  type="button"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>

          <div className="despacho-save-row">
            <button className="tool-btn primary" disabled={busy || !canUseApi} onClick={saveTable} type="button">
              <Save size={16} />
              {busy ? "A gravar" : "Gravar tabela"}
            </button>
            {saved ? <small className="success-text">Tabela gravada.</small> : null}
            {error ? <small className="error-text">{error}</small> : null}
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
