"use client";

import { useState, useEffect } from "react";
import { Plus } from "lucide-react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";
import { ThirdPartyCombobox } from "@/app/components/ThirdPartyCombobox";

interface VehicleOption {
  id: string;
  plate: string;
}

interface WorkOrderFormData {
  vehicle_id: string;
  planned_work: string;
  diagnosis: string;
  estimated_cost: number | null;
  priority: "normal" | "high" | "critical";
  service_provider_third_party_id: string | null;
  service_provider_name: string;
  notes: string;
}

interface WorkOrderFormModalProps {
  vehicleOptions?: VehicleOption[];
  onSuccess?: () => void;
}

const inputCls =
  "w-full min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-amber focus:ring-2 focus:ring-amber/20";
const labelCls = "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

export function WorkOrderFormModal({ vehicleOptions: vehicleOptionsProp, onSuccess }: WorkOrderFormModalProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Partial<WorkOrderFormData>>({
    service_provider_third_party_id: null,
    service_provider_name: "",
    priority: "normal",
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
    setForm({
      service_provider_third_party_id: null,
      service_provider_name: "",
      priority: "normal",
    });
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
      const res = await fetch("/api/work-orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        setError(body.error?.message ?? body.detail ?? "Erro ao criar ordem de trabalho");
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
        Nova Ordem de Trabalho
      </button>

      <ModalDialog
        open={open}
        onClose={handleClose}
        title="Nova Ordem de Trabalho"
        className="modal-wide"
      >
        <div className="px-6 pb-6 pt-4 overflow-y-auto max-h-[70vh]">
          {error && (
            <div className="mb-4 px-3 py-2 bg-error-bg border border-error-border rounded-md text-[13px] text-error">
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

            {/* Planned work */}
            <div>
              <label className={labelCls}>Trabalho Planeado *</label>
              <input
                required
                type="text"
                placeholder="Ex: Substituição de filtro de óleo, pastilhas de travão..."
                value={form.planned_work ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, planned_work: e.target.value }))}
                className={inputCls}
              />
            </div>

            {/* Diagnosis */}
            <div>
              <label className={labelCls}>Diagnóstico / Sintoma</label>
              <textarea
                rows={2}
                placeholder="Descreva o problema observado..."
                value={form.diagnosis ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, diagnosis: e.target.value }))}
                className={`${inputCls} resize-y min-h-[60px]`}
              />
            </div>

            {/* Priority + Estimated cost */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelCls}>Prioridade</label>
                <select
                  value={form.priority ?? "normal"}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      priority: e.target.value as WorkOrderFormData["priority"],
                    }))
                  }
                  className={inputCls}
                >
                  <option value="normal">Normal</option>
                  <option value="high">Alta</option>
                  <option value="critical">Crítica</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Custo Estimado (MZN)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.estimated_cost ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      estimated_cost: e.target.value ? parseFloat(e.target.value) : null,
                    }))
                  }
                  className={`${inputCls} font-mono`}
                />
              </div>
            </div>

            {/* Service Provider */}
            <div className="flex flex-col gap-1.5">
              <ThirdPartyCombobox
                roleType="service_provider"
                value={form.service_provider_third_party_id ?? null}
                displayValue={form.service_provider_name ?? null}
                label="Prestador de Serviço (opcional)"
                placeholder="Seleccionar prestador registado..."
                onChange={(sel) => {
                  if (sel) {
                    setForm((f) => ({
                      ...f,
                      service_provider_third_party_id: sel.id,
                      service_provider_name: sel.name,
                    }));
                  } else {
                    setForm((f) => ({
                      ...f,
                      service_provider_third_party_id: null,
                      service_provider_name: "",
                    }));
                  }
                }}
              />
              {form.service_provider_third_party_id && (
                <p className="text-[11px] font-mono text-muted m-0">
                  ID: {form.service_provider_third_party_id}
                </p>
              )}
            </div>

            {/* Notes */}
            <div>
              <label className={labelCls}>Notas Adicionais</label>
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
                {submitting ? "A criar..." : "Criar Ordem"}
              </button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </>
  );
}
