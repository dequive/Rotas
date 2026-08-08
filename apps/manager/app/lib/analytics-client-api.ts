"use client";

import { bffFetch } from "./bff";
import type {
  AnalyticsDashboard,
  DocumentExpiryItem,
  DocumentExpiryResponse,
} from "./analytics-api";

export async function getAnalyticsDashboard(params: {
  periodStart: string;
  periodEnd: string;
  vehicleId?: string;
  driverId?: string;
}): Promise<AnalyticsDashboard> {
  const query = new URLSearchParams({
    period_start: params.periodStart,
    period_end: params.periodEnd,
    ...(params.vehicleId ? { vehicle_id: params.vehicleId } : {}),
    ...(params.driverId ? { driver_id: params.driverId } : {}),
  });
  const raw = await bffFetch<Record<string, unknown>>(
    `/api/v1/analytics/dashboard?${query}`,
  );
  return {
    costPerKm: Object.fromEntries(
      ((raw.cost_per_km ?? []) as Record<string, unknown>[]).map((item) => [
        item.vehicle_id,
        item.cost_per_km,
      ]),
    ),
    fleetUtilization: (raw.fleet_utilization as number) ?? 0,
    lPer100Km: (raw.l_per_100km as number) ?? 0,
    tripsCompleted: (raw.trips_completed as number) ?? 0,
    driverSummary: ((raw.driver_summary ?? []) as Record<string, unknown>[]).map(
      (item) => ({
        driverId: item.driver_id as string,
        driverName: (item.driver_name as string) ?? (item.driver_id as string),
        tripsCount: item.trip_count as number,
        totalKm: item.total_km as number,
        totalCost: item.total_cost as number,
      }),
    ),
    route_profitability: (
      (raw.route_profitability ?? []) as Record<string, unknown>[]
    ).map((item) => ({
      origin: item.origin as string,
      destination: item.destination as string,
      trip_count: item.trip_count as number,
      avg_cost: item.avg_cost as number,
    })),
    contract_margins: (
      (raw.contract_margins ?? []) as Record<string, unknown>[]
    ).map((item) => ({
      billing_document_id: item.billing_document_id as string,
      invoice_number: (item.invoice_number as string | null) ?? null,
      total_revenue: item.total_revenue as number,
      total_cost: item.total_cost as number,
      gross_margin: item.gross_margin as number,
    })),
    delivery_nps:
      raw.delivery_nps === null || raw.delivery_nps === undefined
        ? null
        : (raw.delivery_nps as number),
    top_drivers: ((raw.top_drivers ?? []) as Record<string, unknown>[]).map(
      (item) => ({
        driver_id: item.driver_id as string,
        driver_name: (item.driver_name as string | null) ?? null,
        trip_count: item.trip_count as number,
        total_km: item.total_km as number,
      }),
    ),
  };
}

export async function getDocumentExpiry(): Promise<DocumentExpiryResponse> {
  const raw = await bffFetch<unknown>("/api/v1/analytics/document-expiry");
  const items: DocumentExpiryItem[] = Array.isArray(raw)
    ? (raw as Record<string, unknown>[]).map((item) => ({
        entityId: item.entity_id as string,
        entityName: item.entity_name as string,
        entityType: item.entity_type as "vehicle" | "driver",
        documentType: item.document_type as string,
        expiresAt: item.expires_at as string,
        daysUntilExpiry: item.days_remaining as number,
        severity: item.severity as "warning" | "urgent" | "critical",
      }))
    : [];
  return {
    vehicles: items.filter((item) => item.entityType === "vehicle"),
    drivers: items.filter((item) => item.entityType === "driver"),
  };
}
