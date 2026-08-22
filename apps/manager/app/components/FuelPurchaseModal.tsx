"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";

interface FuelPurchaseFormData {
  supplier_name: string;
  purchase_reference: string;
  fuel_type: string;
  ordered_liters: string;
  unit_price: string;
  ordered_at: string;
  notes: string;
}

interface FuelPurchaseModalProps {
  onSuccess?: () => void;
}

const emptyForm: FuelPurchaseFormData = {
  supplier_name: "",
  purchase_reference: "",
  fuel_type: "gasoleo",
  ordered_liters: "",
  unit_price: "",
  ordered_at: "",
  notes: "",
};

const inputCls =
  "w-full min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";
const labelCls = "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

export function FuelPurchaseModal({ onSuccess }: FuelPurchaseModalProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FuelPurchaseFormData>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof FuelPurchaseFormData>(key: K, value: FuelPurchaseFormData[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleClose() {
    setOpen(false);
    setForm(emptyForm);
    setError(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/fuel-purchases", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          supplier_name: form.supplier_name.trim(),
          purchase_reference: form.purchase_reference.trim(),
          fuel_type: form.fuel_type,
          ordered_liters: Number(form.ordered_liters),
          unit_price: Number(form.unit_price),
          ordered_at: new Date(form.ordered_at).toISOString(),
          notes: form.notes.trim() || null,
        }),
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        setError(body.error?.message ?? body.detail ?? "Erro ao registar a compra.");
        return;
      }

      handleClose();
      if (onSuccess) onSuccess();
      else window.location.reload();
    } catch {
      setError("Erro de rede — tente novamente.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 h-[38px] px-3.5 border-none rounded-md bg-amber text-white text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors duration-100"
      >
        <Plus size={15} /> Registar Compra
      </button>

      <ModalDialog open={open} onClose={handleClose} title="Registar compra de combustível" className="modal-wide">
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-4">
          {error && <div role="alert" className="px-3 py-2 bg-error-bg border border-error-border rounded-md text-[13px] text-error">{error}</div>}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label htmlFor="fuel-supplier" className={labelCls}>Fornecedor *</label>
              <input id="fuel-supplier" required value={form.supplier_name} onChange={(event) => update("supplier_name", event.target.value)} className={inputCls} />
            </div>
            <div>
              <label htmlFor="fuel-reference" className={labelCls}>Referência da compra *</label>
              <input id="fuel-reference" required value={form.purchase_reference} onChange={(event) => update("purchase_reference", event.target.value)} className={inputCls} />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label htmlFor="fuel-type" className={labelCls}>Tipo de combustível *</label>
              <select id="fuel-type" required value={form.fuel_type} onChange={(event) => update("fuel_type", event.target.value)} className={inputCls}>
                <option value="gasoleo">Gasóleo</option>
                <option value="gasolina">Gasolina</option>
              </select>
            </div>
            <div>
              <label htmlFor="fuel-liters" className={labelCls}>Litros encomendados *</label>
              <input id="fuel-liters" required type="number" min="0.01" step="0.01" value={form.ordered_liters} onChange={(event) => update("ordered_liters", event.target.value)} className={inputCls} />
            </div>
            <div>
              <label htmlFor="fuel-unit-price" className={labelCls}>Preço unitário (MZN) *</label>
              <input id="fuel-unit-price" required type="number" min="0.01" step="0.01" value={form.unit_price} onChange={(event) => update("unit_price", event.target.value)} className={inputCls} />
            </div>
          </div>

          <div>
            <label htmlFor="fuel-ordered-at" className={labelCls}>Data da encomenda *</label>
            <input id="fuel-ordered-at" required type="datetime-local" value={form.ordered_at} onChange={(event) => update("ordered_at", event.target.value)} className={inputCls} />
          </div>

          <div>
            <label htmlFor="fuel-notes" className={labelCls}>Observações</label>
            <textarea id="fuel-notes" rows={2} value={form.notes} onChange={(event) => update("notes", event.target.value)} className={`${inputCls} resize-y min-h-[60px]`} />
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border">
            <button type="button" onClick={handleClose} className="px-4 py-2 border border-border rounded-md bg-transparent text-muted text-[13px] font-semibold hover:bg-surface-2">Cancelar</button>
            <button type="submit" disabled={submitting} className="px-4 py-2 rounded-md bg-amber text-white border-none text-[13px] font-bold hover:bg-amber-dark disabled:bg-muted disabled:cursor-not-allowed">
              {submitting ? "A guardar..." : "Registar compra"}
            </button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
