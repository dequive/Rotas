"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, PackageMinus, Truck } from "lucide-react";
import { Button } from "@/app/components/ui/Button";
import * as Dialog from "@radix-ui/react-dialog";
import { Item, Warehouse, registerStockOut } from "@/app/lib/inventory-api";

interface Props {
  part: Item;
  warehouses: Warehouse[];
  vehicles: { id: string; plate: string }[];
}

export function PartConsumptionModal({ part, warehouses, vehicles }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id || "");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const form = new FormData(e.currentTarget);
    const qty = Number(form.get("quantity"));
    const vehicleId = form.get("vehicle_id") as string;
    const notes = form.get("notes") as string;

    if (qty <= 0 || qty > Number(part.current_stock)) {
      setError("Quantidade inválida ou superior ao stock.");
      setLoading(false);
      return;
    }

    if (!warehouseId) {
      setError("Selecione um armazém.");
      setLoading(false);
      return;
    }

    try {
      await registerStockOut({
        item_id: part.id,
        warehouse_id: warehouseId,
        quantity: qty,
        reference_doc: `WO-VEHICLE-${vehicleId}`,
        notes: notes
      });

      setOpen(false);
      router.refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-bold text-xs rounded-lg transition-colors border border-indigo-200 shadow-sm">
          <PackageMinus size={14} /> Consumir
        </button>
      </Dialog.Trigger>
      
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 transition-opacity" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl z-50">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center">
              <PackageMinus size={20} />
            </div>
            <div>
              <Dialog.Title className="text-xl font-black text-slate-900">
                Registar Consumo
              </Dialog.Title>
              <Dialog.Description className="text-sm font-medium text-slate-500">
                Lançar a saída da peça: <span className="font-bold text-slate-700">{part.name}</span>
              </Dialog.Description>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 px-3 py-2 rounded-lg text-sm font-bold">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Armazém de Origem</label>
              <select
                required
                value={warehouseId}
                onChange={e => setWarehouseId(e.target.value)}
                className="w-full border-2 border-slate-200 rounded-xl px-4 py-3 text-slate-700 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-all outline-none"
              >
                <option value="" disabled>Selecione um armazém</option>
                {warehouses.map(w => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Stock Disponível</label>
                <div className="text-2xl font-black text-slate-900 border-2 border-slate-100 bg-slate-50 rounded-xl px-4 py-3 flex items-center justify-between">
                  <span>{Number(part.current_stock).toLocaleString("pt-MZ")}</span>
                  <span className="text-sm font-bold text-slate-400">{part.unit_of_measure}</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Qtd. Gasta</label>
                <input 
                  required 
                  name="quantity" 
                  type="number" 
                  step="0.01" 
                  min="0.01" 
                  max={Number(part.current_stock)}
                  defaultValue={1}
                  className="h-11 border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl px-3 font-mono text-slate-900 font-bold"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Aplicar em Viatura</label>
              <div className="relative">
                <Truck size={16} className="absolute left-3 top-3.5 text-slate-400" />
                <select 
                  required 
                  name="vehicle_id"
                  className="w-full h-11 pl-10 pr-4 bg-white border border-slate-200 rounded-xl text-sm font-bold text-slate-900 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10"
                >
                  <option value="">Selecione uma viatura...</option>
                  {vehicles.map(v => (
                    <option key={v.id} value={v.id}>{v.plate}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wide">Notas de Intervenção</label>
              <input 
                name="notes" 
                placeholder="Ex: Pneu furado na N1, substituição de emergência."
                className="h-11 w-full border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl px-3 text-sm font-medium text-slate-900"
              />
            </div>

            <div className="pt-4 flex gap-3">
              <Dialog.Close asChild>
                <Button type="button" variant="outline" className="flex-1 h-12 rounded-xl font-bold">Cancelar</Button>
              </Dialog.Close>
              <Button type="submit" disabled={loading} className="flex-1 h-12 rounded-xl font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg shadow-indigo-600/20">
                {loading ? <Loader2 className="animate-spin" size={20} /> : "Registar & Contabilizar"}
              </Button>
            </div>
            <p className="text-center text-[10px] text-slate-400 mt-2 font-medium">A contabilidade da viatura será atualizada automaticamente.</p>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
