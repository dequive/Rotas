"use client";

import { Edit2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Vehicle } from "../lib/vehicles-api";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

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
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-row">
            <label>Matrícula<input name="plate" defaultValue={vehicle?.plate} required placeholder="MPT-00-RT" /></label>
            <label>Chassis<input name="chassis" defaultValue={""} placeholder="VIN/Chassis" /></label>
          </div>
          <div className="form-row">
            <label>Marca<input name="brand" defaultValue={vehicle?.brand} required placeholder="Mercedes-Benz" /></label>
            <label>Modelo<input name="model" defaultValue={vehicle?.model} required placeholder="Actros" /></label>
          </div>
          <div className="form-row">
            <label>Ano<input name="year" type="number" defaultValue={vehicle?.year ?? new Date().getFullYear()} required min={1990} max={2030} /></label>
            <label>Cor<input name="color" defaultValue={vehicle?.color ?? ""} placeholder="Branco" /></label>
          </div>
          <div className="form-row">
            <label>Categoria
              <select name="category" defaultValue={vehicle?.category ?? "pesado"}>
                <option value="ligeiro">Ligeiro</option>
                <option value="pesado">Pesado</option>
                <option value="semi_reboque">Semi-Reboque</option>
                <option value="cisterna">Cisterna</option>
              </select>
            </label>
            <label>Combustível
              <select name="fuel_type" defaultValue={vehicle?.fuel_type ?? "gasoleo"}>
                <option value="gasoleo">Gasóleo</option>
                <option value="gasolina">Gasolina</option>
                <option value="gnc">GNC</option>
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>Km actual<input name="current_km" type="number" defaultValue={vehicle?.current_km ?? 0} required min={0} /></label>
            <label>Consumo alvo (L/100km)<input name="avg_consumption_target" type="number" step="0.1" defaultValue={vehicle?.avg_consumption_target ?? ""} placeholder="32.5" /></label>
          </div>
          <label>Limite diário combustível (MZN)<input name="fuel_limit_daily" type="number" step="0.01" defaultValue={vehicle?.fuel_limit_daily ?? ""} placeholder="350" /></label>
          {error && <p className="text-error text-[13px] m-0 bg-error-bg border border-error-border rounded-md px-3 py-2">{error}</p>}
          <div className="modal-actions">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" variant="primary" disabled={loading}>{loading ? "A guardar..." : "Guardar"}</Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
