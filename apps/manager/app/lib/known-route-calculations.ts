import type { KnownRoute, LoadCondition } from "./known-routes-api";

export function calcDespacho(
  distanceKm: number,
  tiers: Array<{
    min_km: number;
    max_km: number | null;
    amount: number;
    label: string | null;
  }>,
  route?: Pick<KnownRoute, "despacho_vazio" | "despacho_carregado">,
  condition?: LoadCondition,
): { amount: number; label: string | null; source: "override" | "tier" } | null {
  if (route && condition === "vazio" && route.despacho_vazio !== null) {
    return { amount: route.despacho_vazio, label: "Vazio (rota)", source: "override" };
  }
  if (route && condition === "carregado" && route.despacho_carregado !== null) {
    return { amount: route.despacho_carregado, label: "Carregado (rota)", source: "override" };
  }
  const tier = tiers.find(
    (item) =>
      distanceKm >= item.min_km &&
      (item.max_km === null || distanceKm < item.max_km),
  );
  return tier
    ? { amount: tier.amount, label: tier.label, source: "tier" }
    : null;
}

export function calcFuel(
  distanceKm: number,
  avgConsumptionL100km: number | null,
  avgFuelLitersOverride: number | null,
): number | null {
  if (avgFuelLitersOverride !== null) return avgFuelLitersOverride;
  if (!avgConsumptionL100km) return null;
  return Math.round(((distanceKm * avgConsumptionL100km) / 100) * 10) / 10;
}
