"use client";

import { useState } from "react";
import { X, CheckCircle, Truck } from "lucide-react";
import { Item, Warehouse, registerStockIn } from "../lib/inventory-api";

export function GoodsReceiptModal({
  part,
  warehouses,
  onClose,
  onSuccess,
}: {
  part: Item;
  warehouses: Warehouse[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id || "");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [reference, setReference] = useState("");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!warehouseId) {
      alert("Selecione um armazém.");
      return;
    }
    setLoading(true);
    try {
      await registerStockIn({
        item_id: part.id,
        warehouse_id: warehouseId,
        quantity: Number(quantity),
        unit_cost: Number(unitCost),
        reference_doc: reference,
        notes: "Entrada via Dashboard",
      });
      onSuccess();
    } catch (err) {
      alert("Erro ao dar entrada de material no armazém.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-surface rounded-xl shadow-2xl w-full max-w-md overflow-hidden border border-border">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-2">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <Truck className="text-amber-600" /> Entrada de Material
          </h3>
          <button onClick={onClose} className="text-muted hover:text-ink"><X size={20} /></button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-4">
          <div className="bg-amber-50/50 border border-amber-100 rounded-lg p-3 text-sm">
            <p className="text-muted">A dar entrada de stock para:</p>
            <p className="font-semibold text-amber-900 text-lg">{part.sku || "N/A"} - {part.name}</p>
            <p className="text-amber-800/70 text-xs">Stock Atual: {Number(part.current_stock).toLocaleString("pt-MZ")} {part.unit_of_measure}s</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Armazém de Destino</label>
            <select
              required
              value={warehouseId}
              onChange={e => setWarehouseId(e.target.value)}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface-2 focus:bg-surface"
            >
              <option value="" disabled>Selecione um armazém</option>
              {warehouses.map(w => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Quantidade Recebida</label>
              <input
                type="number"
                step="0.01"
                required
                min="0.01"
                value={quantity}
                onChange={e => setQuantity(e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 text-lg font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Custo Unitário (MZN)</label>
              <input
                type="number"
                step="0.01"
                required
                min="0"
                value={unitCost}
                onChange={e => setUnitCost(e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 text-lg font-bold text-ink"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Guia / Referência</label>
            <input
              type="text"
              required
              placeholder="Ex: GT-2026/01"
              value={reference}
              onChange={e => setReference(e.target.value)}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm uppercase"
            />
          </div>

          <div className="pt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-muted"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 flex items-center gap-2"
            >
              {loading ? "A processar..." : <><CheckCircle size={16} /> Confirmar Entrada</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
