"use client";

import { Info, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/app/components/ui/Button";
import { ModalDialog } from "@/app/components/ui/ModalDialog";
import type { KnownRoute } from "../lib/known-routes-api";
import { calcDespacho, calcFuel } from "../lib/known-routes-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";
import type { Contract } from "../lib/contracts-api";
import type { DriverDespachoTier } from "../lib/operations-admin-api";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

interface AutoFill {
  origin: string;
  destination: string;
  distanceKm: string;
  despachoAmount: number | null;
  despachoLabel: string | null;
  fuelLiters: number | null;
}

function computeAutoFill(
  route: KnownRoute,
  vehicle: Vehicle | undefined,
  tiers: DriverDespachoTier[]
): AutoFill {
  const despacho = calcDespacho(route.distance_km, tiers);
  const fuel = calcFuel(
    route.distance_km,
    vehicle?.avg_consumption_target ?? null,
    route.avg_fuel_liters
  );
  return {
    origin: route.origin,
    destination: route.destination,
    distanceKm: String(route.distance_km),
    despachoAmount: despacho?.amount ?? null,
    despachoLabel: despacho?.label ?? null,
    fuelLiters: fuel,
  };
}

function money(v: number) {
  return new Intl.NumberFormat("pt-MZ", { style: "currency", currency: "MZN", maximumFractionDigits: 0 }).format(v);
}

export function TripFormModal({
  vehicles,
  drivers,
  contracts,
  knownRoutes,
  despacheTiers,
}: {
  vehicles: Vehicle[];
  drivers: Driver[];
  contracts: Contract[];
  knownRoutes: KnownRoute[];
  despacheTiers: DriverDespachoTier[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState("");
  const [autoFill, setAutoFill] = useState<AutoFill | null>(null);
  const [manualOrigin, setManualOrigin] = useState("");
  const [manualDest, setManualDest] = useState("");
  const [manualDist, setManualDist] = useState("");

  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId);

  function handleRouteSelect(routeId: string) {
    if (!routeId) { setAutoFill(null); return; }
    const route = knownRoutes.find((r) => r.id === routeId);
    if (!route) return;
    const fill = computeAutoFill(route, selectedVehicle, despacheTiers);
    setAutoFill(fill);
    setManualOrigin(fill.origin);
    setManualDest(fill.destination);
    setManualDist(fill.distanceKm);
  }

  function handleVehicleChange(vehicleId: string) {
    setSelectedVehicleId(vehicleId);
    if (autoFill) {
      const route = knownRoutes.find(
        (r) => r.origin === autoFill.origin && r.destination === autoFill.destination
      );
      if (route) {
        const vehicle = vehicles.find((v) => v.id === vehicleId);
        setAutoFill(computeAutoFill(route, vehicle, despacheTiers));
      }
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      vehicle_id: fd.get("vehicle_id"),
      driver_id: fd.get("driver_id"),
      origin: fd.get("origin"),
      destination: fd.get("destination"),
      cargo_type: fd.get("cargo_type") || undefined,
      load_state: fd.get("load_state") || undefined,
      contract_id: fd.get("contract_id") || undefined,
      distance_km: fd.get("distance_km") ? Number(fd.get("distance_km")) : undefined,
      despacho_amount: autoFill?.despachoAmount ?? undefined,
      fuel_estimate_liters: autoFill?.fuelLiters ?? undefined,
    };
    try {
      const res = await fetch("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao criar viagem."); return; }
      setOpen(false);
      setAutoFill(null);
      setSelectedVehicleId("");
      setManualOrigin(""); setManualDest(""); setManualDist("");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  const activeVehicles = vehicles.filter((v) => v.status === "active");
  const activeDrivers = drivers.filter((d) => d.status === "active");

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        <Plus size={16} /> Nova viagem
      </Button>

      <ModalDialog open={open} onClose={() => setOpen(false)} title="Nova viagem" className="modal-wide">
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          {knownRoutes.length > 0 && (
            <label className={lbl}>
              Destino do catálogo
              <select onChange={(e) => handleRouteSelect(e.target.value)} defaultValue="" className={inp}>
                <option value="">— Seleccionar destino (preenche automaticamente) —</option>
                {knownRoutes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.origin} → {r.destination} ({r.distance_km} km)
                  </option>
                ))}
              </select>
            </label>
          )}

          {autoFill && (
            <div className="flex items-start gap-2 px-3.5 py-2.5 bg-info-bg border border-info-border rounded-lg text-[13px] text-info leading-relaxed">
              <Info size={14} className="flex-shrink-0 mt-0.5" />
              <span>
                <strong>{autoFill.distanceKm} km</strong>
                {autoFill.despachoAmount !== null && (
                  <> · Despacho <strong>{money(autoFill.despachoAmount)}</strong>
                    {autoFill.despachoLabel ? ` (${autoFill.despachoLabel})` : ""}</>
                )}
                {autoFill.fuelLiters !== null && (
                  <> · Combustível estimado <strong>{autoFill.fuelLiters} L</strong></>
                )}
                {autoFill.despachoAmount === null && (
                  <> · <span className="text-warning font-bold">Distância fora das faixas de despacho</span></>
                )}
              </span>
            </div>
          )}

          <div className={row}>
            <label className={lbl}>
              Viatura
              <select
                name="vehicle_id"
                required
                value={selectedVehicleId}
                onChange={(e) => handleVehicleChange(e.target.value)}
                className={inp}
              >
                <option value="">Seleccionar...</option>
                {activeVehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate} — {v.brand} {v.model}
                    {v.avg_consumption_target ? ` (${v.avg_consumption_target} L/100km)` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className={lbl}>
              Motorista
              <select name="driver_id" required className={inp}>
                <option value="">Seleccionar...</option>
                {activeDrivers.map((d) => (
                  <option key={d.id} value={d.id}>{d.full_name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Origem
              <input
                name="origin"
                required
                placeholder="Maputo"
                value={manualOrigin}
                onChange={(e) => { setManualOrigin(e.target.value); setAutoFill(null); }}
                className={inp}
              />
            </label>
            <label className={lbl}>
              Destino
              <input
                name="destination"
                required
                placeholder="Beira"
                value={manualDest}
                onChange={(e) => { setManualDest(e.target.value); setAutoFill(null); }}
                className={inp}
              />
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Distância (km)
              <input
                name="distance_km"
                type="number"
                min={0}
                step="0.1"
                placeholder="530"
                value={manualDist}
                onChange={(e) => { setManualDist(e.target.value); setAutoFill(null); }}
                className={inp}
              />
            </label>
            <label className={lbl}>
              Tipo de carga
              <input name="cargo_type" placeholder="Cimento ensacado" className={inp} />
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Estado carga
              <select name="load_state" className={inp}>
                <option value="">Não definido</option>
                <option value="loaded_empty">Carregado / Vazio</option>
                <option value="loaded_loaded">Carregado / Carregado</option>
                <option value="empty_loaded">Vazio / Carregado</option>
                <option value="empty_empty">Vazio / Vazio</option>
              </select>
            </label>
            <label className={lbl}>
              Contrato (opcional)
              <select name="contract_id" className={inp}>
                <option value="">Sem contrato</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>{c.contract_reference} — {c.client_name}</option>
                ))}
              </select>
            </label>
          </div>

          {error && <p className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{error}</p>}
          <div className={actions}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" variant="primary" disabled={loading}>{loading ? "A criar..." : "Criar viagem"}</Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
