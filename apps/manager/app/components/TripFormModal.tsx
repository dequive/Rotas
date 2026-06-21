"use client";

import { Info, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/app/components/ui/Button";
import type { KnownRoute } from "../lib/known-routes-api";
import { calcDespacho, calcFuel } from "../lib/known-routes-api";
import type { Vehicle } from "../lib/vehicles-api";
import type { Driver } from "../lib/drivers-api";
import type { Contract } from "../lib/contracts-api";
import type { DriverDespachoTier } from "../lib/operations-admin-api";

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

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Nova viagem</h2>
              <button className="icon-btn" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>

            <form onSubmit={handleSubmit} className="modal-form">
              {/* Destino conhecido */}
              {knownRoutes.length > 0 && (
                <label>
                  Destino do catálogo
                  <select onChange={(e) => handleRouteSelect(e.target.value)} defaultValue="">
                    <option value="">— Seleccionar destino (preenche automaticamente) —</option>
                    {knownRoutes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.origin} → {r.destination} ({r.distance_km} km)
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {/* Auto-fill preview */}
              {autoFill && (
                <div className="autofill-summary">
                  <Info size={14} />
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
                      <> · <span className="warn-text">Distância fora das faixas de despacho</span></>
                    )}
                  </span>
                </div>
              )}

              {/* Viatura + motorista */}
              <div className="form-row">
                <label>
                  Viatura
                  <select
                    name="vehicle_id"
                    required
                    value={selectedVehicleId}
                    onChange={(e) => handleVehicleChange(e.target.value)}
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
                <label>
                  Motorista
                  <select name="driver_id" required>
                    <option value="">Seleccionar...</option>
                    {activeDrivers.map((d) => (
                      <option key={d.id} value={d.id}>{d.full_name}</option>
                    ))}
                  </select>
                </label>
              </div>

              {/* Origem / Destino / Distância */}
              <div className="form-row">
                <label>
                  Origem
                  <input
                    name="origin"
                    required
                    placeholder="Maputo"
                    value={manualOrigin}
                    onChange={(e) => { setManualOrigin(e.target.value); setAutoFill(null); }}
                  />
                </label>
                <label>
                  Destino
                  <input
                    name="destination"
                    required
                    placeholder="Beira"
                    value={manualDest}
                    onChange={(e) => { setManualDest(e.target.value); setAutoFill(null); }}
                  />
                </label>
              </div>

              <div className="form-row">
                <label>
                  Distância (km)
                  <input
                    name="distance_km"
                    type="number"
                    min={0}
                    step="0.1"
                    placeholder="530"
                    value={manualDist}
                    onChange={(e) => { setManualDist(e.target.value); setAutoFill(null); }}
                  />
                </label>
                <label>
                  Tipo de carga
                  <input name="cargo_type" placeholder="Cimento ensacado" />
                </label>
              </div>

              <div className="form-row">
                <label>
                  Estado carga
                  <select name="load_state">
                    <option value="">Não definido</option>
                    <option value="loaded_empty">Carregado / Vazio</option>
                    <option value="loaded_loaded">Carregado / Carregado</option>
                    <option value="empty_loaded">Vazio / Carregado</option>
                    <option value="empty_empty">Vazio / Vazio</option>
                  </select>
                </label>
                <label>
                  Contrato (opcional)
                  <select name="contract_id">
                    <option value="">Sem contrato</option>
                    {contracts.map((c) => (
                      <option key={c.id} value={c.id}>{c.contract_reference} — {c.client_name}</option>
                    ))}
                  </select>
                </label>
              </div>

              {error && <p className="form-error">{error}</p>}
              <div className="modal-actions">
                <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
                <Button type="submit" variant="primary" disabled={loading}>{loading ? "A criar..." : "Criar viagem"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
