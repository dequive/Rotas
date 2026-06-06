"use client";

import { Edit2, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { KnownRoute } from "../lib/known-routes-api";

export function KnownRouteFormModal({ route }: { route?: KnownRoute }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!route;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      origin: fd.get("origin"),
      destination: fd.get("destination"),
      distance_km: Number(fd.get("distance_km")),
      avg_fuel_liters: fd.get("avg_fuel_liters") ? Number(fd.get("avg_fuel_liters")) : undefined,
      despacho_vazio: fd.get("despacho_vazio") ? Number(fd.get("despacho_vazio")) : undefined,
      despacho_carregado: fd.get("despacho_carregado") ? Number(fd.get("despacho_carregado")) : undefined,
      notes: fd.get("notes") || undefined,
    };
    if (isEdit) payload.id = route.id;
    try {
      const res = await fetch("/api/known-routes", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string };
      if (!res.ok) { setError(body.detail ?? "Erro ao guardar rota."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className={isEdit ? "icon-btn" : "primary-btn"} onClick={() => setOpen(true)}>
        {isEdit ? <Edit2 size={15} /> : <><Plus size={16} /> Novo destino</>}
      </button>
      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{isEdit ? "Editar destino" : "Novo destino"}</h2>
              <button className="icon-btn" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              <div className="form-row">
                <label>Origem<input name="origin" defaultValue={route?.origin} required placeholder="Maputo" /></label>
                <label>Destino<input name="destination" defaultValue={route?.destination} required placeholder="Beira" /></label>
              </div>
              <div className="form-row">
                <label>
                  Distância (km)
                  <input name="distance_km" type="number" step="0.1" min="1" defaultValue={route?.distance_km} required placeholder="530" />
                </label>
                <label>
                  Combustível estimado (L)
                  <input name="avg_fuel_liters" type="number" step="0.1" min="0" defaultValue={route?.avg_fuel_liters ?? ""} placeholder="Auto (consumo da viatura)" />
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>Deixe em branco para calcular pelo consumo da viatura</span>
                </label>
              </div>
              <div className="form-row">
                <label>
                  Despacho — Vazio (MZN)
                  <input name="despacho_vazio" type="number" step="1" min="0" defaultValue={route?.despacho_vazio ?? ""} placeholder="Auto (faixas do tenant)" />
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>Override para viatura vazia nesta rota</span>
                </label>
                <label>
                  Despacho — Carregado (MZN)
                  <input name="despacho_carregado" type="number" step="1" min="0" defaultValue={route?.despacho_carregado ?? ""} placeholder="Auto (faixas do tenant)" />
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>Override para viatura carregada nesta rota</span>
                </label>
              </div>
              <label>Notas<textarea name="notes" rows={2} defaultValue={route?.notes ?? ""} placeholder="Observações sobre a rota, portagens, etc." /></label>
              {error && <p className="form-error">{error}</p>}
              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setOpen(false)}>Cancelar</button>
                <button type="submit" className="primary-btn" disabled={loading}>{loading ? "A guardar..." : "Guardar"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
