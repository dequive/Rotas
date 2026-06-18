import { apiFetch } from "./api";
import { throwWhenDemoFallbackDisabled } from "./runtime-guards";
import { getApiConfig } from "./billing-api";

export interface DriverDespachoTier {
  min_km: number;
  max_km: number | null;
  amount: number;
  label: string | null;
  code: string | null;
}

export interface DriverDespachoTable {
  enabled: boolean;
  table_name: string;
  table_reference: string | null;
  currency: string;
  effective_from: string | null;
  min_long_course_km: number;
  tiers: DriverDespachoTier[];
  entry_mode?: "manual" | string | null;
}

export interface DriverDespachoTableLoadResult {
  configured: boolean;
  table: DriverDespachoTable;
  source: "api" | "fallback";
  message: string | null;
}

const fallbackTable: DriverDespachoTable = {
  enabled: true,
  table_name: "Tabela de despacho",
  table_reference: "Por preencher",
  currency: "MZN",
  effective_from: null,
  min_long_course_km: 100,
  entry_mode: "manual",
  tiers: [
    {
      min_km: 100,
      max_km: 250,
      amount: 500,
      label: "Longo curso curto",
      code: "LC-100",
    },
    {
      min_km: 250,
      max_km: 500,
      amount: 1000,
      label: "Longo curso medio",
      code: "LC-250",
    },
    {
      min_km: 500,
      max_km: null,
      amount: 1500,
      label: "Longo curso nacional",
      code: "LC-500",
    },
  ],
};

interface ApiDriverDespachoTableResponse {
  configured: boolean;
  table: Partial<DriverDespachoTable> | null;
}

export async function loadDriverDespachoTable(): Promise<DriverDespachoTableLoadResult> {
  try {
    const payload = await apiFetch<ApiDriverDespachoTableResponse>("/api/v1/tenants/me/driver-despacho-table");
    return { configured: payload.configured, table: normalizeTable(payload.table), source: "api", message: null };
  } catch (caught) {
    throwWhenDemoFallbackDisabled("Tabela de despacho", caught);
    return {
      configured: false,
      table: fallbackTable,
      source: "fallback",
      message: caught instanceof Error ? `Tabela de despacho: ${caught.message}` : "Indisponível.",
    };
  }
}

function normalizeTable(table: Partial<DriverDespachoTable> | null): DriverDespachoTable {
  if (!table) {
    return fallbackTable;
  }
  const tiers = Array.isArray(table.tiers) && table.tiers.length > 0 ? table.tiers : fallbackTable.tiers;
  return {
    enabled: table.enabled ?? true,
    table_name: table.table_name ?? fallbackTable.table_name,
    table_reference: table.table_reference ?? fallbackTable.table_reference,
    currency: table.currency ?? fallbackTable.currency,
    effective_from: table.effective_from ?? null,
    min_long_course_km: Number(table.min_long_course_km ?? fallbackTable.min_long_course_km),
    entry_mode: table.entry_mode ?? "manual",
    tiers: tiers.map((tier) => ({
      min_km: Number(tier.min_km ?? 0),
      max_km: tier.max_km === null || tier.max_km === undefined ? null : Number(tier.max_km),
      amount: Number(tier.amount ?? 0),
      label: tier.label ?? null,
      code: tier.code ?? null,
    })),
  };
}
