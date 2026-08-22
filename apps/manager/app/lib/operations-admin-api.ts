import { apiFetch } from "./api";

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
  source: "api";
  message: string | null;
}

const unconfiguredTable: DriverDespachoTable = {
  enabled: false,
  table_name: "",
  table_reference: null,
  currency: "MZN",
  effective_from: null,
  min_long_course_km: 0,
  entry_mode: "manual",
  tiers: [],
};

interface ApiDriverDespachoTableResponse {
  configured: boolean;
  table: Partial<DriverDespachoTable> | null;
}

export async function loadDriverDespachoTable(): Promise<DriverDespachoTableLoadResult> {
  const payload = await apiFetch<ApiDriverDespachoTableResponse>(
    "/api/v1/tenants/me/driver-despacho-table",
  );
  return {
    configured: payload.configured,
    table: normalizeTable(payload.table),
    source: "api",
    message: null,
  };
}

function normalizeTable(table: Partial<DriverDespachoTable> | null): DriverDespachoTable {
  if (!table) {
    return unconfiguredTable;
  }
  const tiers = Array.isArray(table.tiers) ? table.tiers : [];
  return {
    enabled: table.enabled ?? false,
    table_name: table.table_name ?? "",
    table_reference: table.table_reference ?? null,
    currency: table.currency ?? "MZN",
    effective_from: table.effective_from ?? null,
    min_long_course_km: Number(table.min_long_course_km ?? 0),
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
