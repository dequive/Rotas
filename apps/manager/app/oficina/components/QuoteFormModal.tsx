"use client";

import { useState, useEffect } from "react";
import { Calculator, FileText, LockKeyhole, Plus, Trash2 } from "lucide-react";
import { ModalDialog } from "@/app/components/ui/ModalDialog";
import { Button, type ButtonVariant } from "@/app/components/ui/Button";
import { bffRequest } from "@/app/lib/bff";

interface VehicleOption {
  id: string;
  plate: string;
  brand?: string;
  model?: string;
}

interface QuoteItemRow {
  id: string;
  item_type: "labor" | "part";
  description: string;
  quantity: number;
  unit_price: number;
  warranty_months: number;
  warranty_km: number;
}

interface QuoteFormModalProps {
  vehicleOptions?: VehicleOption[];
  initialVehicleId?: string;
  initialClientId?: string | null;
  initialReceptionId?: string | null;
  isSupplemental?: boolean;
  relatedWorkOrderId?: string | null;
  triggerLabel?: string;
  triggerVariant?: ButtonVariant;
  onSuccess?: () => void;
}

const inputCls =
  "w-full min-h-[38px] px-2.5 border border-border-strong rounded-md bg-surface text-ink text-[13px] focus:outline-none focus:border-focus focus:ring-2 focus:ring-focus-soft";
const labelCls = "block text-[11px] font-semibold uppercase tracking-wide text-muted mb-1";

export function QuoteFormModal({
  vehicleOptions: initialVehicles,
  initialVehicleId = "",
  initialClientId,
  initialReceptionId,
  isSupplemental = false,
  relatedWorkOrderId,
  triggerLabel,
  triggerVariant = "accent",
  onSuccess,
}: QuoteFormModalProps) {
  const [open, setOpen] = useState(false);
  const [vehicles, setVehicles] = useState<VehicleOption[]>(initialVehicles ?? []);
  const [selectedVehicleId, setSelectedVehicleId] = useState(initialVehicleId);
  const [validUntil, setValidUntil] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<QuoteItemRow[]>([
    {
      id: "1",
      item_type: "labor",
      description: "",
      quantity: 1,
      unit_price: 0,
      warranty_months: 0,
      warranty_km: 0,
    },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || initialVehicles) return;
    fetch("/api/vehicles?limit=200", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: unknown) => {
        const list = Array.isArray(data) ? data : [];
        setVehicles(
          (list as Array<{ id: string; plate: string; brand?: string; model?: string }>).map((v) => ({
            id: v.id,
            plate: v.plate,
            brand: v.brand,
            model: v.model,
          }))
        );
      })
      .catch(() => setVehicles([]));
  }, [open, initialVehicles]);

  function addItem() {
    setItems((prev) => [
      ...prev,
      {
        id: String(Date.now()),
        item_type: "part",
        description: "",
        quantity: 1,
        unit_price: 0,
        warranty_months: 0,
        warranty_km: 0,
      },
    ]);
  }

  function removeItem(id: string) {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  function updateItem(id: string, field: keyof QuoteItemRow, value: unknown) {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, [field]: value } : item))
    );
  }

  const subtotal = items.reduce((sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unit_price) || 0), 0);
  const tax = subtotal * 0.16; // IVA 16% Moçambique
  const total = subtotal + tax;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedVehicleId) {
      setError("Por favor, selecione uma viatura.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const payload = {
      vehicle_id: selectedVehicleId,
      client_id: initialClientId || undefined,
      reception_id: initialReceptionId || undefined,
      is_supplemental: isSupplemental,
      related_work_order_id: relatedWorkOrderId || undefined,
      valid_until: validUntil ? new Date(validUntil).toISOString() : undefined,
      notes: notes || undefined,
      tax_total: tax,
      items: items.map((i) => ({
        item_type: i.item_type,
        description: i.description || "Serviço sem descrição",
        quantity: Number(i.quantity) || 1,
        unit_price: Number(i.unit_price) || 0,
        warranty_months: Number(i.warranty_months) || 0,
        warranty_km: Number(i.warranty_km) || 0,
      })),
    };

    try {
      const res = await bffRequest("/api/v1/workshop/quotes", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string;
          error?: { message?: string };
        };
        setError(body.error?.message ?? body.detail ?? "Erro ao criar orçamento de oficina");
        return;
      }

      setOpen(false);
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch {
      setError("Erro de ligação ao servidor — tente novamente");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button variant={triggerVariant} onClick={() => setOpen(true)}>
        {isSupplemental ? <LockKeyhole size={16} /> : <Plus size={16} />}
        {triggerLabel ?? (isSupplemental ? "Criar suplemento" : "Criar orçamento")}
      </Button>

      <ModalDialog
        open={open}
        onClose={() => setOpen(false)}
        title={isSupplemental ? "Criar Orçamento Suplementar" : "Criar Novo Orçamento de Oficina"}
        className="modal-wide"
      >
        <form onSubmit={handleSubmit} className="px-6 pb-6 pt-4 flex flex-col gap-4">
          {error && (
            <div
              role="alert"
              className="rounded-md border border-status-cancelled bg-status-cancelled-soft p-3 text-xs font-medium text-status-cancelled"
            >
              {error}
            </div>
          )}

          {isSupplemental && (
            <div className="rounded-[var(--r-md)] border border-status-supplement bg-status-supplement-soft p-3 text-xs text-status-supplement">
              Este documento será um suplemento separado. O orçamento original
              permanece imutável e a execução adicional só pode começar após
              nova aprovação do cliente.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>Viatura *</label>
              <select
                required
                value={selectedVehicleId}
                onChange={(e) => setSelectedVehicleId(e.target.value)}
                className={inputCls}
              >
                <option value="">Selecione a viatura...</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.plate} {v.brand ? `— ${v.brand} ${v.model ?? ""}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelCls}>Válido Até</label>
              <input
                type="date"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          <div>
            <label className={labelCls}>Observações / Diagnóstico Inicial</label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex: Orçamento inicial para substituição de calços de travão e revisão periódica..."
              className={inputCls}
            />
          </div>

          {/* Items Table */}
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <FileText size={14} /> Itens do Orçamento (Serviços e Peças)
              </span>
              <Button type="button" variant="outline" onClick={addItem} className="h-7 text-xs px-2.5">
                <Plus size={13} /> Adicionar Linha
              </Button>
            </div>

            <div className="overflow-x-auto border border-border rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/50 font-semibold text-muted-foreground uppercase">
                  <tr>
                    <th className="p-2 w-28">Tipo</th>
                    <th className="p-2">Descrição</th>
                    <th className="p-2 w-20 text-right">Qtd</th>
                    <th className="p-2 w-28 text-right">P. Unit (MZN)</th>
                    <th className="p-2 w-32 text-right">Garantia</th>
                    <th className="p-2 w-28 text-right">Total (MZN)</th>
                    <th className="p-2 w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {items.map((item) => {
                    const rowTotal = (Number(item.quantity) || 0) * (Number(item.unit_price) || 0);
                    return (
                      <tr key={item.id} className="hover:bg-muted/20">
                        <td className="p-2">
                          <select
                            value={item.item_type}
                            onChange={(e) =>
                              updateItem(item.id, "item_type", e.target.value as "labor" | "part")
                            }
                            className="w-full h-8 px-1.5 text-xs border border-border rounded bg-surface"
                          >
                            <option value="labor">Mão de Obra</option>
                            <option value="part">Peça / Componente</option>
                          </select>
                        </td>
                        <td className="p-2">
                          <input
                            type="text"
                            required
                            placeholder="Descrição do trabalho ou peça..."
                            value={item.description}
                            onChange={(e) => updateItem(item.id, "description", e.target.value)}
                            className="w-full h-8 px-2 text-xs border border-border rounded bg-surface"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            min="1"
                            value={item.quantity}
                            onChange={(e) => updateItem(item.id, "quantity", e.target.value)}
                            className="w-full h-8 px-2 text-xs border border-border rounded bg-surface text-right"
                          />
                        </td>
                        <td className="p-2">
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={item.unit_price}
                            onChange={(e) => updateItem(item.id, "unit_price", e.target.value)}
                            className="w-full h-8 px-2 text-xs border border-border rounded bg-surface text-right font-mono"
                          />
                        </td>
                        <td className="p-2">
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              min="0"
                              placeholder="M"
                              title="Meses de Garantia"
                              value={item.warranty_months}
                              onChange={(e) => updateItem(item.id, "warranty_months", e.target.value)}
                              className="w-1/2 h-8 px-1 text-xs border border-border rounded bg-surface text-right"
                            />
                            <span className="text-[10px] text-muted">m</span>
                            <input
                              type="number"
                              min="0"
                              placeholder="KM"
                              title="KM de Garantia"
                              value={item.warranty_km}
                              onChange={(e) => updateItem(item.id, "warranty_km", e.target.value)}
                              className="w-1/2 h-8 px-1 text-xs border border-border rounded bg-surface text-right"
                            />
                          </div>
                        </td>
                        <td className="p-2 text-right font-mono font-bold text-ink">
                          {rowTotal.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })} MT
                        </td>
                        <td className="p-2 text-center">
                          <button
                            type="button"
                            aria-label={`Remover ${item.description || "linha sem descrição"}`}
                            onClick={() => removeItem(item.id)}
                            disabled={items.length <= 1}
                            className="rounded p-2 text-muted hover:bg-status-cancelled-soft hover:text-status-cancelled focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-30"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Financial Summary */}
          <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface-2 p-3 text-xs sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-1.5 text-muted font-medium">
              <Calculator size={16} /> Resumo Financeiro do Orçamento
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono tabular-nums">
              <div>
                Subtotal: <strong className="text-ink">{subtotal.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })} MT</strong>
              </div>
              <div>
                IVA (16%): <strong className="text-ink">{tax.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })} MT</strong>
              </div>
              <div className="text-sm font-bold text-accent-action-600">
                TOTAL: {total.toLocaleString("pt-MZ", { minimumFractionDigits: 2 })} MT
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t border-border">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" loading={submitting}>
              {isSupplemental ? "Guardar e enviar suplemento" : "Guardar e enviar orçamento"}
            </Button>
          </div>
        </form>
      </ModalDialog>
    </>
  );
}
