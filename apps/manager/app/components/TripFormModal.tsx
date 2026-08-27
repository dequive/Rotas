"use client";

import { FileText, Info, Plus, ShieldCheck } from "lucide-react";
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
import { bffRequest } from "@/app/lib/bff";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

interface AutoFill {
  origin: string;
  destination: string;
  distanceKm: string;
  despachoAmount: number | null;
  despachoLabel: string | null;
  fuelLiters: number | null;
  baseFuelLiters: number | null;
  baseDespachoAmount: number | null;
}
function computeAutoFill(
  route: KnownRoute,
  vehicle: Vehicle | undefined,
  tiers: DriverDespachoTier[],
  loadState: string
): AutoFill {
  const baseDespacho = calcDespacho(route.distance_km, tiers);
  const baseFuel = calcFuel(
    route.distance_km,
    vehicle?.avg_consumption_target ?? null,
    route.avg_fuel_liters
  );

  // Proportional multiplier based on load_state from pre-configured table logic
  // loaded_loaded implies 2 legs loaded (~1.8x fuel & despacho factor)
  // loaded_empty implies 1 leg loaded + 1 leg empty (~1.0x factor)
  const multiplier = loadState === "loaded_loaded" ? 1.8 : 1.0;

  const finalDespachoAmount = baseDespacho?.amount ? Math.round(baseDespacho.amount * multiplier) : null;
  const finalFuelLiters = baseFuel ? Math.round(baseFuel * multiplier) : null;

  return {
    origin: route.origin,
    destination: route.destination,
    distanceKm: String(route.distance_km),
    despachoAmount: finalDespachoAmount,
    despachoLabel: baseDespacho?.label ? `${baseDespacho.label} (${loadState === "loaded_loaded" ? "Ida e Volta Carregado" : "Ida Carregado"})` : null,
    fuelLiters: finalFuelLiters,
    baseFuelLiters: baseFuel,
    baseDespachoAmount: baseDespacho?.amount ?? null,
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
  const [selectedLoadState, setSelectedLoadState] = useState("loaded_empty");
  const [autoFill, setAutoFill] = useState<AutoFill | null>(null);
  const [manualOrigin, setManualOrigin] = useState("");
  const [manualDest, setManualDest] = useState("");
  const [manualDist, setManualDist] = useState("");
  const [selectedRouteId, setSelectedRouteId] = useState("");
  const [requiresLoadPermit, setRequiresLoadPermit] = useState(true);
  const [requiresManifest, setRequiresManifest] = useState(true);

  const selectedVehicle = vehicles.find((v) => v.id === selectedVehicleId);

  function handleRouteSelect(routeId: string, loadState = selectedLoadState) {
    setSelectedRouteId(routeId);
    if (!routeId) { setAutoFill(null); return; }
    const route = knownRoutes.find((r) => r.id === routeId);
    if (!route) return;
    const fill = computeAutoFill(route, selectedVehicle, despacheTiers, loadState);
    setAutoFill(fill);
    setManualOrigin(fill.origin);
    setManualDest(fill.destination);
    setManualDist(fill.distanceKm);
  }

  function handleVehicleChange(vehicleId: string) {
    setSelectedVehicleId(vehicleId);
    if (selectedRouteId) {
      handleRouteSelect(selectedRouteId, selectedLoadState);
    }
  }

  function handleLoadStateChange(loadState: string) {
    setSelectedLoadState(loadState);
    if (selectedRouteId) {
      handleRouteSelect(selectedRouteId, loadState);
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
      load_state: selectedLoadState,
      contract_id: fd.get("contract_id") || undefined,
      distance_km: fd.get("distance_km") ? Number(fd.get("distance_km")) : undefined,
      despacho_amount: autoFill?.despachoAmount ?? undefined,
      fuel_estimate_liters: autoFill?.fuelLiters ?? undefined,
      load_permit_number: fd.get("load_permit_number") || undefined,
      requires_load_permit: requiresLoadPermit,
      requires_cargo_manifest: requiresManifest,
      waybill_number: fd.get("waybill_number") || undefined,
      contract_reference: fd.get("contract_reference") || undefined,
    };

    try {
      const res = await bffRequest("/api/v1/trips", {
        path: "/api/trips",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao criar viagem."); return; }

      const keepOpen = (window as unknown as { _keepTripModalOpen?: boolean })._keepTripModalOpen;
      (window as unknown as { _keepTripModalOpen?: boolean })._keepTripModalOpen = false;

      if (keepOpen) {
        // Rapid Batch Mode — Keep modal open, reset fields for next trip entry
        setManualOrigin(autoFill?.origin ?? "");
        setManualDest(autoFill?.destination ?? "");
        setManualDist(autoFill?.distanceKm ?? "");
        setError(null);
      } else {
        setOpen(false);
        setAutoFill(null);
        setSelectedVehicleId("");
        setSelectedRouteId("");
        setManualOrigin(""); setManualDest(""); setManualDist("");
      }
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

      <ModalDialog open={open} onClose={() => setOpen(false)} title="Nova Viagem de Transporte" className="modal-wide">
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          {knownRoutes.length > 0 && (
            <label className={lbl}>
              Destino do Catálogo (Tabela de Tarifas &amp; Distâncias)
              <select onChange={(e) => handleRouteSelect(e.target.value)} value={selectedRouteId} className={inp}>
                <option value="">— Seleccionar destino da tabela —</option>
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
                  <> · Despacho Ponderado <strong>{money(autoFill.despachoAmount)}</strong>
                    {autoFill.despachoLabel ? ` (${autoFill.despachoLabel})` : ""}</>
                )}
                {autoFill.fuelLiters !== null && (
                  <> · Combustível Estimado <strong>{autoFill.fuelLiters} L</strong></>
                )}
              </span>
            </div>
          )}

          <div className={row}>
            <label className={lbl}>
              Viatura (Camião)
              <select
                name="vehicle_id"
                required
                value={selectedVehicleId}
                onChange={(e) => handleVehicleChange(e.target.value)}
                className={inp}
              >
                <option value="">Seleccionar viatura...</option>
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
                <option value="">Seleccionar motorista...</option>
                {activeDrivers.map((d) => (
                  <option key={d.id} value={d.id}>{d.full_name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Estado da Carga (Tabelado)
              <select
                name="load_state"
                value={selectedLoadState}
                onChange={(e) => handleLoadStateChange(e.target.value)}
                className={inp}
              >
                <option value="loaded_empty">Carregado / Vazio (Ida Carregado, Volta Vazio)</option>
                <option value="loaded_loaded">Carregado / Carregado (Ida e Volta Carregado)</option>
                <option value="empty_empty">Vazio / Vazio (Transferência de Frota)</option>
              </select>
            </label>
            <label className={lbl}>
              Contrato Comercial
              <select name="contract_id" className={inp}>
                <option value="">Sem contrato (Spot Rate)</option>
                {contracts.map((c) => (
                  <option key={c.id} value={c.id}>{c.contract_reference} — {c.client_name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Número do Load Permit (Emitido pelo Cliente)
              <input
                name="load_permit_number"
                placeholder="Ex: LP-2026-9874"
                className={inp}
              />
            </label>
            <label className={lbl}>
              Guia de Transporte Fiscal (Gerada Automaticamente)
              <input
                disabled
                value="GT-2026/AUTO (Gerada no Registo)"
                className={`${inp} bg-muted/40 text-muted-foreground italic cursor-not-allowed`}
              />
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Origem (Preenchida da Tabela)
              <input
                name="origin"
                required
                readOnly={Boolean(selectedRouteId)}
                placeholder="Maputo"
                value={manualOrigin}
                onChange={(e) => setManualOrigin(e.target.value)}
                className={`${inp} ${selectedRouteId ? "bg-muted/40 text-muted-foreground cursor-not-allowed" : ""}`}
              />
            </label>
            <label className={lbl}>
              Destino (Preenchido da Tabela)
              <input
                name="destination"
                required
                readOnly={Boolean(selectedRouteId)}
                placeholder="Beira"
                value={manualDest}
                onChange={(e) => setManualDest(e.target.value)}
                className={`${inp} ${selectedRouteId ? "bg-muted/40 text-muted-foreground cursor-not-allowed" : ""}`}
              />
            </label>
          </div>

          <div className={row}>
            <label className={lbl}>
              Distância Tabelada (km)
              <input
                name="distance_km"
                type="number"
                min={0}
                step="0.1"
                readOnly={Boolean(selectedRouteId)}
                placeholder="530"
                value={manualDist}
                onChange={(e) => setManualDist(e.target.value)}
                className={`${inp} ${selectedRouteId ? "bg-muted/40 text-muted-foreground cursor-not-allowed" : ""}`}
              />
            </label>
            <label className={lbl}>
              Descrição da Mercadoria
              <input name="cargo_type" placeholder="Ex: Cimento, Clinquer, Contentor 40ft" className={inp} />
            </label>
          </div>

          <div className="flex items-center gap-6 pt-2 border-t border-border/60 text-xs text-ink font-medium">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={requiresLoadPermit}
                onChange={(e) => setRequiresLoadPermit(e.target.checked)}
                className="rounded border-border text-rotas-500 focus:ring-focus"
              />
              <span>Exige Load Permit Válido do Cliente</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={requiresManifest}
                onChange={(e) => setRequiresManifest(e.target.checked)}
                className="rounded border-border text-rotas-500 focus:ring-focus"
              />
              <span>Gerar Manifesto de Carga Oficial</span>
            </label>
          </div>

          {error && <p className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{error}</p>}
          <div className={actions}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button
              type="submit"
              variant="secondary"
              disabled={loading}
              onClick={() => {
                (window as unknown as { _keepTripModalOpen?: boolean })._keepTripModalOpen = true;
              }}
            >
              {loading ? "A registar..." : "⚡ Registar e Agendar Outra (Modo Rápido)"}
            </Button>
            <Button type="submit" variant="primary" disabled={loading}>
              {loading ? "A criar..." : "Criar e Fechar"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
