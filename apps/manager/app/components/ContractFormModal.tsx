"use client";

import { Edit2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Contract } from "../lib/contracts-api";
import { ClientCombobox } from "./ClientCombobox";
import { Button } from "@/app/components/ui/Button";
import { IconButton } from "@/app/components/ui/IconButton";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

const lbl = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inp = "min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";
const row = "grid grid-cols-2 gap-3";
const actions = "flex justify-end gap-2.5 mt-1.5 pt-4 border-t border-border";

export function ContractFormModal({ contract }: { contract?: Contract }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientId, setClientId] = useState<string>(contract?.client_id ?? "");
  const [clientName, setClientName] = useState<string>(contract?.client_name ?? "");
  const [clientError, setClientError] = useState<string | null>(null);

  const isEdit = !!contract;

  function handleClientChange(id: string, name: string) {
    setClientId(id);
    setClientName(name);
    setClientError(null);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setClientError(null);

    if (!clientId && !clientName) {
      setClientError("Seleccione um cliente.");
      return;
    }

    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = {
      client_id: clientId || undefined,
      client_name: clientId ? clientName : (clientName || undefined),
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
      const body = (await res.json()) as { detail?: string; error?: { message?: string; code?: string } };
      if (!res.ok) { setError(body.error?.message ?? body.error?.code ?? body.detail ?? "Erro ao guardar contrato."); return; }
      setOpen(false);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  function handleOpen() {
    setClientId(contract?.client_id ?? "");
    setClientName(contract?.client_name ?? "");
    setClientError(null);
    setError(null);
    setOpen(true);
  }

  return (
    <>
      {isEdit ? (
        <IconButton onClick={handleOpen} label="Editar contrato"><Edit2 size={15} /></IconButton>
      ) : (
        <Button onClick={handleOpen}><Plus size={16} /> Novo contrato</Button>
      )}

      <ModalDialog open={open} onClose={() => setOpen(false)} title={isEdit ? "Editar contrato" : "Novo contrato"} className="modal-wide">
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-3.5">
          <div className={row}>
            <label className={lbl}>Referência<input name="contract_reference" defaultValue={contract?.contract_reference} required placeholder="CTR-2026-001" className={inp} /></label>
          </div>

          <div>
            <label className="flex flex-col gap-1.5 text-[13px] font-bold text-muted">
              Cliente <span aria-hidden="true" className="text-error">*</span>
            </label>
            <ClientCombobox
              value={clientId || undefined}
              onChange={handleClientChange}
              disabled={loading}
            />
            {clientError && (
              <p className="text-xs text-error mt-1 mb-0">{clientError}</p>
            )}
          </div>

          <label className={lbl}>Título<input name="title" defaultValue={contract?.title} required className={inp} /></label>
          <div className={row}>
            <label className={lbl}>Tipo de serviço
              <select name="service_type" defaultValue={contract?.service_type ?? "cargo_transport"} className={inp}>
                <option value="cargo_transport">Transporte de carga</option>
                <option value="passenger_transport">Transporte de passageiros</option>
              </select>
            </label>
            <label className={lbl}>Ciclo de cobrança
              <select name="billing_cycle" defaultValue={contract?.billing_cycle ?? "monthly"} className={inp}>
                <option value="monthly">Mensal</option>
                <option value="weekly">Semanal</option>
                <option value="per_trip">Por viagem</option>
              </select>
            </label>
          </div>
          <div className={row}>
            <label className={lbl}>Base de cobrança
              <select name="billing_basis" defaultValue={contract?.billing_basis ?? "trip"} className={inp}>
                <option value="trip">Por viagem</option>
                <option value="km">Por km</option>
                <option value="weight">Por peso</option>
              </select>
            </label>
            <label className={lbl}>Moeda
              <select name="currency" defaultValue={contract?.currency ?? "MZN"} className={inp}>
                <option value="MZN">MZN</option>
                <option value="USD">USD</option>
                <option value="ZAR">ZAR</option>
              </select>
            </label>
          </div>
          <label className={lbl}>Preço unitário padrão<input name="default_unit_price" type="number" step="0.01" defaultValue={contract?.default_unit_price ?? ""} placeholder="12500" className={inp} /></label>
          <div className={row}>
            <label className={lbl}>Início<input name="starts_at" type="date" defaultValue={contract?.starts_at?.slice(0, 10) ?? ""} className={inp} /></label>
            <label className={lbl}>Fim<input name="ends_at" type="date" defaultValue={contract?.ends_at?.slice(0, 10) ?? ""} className={inp} /></label>
          </div>
          <div className="grid grid-cols-2 gap-3 items-center">
            <label className="flex flex-row items-center gap-2 text-sm font-semibold text-ink cursor-pointer">
              <input name="requires_load_permit" type="checkbox" defaultChecked={contract?.requires_load_permit ?? true} className="w-4 h-4 accent-amber" />
              Requer Load Permit
            </label>
            <label className="flex flex-row items-center gap-2 text-sm font-semibold text-ink cursor-pointer">
              <input name="requires_delivery_proof" type="checkbox" defaultChecked={contract?.requires_delivery_proof ?? true} className="w-4 h-4 accent-amber" />
              Requer Prova de entrega
            </label>
          </div>
          <label className={lbl}>Notas<textarea name="notes" rows={2} placeholder="Observações sobre o contrato..." className="px-2.5 py-2 border border-border-strong rounded-md bg-surface text-[14px] text-ink w-full focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft resize-y" /></label>
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
