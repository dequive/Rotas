import { apiFetch } from "./api";

// --- Types ---

export interface CostPerKmByVehicle {
  [vehicleId: string]: number;
}

export interface DriverSummaryRow {
  driverId: string;
  driverName: string;
  tripsCount: number;
  totalKm: number;
  totalCost: number;
}

export interface FleetKpis {
  costPerKm: CostPerKmByVehicle;
  fleetUtilization: number;
  lPer100Km: number;
  tripsCompleted: number;
  driverSummary: DriverSummaryRow[];
}

export interface DocumentExpiryItem {
  entityId: string;
  entityName: string; // plate or full_name
  entityType: "vehicle" | "driver";
  documentType: string;
  expiresAt: string;
  daysUntilExpiry: number;
  severity: "warning" | "urgent" | "critical";
}

export interface DocumentExpiryResponse {
  vehicles: DocumentExpiryItem[];
  drivers: DocumentExpiryItem[];
}

// --- API functions ---

export async function getFleetKpis(params: {
  periodStart: string;
  periodEnd: string;
  vehicleId?: string;
  driverId?: string;
}): Promise<FleetKpis> {
  const qs = new URLSearchParams({
    period_start: params.periodStart,
    period_end: params.periodEnd,
    ...(params.vehicleId ? { vehicle_id: params.vehicleId } : {}),
    ...(params.driverId ? { driver_id: params.driverId } : {}),
  });
  const raw = await apiFetch<Record<string, unknown>>(`/api/v1/analytics/kpis?${qs}`);
  // Explicit snake_case → camelCase mapping. apiFetch does NOT auto-transform.
  // cost_per_km is list[{vehicle_id, cost_per_km, ...}] from backend — transform to Record<vehicleId, cost>
  return {
    costPerKm: Object.fromEntries(
      ((raw.cost_per_km ?? []) as Record<string, unknown>[]).map((r) => [
        r.vehicle_id,
        r.cost_per_km,
      ]),
    ),
    fleetUtilization: raw.fleet_utilization as number,
    lPer100Km: raw.l_per_100km as number,
    tripsCompleted: raw.trips_completed as number,
    driverSummary: ((raw.driver_summary ?? []) as Record<string, unknown>[]).map((d) => ({
      driverId: d.driver_id as string,
      driverName: d.driver_name as string,
      tripsCount: d.trip_count as number,
      totalKm: d.total_km as number,
      totalCost: d.total_cost as number,
    })),
  };
}

// --- New types for analytics dashboard (Phase 18) ---

export interface RouteProfitabilityRow {
  origin: string;
  destination: string;
  trip_count: number;
  avg_cost: number;
}

export interface ContractMarginRow {
  billing_document_id: string;
  total_revenue: number;
  total_cost: number;
  gross_margin: number;
}

export interface TopDriverRow {
  driver_id: string;
  trip_count: number;
  total_km: number;
}

export interface AnalyticsDashboard extends FleetKpis {
  route_profitability: RouteProfitabilityRow[];
  contract_margins: ContractMarginRow[];
  delivery_nps: number | null;
  top_drivers: TopDriverRow[];
}

export async function getAnalyticsDashboard(params: {
  periodStart: string;
  periodEnd: string;
  vehicleId?: string;
  driverId?: string;
}): Promise<AnalyticsDashboard> {
  const qs = new URLSearchParams({
    period_start: params.periodStart,
    period_end: params.periodEnd,
    ...(params.vehicleId ? { vehicle_id: params.vehicleId } : {}),
    ...(params.driverId ? { driver_id: params.driverId } : {}),
  });
  const raw = await apiFetch<Record<string, unknown>>(
    `/api/v1/analytics/dashboard?${qs}`,
  );
  return {
    // FleetKpis fields
    costPerKm: Object.fromEntries(
      ((raw.cost_per_km ?? []) as Record<string, unknown>[]).map((r) => [
        r.vehicle_id,
        r.cost_per_km,
      ]),
    ),
    fleetUtilization: (raw.fleet_utilization as number) ?? 0,
    lPer100Km: (raw.l_per_100km as number) ?? 0,
    tripsCompleted: (raw.trips_completed as number) ?? 0,
    driverSummary: ((raw.driver_summary ?? []) as Record<string, unknown>[]).map(
      (d) => ({
        driverId: d.driver_id as string,
        driverName: (d.driver_name as string) ?? (d.driver_id as string),
        tripsCount: d.trip_count as number,
        totalKm: d.total_km as number,
        totalCost: d.total_cost as number,
      }),
    ),
    // New dashboard fields
    route_profitability: (
      (raw.route_profitability ?? []) as Record<string, unknown>[]
    ).map((r) => ({
      origin: r.origin as string,
      destination: r.destination as string,
      trip_count: r.trip_count as number,
      avg_cost: r.avg_cost as number,
    })),
    contract_margins: (
      (raw.contract_margins ?? []) as Record<string, unknown>[]
    ).map((r) => ({
      billing_document_id: r.billing_document_id as string,
      total_revenue: r.total_revenue as number,
      total_cost: r.total_cost as number,
      gross_margin: r.gross_margin as number,
    })),
    delivery_nps:
      raw.delivery_nps !== null && raw.delivery_nps !== undefined
        ? (raw.delivery_nps as number)
        : null,
    top_drivers: ((raw.top_drivers ?? []) as Record<string, unknown>[]).map(
      (d) => ({
        driver_id: d.driver_id as string,
        trip_count: d.trip_count as number,
        total_km: d.total_km as number,
      }),
    ),
  };
}

export async function getDocumentExpiry(): Promise<DocumentExpiryResponse> {
  const raw = await apiFetch<unknown>("/api/v1/analytics/document-expiry");
  // Backend returns a flat list; map each item's snake_case fields to camelCase.
  const mapItem = (item: Record<string, unknown>): DocumentExpiryItem => ({
    entityId: item.entity_id as string,
    entityName: item.entity_name as string,
    entityType: item.entity_type as "vehicle" | "driver",
    documentType: item.document_type as string,
    expiresAt: item.expires_at as string,
    daysUntilExpiry: item.days_remaining as number,
    severity: item.severity as "warning" | "urgent" | "critical",
  });
  const items: DocumentExpiryItem[] = Array.isArray(raw)
    ? (raw as Record<string, unknown>[]).map(mapItem)
    : [];
  return {
    vehicles: items.filter((i) => i.entityType === "vehicle"),
    drivers: items.filter((i) => i.entityType === "driver"),
  };
}
