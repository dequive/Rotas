"use client";

import { Edit2, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Contract } from "../lib/contracts-api";

export function ContractFormModal({ contract }: { contract?: Contract }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!contract;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      client_name: fd.get("client_name"),
      contract_reference: fd.get("contract_reference"),
      title: fd.get("title"),
      service_type: fd.get("service_type"),
      billing_cycle: fd.get("billing_cycle"),
      billing_basis: fd.get("billing_basis"),
      currency: fd.get("currency"),
      default_unit_price: fd.get("default_unit_price") ? Number(fd.get("default_unit_price")) : undefined,
      requires_load_permit: fd.get("requires_load_permit") === "on",
      requires_delivery_proof: fd.get("requires_delivery_proof") === "on",
      starts_at: fd.get("starts_at") || undefined,
      ends_at: fd.get("ends_at") || undefined,
      notes: fd.get("notes") || undefined,
    };
    if (isEdit) payload.id = contract.id;

    try {
      const res = await fetch("/api/contracts", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json()) as { detail?: string };
      if (!res.ok) { setError(body.detail ?? "Erro ao guardar contrato."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className={isEdit ? "icon-btn" : "primary-btn"} onClick={() => setOpen(true)}>
        {isEdit ? <Edit2 size={15} /> : <><Plus size={16} /> Novo contrato</>}
      </button>

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{isEdit ? "Editar contrato" : "Novo contrato"}</h2>
              <button className="icon-btn" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              <div className="form-row">
                <label>Referência<input name="contract_reference" defaultValue={contract?.contract_reference} required placeholder="CTR-2026-001" /></label>
                <label>Cliente<input name="client_name" defaultValue={contract?.client_name} required /></label>
              </div>
              <label>Título<input name="title" defaultValue={contract?.title} required /></label>
              <div className="form-row">
                <label>Tipo de serviço
                  <select name="service_type" defaultValue={contract?.service_type ?? "cargo_transport"}>
                    <option value="cargo_transport">Transporte de carga</option>
                    <option value="passenger_transport">Transporte de passageiros</option>
                  </select>
                </label>
                <label>Ciclo de cobrança
                  <select name="billing_cycle" defaultValue={contract?.billing_cycle ?? "monthly"}>
                    <option value="monthly">Mensal</option>
                    <option value="weekly">Semanal</option>
                    <option value="per_trip">Por viagem</option>
                  </select>
                </label>
              </div>
              <div className="form-row">
                <label>Base de cobrança
                  <select name="billing_basis" defaultValue={contract?.billing_basis ?? "trip"}>
                    <option value="trip">Por viagem</option>
                    <option value="km">Por km</option>
                    <option value="weight">Por peso</option>
                  </select>
                </label>
                <label>Moeda
                  <select name="currency" defaultValue={contract?.currency ?? "MZN"}>
                    <option value="MZN">MZN</option>
                    <option value="USD">USD</option>
                    <option value="ZAR">ZAR</option>
                  </select>
                </label>
              </div>
              <label>Preço unitário padrão<input name="default_unit_price" type="number" step="0.01" defaultValue={contract?.default_unit_price ?? ""} placeholder="12500" /></label>
              <div className="form-row">
                <label>Início<input name="starts_at" type="date" defaultValue={contract?.starts_at?.slice(0, 10) ?? ""} /></label>
                <label>Fim<input name="ends_at" type="date" defaultValue={contract?.ends_at?.slice(0, 10) ?? ""} /></label>
              </div>
              <div className="form-row checkboxes">
                <label className="checkbox-label">
                  <input name="requires_load_permit" type="checkbox" defaultChecked={contract?.requires_load_permit ?? true} />
                  Requer Load Permit
                </label>
                <label className="checkbox-label">
                  <input name="requires_delivery_proof" type="checkbox" defaultChecked={contract?.requires_delivery_proof ?? true} />
                  Requer Prova de entrega
                </label>
              </div>
              <label>Notas<textarea name="notes" rows={2} placeholder="Observações sobre o contrato..." /></label>
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
