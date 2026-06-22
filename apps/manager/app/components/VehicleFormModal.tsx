"use client";

import { Edit2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Vehicle } from "../lib/vehicles-api";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

export function VehicleFormModal({ vehicle }: { vehicle?: Vehicle }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!vehicle;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      plate: fd.get("plate"),
      chassis: fd.get("chassis"),
      brand: fd.get("brand"),
      model: fd.get("model"),
      year: Number(fd.get("year")),
      category: fd.get("category"),
      fuel_type: fd.get("fuel_type"),
      color: fd.get("color") || undefined,
      current_km: Number(fd.get("current_km")),
      avg_consumption_target: fd.get("avg_consumption_target") ? Number(fd.get("avg_consumption_target")) : undefined,
      fuel_limit_daily: fd.get("fuel_limit_daily") ? Number(fd.get("fuel_limit_daily")) : undefined,
    };
    if (isEdit) payload.id = vehicle.id;

    try {
      const res = await fetch("/api/vehicles", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao guardar viatura."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {isEdit ? (
        <IconButton onClick={() => setOpen(true)} label="Editar viatura"><Edit2 size={15} /></IconButton>
      ) : (
        <Button onClick={() => setOpen(true)}><Plus size={16} /> Nova viatura</Button>
      )}

      <ModalDialog open={open} onClose={() => setOpen(false)} title={isEdit ? "Editar viatura" : "Nova viatura"}>
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          <div className={row}>
            <label className={lbl}>Matrícula<input name="plate" defaultValue={vehicle?.plate} required placeholder="MPT-00-RT" className={inp} /></label>
            <label className={lbl}>Chassis<input name="chassis" defaultValue={""} placeholder="VIN/Chassis" className={inp} /></label>
          </div>
          <div className={row}>
            <label className={lbl}>Marca<input name="brand" defaultValue={vehicle?.brand} required placeholder="Mercedes-Benz" className={inp} /></label>
            <label className={lbl}>Modelo<input name="model" defaultValue={vehicle?.model} required placeholder="Actros" className={inp} /></label>
          </div>
          <div className={row}>
            <label className={lbl}>Ano<input name="year" type="number" defaultValue={vehicle?.year ?? new Date().getFullYear()} required min={1990} max={2030} className={inp} /></label>
            <label className={lbl}>Cor<input name="color" defaultValue={vehicle?.color ?? ""} placeholder="Branco" className={inp} /></label>
          </div>
          <div className={row}>
            <label className={lbl}>Categoria
              <select name="category" defaultValue={vehicle?.category ?? "pesado"} className={inp}>
                <option value="ligeiro">Ligeiro</option>
                <option value="pesado">Pesado</option>
                <option value="semi_reboque">Semi-Reboque</option>
                <option value="cisterna">Cisterna</option>
              </select>
            </label>
            <label className={lbl}>Combustível
              <select name="fuel_type" defaultValue={vehicle?.fuel_type ?? "gasoleo"} className={inp}>
                <option value="gasoleo">Gasóleo</option>
                <option value="gasolina">Gasolina</option>
                <option value="gnc">GNC</option>
              </select>
            </label>
          </div>
          <div className={row}>
            <label className={lbl}>Km actual<input name="current_km" type="number" defaultValue={vehicle?.current_km ?? 0} required min={0} className={inp} /></label>
            <label className={lbl}>Consumo alvo (L/100km)<input name="avg_consumption_target" type="number" step="0.1" defaultValue={vehicle?.avg_consumption_target ?? ""} placeholder="32.5" className={inp} /></label>
          </div>
          <label className={lbl}>Limite diário combustível (MZN)<input name="fuel_limit_daily" type="number" step="0.01" defaultValue={vehicle?.fuel_limit_daily ?? ""} placeholder="350" className={inp} /></label>
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
