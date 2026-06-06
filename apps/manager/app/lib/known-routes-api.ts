import { apiFetch } from "./api";

export interface KnownRoute {
  id: string;
  origin: string;
  destination: string;
  distance_km: number;
  avg_fuel_liters: number | null;
  notes: string | null;
  is_active: boolean;
}

export interface CreateKnownRoutePayload {
  origin: string;
  destination: string;
  distance_km: number;
  avg_fuel_liters?: number;
  notes?: string;
}

export async function loadKnownRoutes(): Promise<KnownRoute[]> {
  try {
    return await apiFetch<KnownRoute[]>("/api/v1/known-routes", { revalidate: 30 });
  } catch {
    return [];
  }
}

export function calcDespacho(
  distanceKm: number,
  tiers: Array<{ min_km: number; max_km: number | null; amount: number; label: string | null }>
): { amount: number; label: string | null } | null {
  const tier = tiers.find(
    (t) => distanceKm >= t.min_km && (t.max_km === null || distanceKm < t.max_km)
  );
  return tier ? { amount: tier.amount, label: tier.label } : null;
}

export function calcFuel(
  distanceKm: number,
  avgConsumptionL100km: number | null,
  avgFuelLitersOverride: number | null
): number | null {
  if (avgFuelLitersOverride !== null) return avgFuelLitersOverride;
  if (!avgConsumptionL100km) return null;
  return Math.round((distanceKm * avgConsumptionL100km) / 100 * 10) / 10;
}
