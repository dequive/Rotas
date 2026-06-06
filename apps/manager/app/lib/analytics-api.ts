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
