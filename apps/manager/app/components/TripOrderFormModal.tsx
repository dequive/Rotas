"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "./ui/Button";
import { ModalDialog } from "./ui/ModalDialog";
import type { Contract } from "../lib/contracts-api";
import { createTripOrder } from "../lib/trip-orders-client";
import {
  type TripOrderCreatePayload,
} from "../lib/trip-orders-api";

const labelClass = "flex flex-col gap-1.5 text-[13px] font-bold text-muted";
const inputClass = "min-h-[38px] w-full rounded-md border border-border-strong bg-surface px-2.5 text-[14px] text-ink focus:border-focus focus:outline-none focus:ring-2 focus:ring-focus-soft";

export function TripOrderFormModal({ contracts }: { contracts: Contract[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contractId, setContractId] = useState("");
  const [requiresLoadPermit, setRequiresLoadPermit] = useState(false);

  const activeContracts = contracts.filter((contract) => contract.status === "active");

  function selectContract(id: string) {
    setContractId(id);
    const contract = activeContracts.find((item) => item.id === id);
    setRequiresLoadPermit(contract?.requires_load_permit ?? false);
  }

  function openForm() {
    setContractId("");
    setRequiresLoadPermit(false);
    setError(null);
    setOpen(true);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const contract = activeContracts.find((item) => item.id === contractId);
    if (!contract) {
      setError("Seleccione um contrato activo.");
      return;
    }

    const form = new FormData(event.currentTarget);
    const estimatedWeight = String(form.get("estimated_weight") ?? "").trim();
    const estimatedWeightValue = estimatedWeight ? Number(estimatedWeight) : null;
    if (
      estimatedWeightValue !== null &&
      (!Number.isFinite(estimatedWeightValue) || estimatedWeightValue < 0)
    ) {
      setError("Informe um peso estimado válido.");
      return;
    }
    const payload: TripOrderCreatePayload = {
      cargo_risk_level: "normal",
      cargo_type: String(form.get("cargo_type") ?? "").trim() || null,
      client_id: contract.client_id,
      contract_id: contract.id,
      customer_reference:
        String(form.get("customer_reference") ?? "").trim() || null,
      destination: String(form.get("destination") ?? "").trim(),
      estimated_weight: estimatedWeightValue,
      origin: String(form.get("origin") ?? "").trim(),
      priority: String(form.get("priority") ?? "normal"),
      requested_delivery_date:
        String(form.get("requested_delivery_date") ?? "") || null,
      requested_pickup_date: String(form.get("requested_pickup_date") ?? ""),
      requires_customs_clearance:
        form.get("requires_customs_clearance") === "on",
      requires_load_permit: requiresLoadPermit,
      requires_police_clearance:
        form.get("requires_police_clearance") === "on",
      source: "manual",
    };

    setLoading(true);
    setError(null);
    try {
      await createTripOrder(payload);
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível criar a ordem de transporte.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Button type="button" onClick={openForm}>
        <Plus size={16} aria-hidden="true" /> Nova ordem
      </Button>

      <ModalDialog
        open={open}
        onClose={() => setOpen(false)}
        title="Nova ordem de transporte"
        className="modal-wide"
      >
        <form onSubmit={submit} className="flex flex-col gap-3.5 px-6 pb-6 pt-4">
          <label className={labelClass}>
            Contrato
            <select
              className={inputClass}
              value={contractId}
              onChange={(event) => selectContract(event.target.value)}
              required
            >
              <option value="">Seleccionar contrato...</option>
              {activeContracts.map((contract) => (
                <option key={contract.id} value={contract.id}>
                  {contract.contract_reference} — {contract.client_name}
                </option>
              ))}
            </select>
          </label>

          <label className={labelClass}>
            Referência do cliente
            <input name="customer_reference" className={inputClass} placeholder="PO-778" />
          </label>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className={labelClass}>
              Origem
              <input name="origin" className={inputClass} required maxLength={160} />
            </label>
            <label className={labelClass}>
              Destino
              <input name="destination" className={inputClass} required maxLength={160} />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className={labelClass}>
              Data de recolha
              <input name="requested_pickup_date" type="date" className={inputClass} required />
            </label>
            <label className={labelClass}>
              Data de entrega
              <input name="requested_delivery_date" type="date" className={inputClass} />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className={labelClass}>
              Tipo de carga
              <input name="cargo_type" className={inputClass} placeholder="Carga geral" />
            </label>
            <label className={labelClass}>
              Peso estimado (kg)
              <input name="estimated_weight" type="number" min="0" step="0.01" className={inputClass} />
            </label>
            <label className={labelClass}>
              Prioridade
              <select name="priority" className={inputClass} defaultValue="normal">
                <option value="low">Baixa</option>
                <option value="normal">Normal</option>
                <option value="high">Alta</option>
                <option value="urgent">Urgente</option>
              </select>
            </label>
          </div>

          <div className="grid grid-cols-1 gap-2 text-sm font-semibold text-ink md:grid-cols-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={requiresLoadPermit}
                onChange={(event) => setRequiresLoadPermit(event.target.checked)}
              />
              Requer load permit
            </label>
            <label className="flex items-center gap-2">
              <input name="requires_police_clearance" type="checkbox" />
              Autorização policial
            </label>
            <label className="flex items-center gap-2">
              <input name="requires_customs_clearance" type="checkbox" />
              Desembaraço aduaneiro
            </label>
          </div>

          {error && (
            <p role="alert" className="rounded-md border border-error-border bg-error-bg px-3 py-2 text-[13px] text-error">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2.5 border-t border-border pt-4">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" loading={loading}>
              Criar rascunho
            </Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
