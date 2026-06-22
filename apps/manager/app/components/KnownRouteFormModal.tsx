"use client";

import { Edit2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { KnownRoute } from "../lib/known-routes-api";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

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
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao guardar rota."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {isEdit ? (
        <IconButton onClick={() => setOpen(true)} label="Editar destino"><Edit2 size={15} /></IconButton>
      ) : (
        <Button onClick={() => setOpen(true)}><Plus size={16} /> Novo destino</Button>
      )}
      <ModalDialog open={open} onClose={() => setOpen(false)} title={isEdit ? "Editar destino" : "Novo destino"}>
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          <div className={row}>
            <label className={lbl}>Origem<input name="origin" defaultValue={route?.origin} required placeholder="Maputo" className={inp} /></label>
            <label className={lbl}>Destino<input name="destination" defaultValue={route?.destination} required placeholder="Beira" className={inp} /></label>
          </div>
          <div className={row}>
            <label className={lbl}>
              Distância (km)
              <input name="distance_km" type="number" step="0.1" min="1" defaultValue={route?.distance_km} required placeholder="530" className={inp} />
            </label>
            <label className={lbl}>
              Combustível estimado (L)
              <input name="avg_fuel_liters" type="number" step="0.1" min="0" defaultValue={route?.avg_fuel_liters ?? ""} placeholder="Auto (consumo da viatura)" className={inp} />
              <span className="text-[11px] text-muted">Deixe em branco para calcular pelo consumo da viatura</span>
            </label>
          </div>
          <div className={row}>
            <label className={lbl}>
              Despacho — Vazio (MZN)
              <input name="despacho_vazio" type="number" step="1" min="0" defaultValue={route?.despacho_vazio ?? ""} placeholder="Auto (faixas do tenant)" className={inp} />
              <span className="text-[11px] text-muted">Override para viatura vazia nesta rota</span>
            </label>
            <label className={lbl}>
              Despacho — Carregado (MZN)
              <input name="despacho_carregado" type="number" step="1" min="0" defaultValue={route?.despacho_carregado ?? ""} placeholder="Auto (faixas do tenant)" className={inp} />
              <span className="text-[11px] text-muted">Override para viatura carregada nesta rota</span>
            </label>
          </div>
          <label className={lbl}>Notas<textarea name="notes" rows={2} defaultValue={route?.notes ?? ""} placeholder="Observações sobre a rota, portagens, etc." className="px-2.5 py-2 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20 resize-y" /></label>
          {error && <p className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{error}</p>}
          <div className={actions}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" variant="primary" disabled={loading}>{loading ? "A guardar..." : "Guardar"}</Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
