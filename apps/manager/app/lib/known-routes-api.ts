import { apiFetch } from "./api";

export interface KnownRoute {
  id: string;
  origin: string;
  destination: string;
  distance_km: number;
  avg_fuel_liters: number | null;
  despacho_vazio: number | null;
  despacho_carregado: number | null;
  notes: string | null;
  is_active: boolean;
}

export interface CreateKnownRoutePayload {
  origin: string;
  destination: string;
  distance_km: number;
  avg_fuel_liters?: number;
  despacho_vazio?: number;
  despacho_carregado?: number;
  notes?: string;
}

export async function loadKnownRoutes(): Promise<KnownRoute[]> {
  try {
    return await apiFetch<KnownRoute[]>("/api/v1/known-routes", { revalidate: 30 });
  } catch {
    return [];
  }
}

export type LoadCondition = "vazio" | "carregado";

export function calcDespacho(
  distanceKm: number,
  tiers: Array<{ min_km: number; max_km: number | null; amount: number; label: string | null }>,
  route?: Pick<KnownRoute, "despacho_vazio" | "despacho_carregado">,
  condition?: LoadCondition,
): { amount: number; label: string | null; source: "override" | "tier" } | null {
  // Per-route override takes priority over global tiers
  if (route && condition === "vazio" && route.despacho_vazio !== null) {
    return { amount: route.despacho_vazio, label: "Vazio (rota)", source: "override" };
  }
  if (route && condition === "carregado" && route.despacho_carregado !== null) {
    return { amount: route.despacho_carregado, label: "Carregado (rota)", source: "override" };
  }
  // Fallback to tenant-level distance tiers
  const tier = tiers.find(
    (t) => distanceKm >= t.min_km && (t.max_km === null || distanceKm < t.max_km)
  );
  return tier ? { amount: tier.amount, label: tier.label, source: "tier" } : null;
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
