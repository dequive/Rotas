"use client";

import { Edit2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Driver } from "../lib/drivers-api";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-amber focus:ring-1 focus:ring-amber/20";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

export function DriverFormModal({ driver }: { driver?: Driver }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!driver;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      full_name: fd.get("full_name"),
      phone: fd.get("phone"),
      email: fd.get("email") || undefined,
      license_number: fd.get("license_number"),
      license_category: fd.get("license_category"),
      license_valid_until: fd.get("license_valid_until"),
      passport_number: fd.get("passport_number") || undefined,
      passport_valid_until: fd.get("passport_valid_until") || undefined,
      bi_number: fd.get("bi_number") || undefined,
      bi_valid_until: fd.get("bi_valid_until") || undefined,
      employment_type: fd.get("employment_type"),
    };
    if (isEdit) payload.id = driver.id;

    try {
      const res = await fetch("/api/drivers", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao guardar motorista."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {isEdit ? (
        <IconButton onClick={() => setOpen(true)} label="Editar motorista"><Edit2 size={15} /></IconButton>
      ) : (
        <Button onClick={() => setOpen(true)}><Plus size={16} /> Novo motorista</Button>
      )}

      <ModalDialog open={open} onClose={() => setOpen(false)} title={isEdit ? "Editar motorista" : "Novo motorista"}>
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          <div className={row}>
            <label className={lbl}>Nome completo<input name="full_name" defaultValue={driver?.full_name} required className={inp} /></label>
            <label className={lbl}>Telefone<input name="phone" defaultValue={driver?.phone} required placeholder="258840000001" className={inp} /></label>
          </div>
          <label className={lbl}>Email<input name="email" type="email" defaultValue={driver?.email ?? ""} placeholder="motorista@empresa.mz" className={inp} /></label>
          <div className={row}>
            <label className={lbl}>Nº Carta<input name="license_number" defaultValue={driver?.license_number} required className={inp} /></label>
            <label className={lbl}>Categoria
              <select name="license_category" defaultValue={driver?.license_category ?? "C"} className={inp}>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="CE">CE</option>
                <option value="D">D</option>
              </select>
            </label>
          </div>
          <label className={lbl}>Validade carta<input name="license_valid_until" type="date" defaultValue={driver?.license_valid_until?.slice(0, 10)} required className={inp} /></label>
          <div className={row}>
            <label className={lbl}>Nº Passaporte<input name="passport_number" defaultValue={driver?.passport_number ?? ""} placeholder="Ex: P123456789" className={inp} /></label>
            <label className={lbl}>Validade Passaporte<input name="passport_valid_until" type="date" defaultValue={driver?.passport_valid_until?.slice(0, 10) ?? ""} className={inp} /></label>
          </div>
          <div className={row}>
            <label className={lbl}>Nº B.I.<input name="bi_number" defaultValue={driver?.bi_number ?? ""} placeholder="Ex: 123456789B001MZ" className={inp} /></label>
            <label className={lbl}>Validade B.I.<input name="bi_valid_until" type="date" defaultValue={driver?.bi_valid_until?.slice(0, 10) ?? ""} className={inp} /></label>
          </div>
          <label className={lbl}>Vínculo
            <select name="employment_type" defaultValue={driver?.employment_type ?? "efectivo"} className={inp}>
              <option value="efectivo">Efectivo</option>
              <option value="contratado">Contratado</option>
              <option value="subcontratado">Subcontratado</option>
            </select>
          </label>
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
