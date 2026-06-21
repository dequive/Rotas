"use client";

import { useState, useEffect } from "react";
import { Plus } from "lucide-react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";
import { ThirdPartyCombobox } from "./ThirdPartyCombobox";

interface VehicleOption {
  id: string;
  plate: string;
}

interface FuelPurchaseFormData {
  vehicle_id: string;
  liters: number;
  unit_cost: number;
  supplier_name: string;
  supplier_third_party_id: string | null;
  station: string;
  odometer_km: number | null;
  notes: string;
}

interface FuelPurchaseModalProps {
  vehicleOptions?: VehicleOption[];
  onSuccess?: () => void;
}

const inputCls =
  "w-full min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20";
const labelCls = "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

export function FuelPurchaseModal({ vehicleOptions: vehicleOptionsProp, onSuccess }: FuelPurchaseModalProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Partial<FuelPurchaseFormData>>({
    supplier_third_party_id: null,
    supplier_name: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vehicleOptions, setVehicleOptions] = useState<VehicleOption[]>(vehicleOptionsProp ?? []);

  useEffect(() => {
    if (!open || vehicleOptionsProp) return;
    fetch("/api/vehicles?limit=200", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: unknown) => {
        const list = Array.isArray(data) ? data : [];
        setVehicleOptions(
          (list as Array<{ id: string; plate: string }>).map((v) => ({
            id: v.id,
            plate: v.plate,
          }))
        );
      })
      .catch(() => setVehicleOptions([]));
  }, [open, vehicleOptionsProp]);

  function resetForm() {
    setForm({ supplier_third_party_id: null, supplier_name: "" });
    setError(null);
  }

  function handleClose() {
    setOpen(false);
    resetForm();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/fuel-purchases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        setError(body.error?.message ?? body.detail ?? "Erro ao registar abastecimento");
        return;
      }
      handleClose();
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch {
      setError("Erro de rede — tente novamente");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 h-[38px] px-3.5 border-none rounded-md bg-amber text-white text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors duration-100"
      >
        <Plus size={15} />
        Registar Abastecimento
      </button>

      <ModalDialog
        open={open}
        onClose={handleClose}
        title="Registar Abastecimento Externo"
        className="modal-wide"
      >
        <div className="px-6 pb-6 pt-4 flex flex-col gap-4">
          {error && (
            <div className="px-3 py-2 bg-error-bg border border-error-border rounded-md text-[13px] text-error">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Vehicle */}
            <div>
              <label className={labelCls}>Viatura *</label>
              <select
                required
                value={form.vehicle_id ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, vehicle_id: e.target.value }))}
                className={inputCls}
              >
                <option value="">Seleccionar viatura</option>
                {vehicleOptions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate}
                  </option>
                ))}
              </select>
            </div>

            {/* Supplier combobox + free-text fallback */}
            <div className="flex flex-col gap-2">
              <ThirdPartyCombobox
                roleType="supplier"
                value={form.supplier_third_party_id ?? null}
                displayValue={form.supplier_name ?? null}
                label="Fornecedor (opcional)"
                placeholder="Seleccionar fornecedor registado..."
                onChange={(sel) => {
                  if (sel) {
                    setForm((f) => ({
                      ...f,
                      supplier_third_party_id: sel.id,
                      supplier_name: sel.name,
                    }));
                  } else {
                    setForm((f) => ({ ...f, supplier_third_party_id: null }));
                  }
                }}
              />
              {!form.supplier_third_party_id && (
                <input
                  type="text"
                  placeholder="Ou escrever nome do posto (texto livre)"
                  value={form.supplier_name ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, supplier_name: e.target.value }))}
                  className={inputCls}
                />
              )}
            </div>

            {/* Liters + Unit cost */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Litros *</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.liters ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, liters: parseFloat(e.target.value) }))}
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>Custo unitário (MZN) *</label>
                <input
                  required
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.unit_cost ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, unit_cost: parseFloat(e.target.value) }))}
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>

            {/* Station + Odometer */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Posto / Estação</label>
                <input
                  type="text"
                  value={form.station ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, station: e.target.value }))}
                  className={inputCls}
                />
              </div>
              <div>
                <label className={labelCls}>Odómetro (km)</label>
                <input
                  type="number"
                  min="0"
                  value={form.odometer_km ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      odometer_km: e.target.value ? parseInt(e.target.value) : null,
                    }))
                  }
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className={labelCls}>Observações</label>
              <textarea
                rows={2}
                value={form.notes ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                className={`${inputCls} resize-y min-h-[60px]`}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-border">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 border border-border rounded-md bg-transparent text-muted text-[13px] font-semibold cursor-pointer hover:bg-surface-2 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-md bg-amber text-white border-none text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors disabled:bg-muted disabled:cursor-not-allowed"
              >
                {submitting ? "A guardar..." : "Registar"}
              </button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </>
  );
}
