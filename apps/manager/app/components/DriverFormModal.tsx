"use client";

import { Edit2, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Driver } from "../lib/drivers-api";
import { Button } from "@/app/components/ui/Button";

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
      <button className={isEdit ? "icon-btn" : "primary-btn"} onClick={() => setOpen(true)}>
        {isEdit ? <Edit2 size={15} /> : <><Plus size={16} /> Novo motorista</>}
      </button>

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{isEdit ? "Editar motorista" : "Novo motorista"}</h2>
              <button className="icon-btn" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              <div className="form-row">
                <label>Nome completo<input name="full_name" defaultValue={driver?.full_name} required /></label>
                <label>Telefone<input name="phone" defaultValue={driver?.phone} required placeholder="258840000001" /></label>
              </div>
              <label>Email<input name="email" type="email" defaultValue={driver?.email ?? ""} placeholder="motorista@empresa.mz" /></label>
              <div className="form-row">
                <label>Nº Carta<input name="license_number" defaultValue={driver?.license_number} required /></label>
                <label>Categoria
                  <select name="license_category" defaultValue={driver?.license_category ?? "C"}>
                    <option value="B">B</option>
                    <option value="C">C</option>
                    <option value="CE">CE</option>
                    <option value="D">D</option>
                  </select>
                </label>
              </div>
              <label>Validade carta<input name="license_valid_until" type="date" defaultValue={driver?.license_valid_until?.slice(0, 10)} required /></label>
              <div className="form-row">
                <label>Nº Passaporte<input name="passport_number" defaultValue={driver?.passport_number ?? ""} placeholder="Ex: P123456789" /></label>
                <label>Validade Passaporte<input name="passport_valid_until" type="date" defaultValue={driver?.passport_valid_until?.slice(0, 10) ?? ""} /></label>
              </div>
              <div className="form-row">
                <label>Nº B.I.<input name="bi_number" defaultValue={driver?.bi_number ?? ""} placeholder="Ex: 123456789B001MZ" /></label>
                <label>Validade B.I.<input name="bi_valid_until" type="date" defaultValue={driver?.bi_valid_until?.slice(0, 10) ?? ""} /></label>
              </div>
              <label>Vínculo
                <select name="employment_type" defaultValue={driver?.employment_type ?? "efectivo"}>
                  <option value="efectivo">Efectivo</option>
                  <option value="contratado">Contratado</option>
                  <option value="subcontratado">Subcontratado</option>
                </select>
              </label>
              {error && <p className="form-error">{error}</p>}
              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setOpen(false)}>Cancelar</button>
                <Button type="submit" variant="primary" disabled={loading}>{loading ? "A guardar..." : "Guardar"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
