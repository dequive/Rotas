"use client";

import { useState } from "react";
import { X, CheckCircle, PackagePlus } from "lucide-react";
import { createItem } from "../lib/inventory-api";

export function NewPartModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("UN");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await createItem({
        sku,
        name,
        unit_of_measure: unit
      });
      onSuccess();
    } catch (err) {
      alert("Erro ao criar peça. Verifique se o SKU já existe.");
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
            <PackagePlus className="text-amber-600" /> Cadastrar Nova Peça
          </h3>
          <button onClick={onClose} className="text-muted hover:text-ink"><X size={20} /></button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Referência (SKU)</label>
            <input
              type="text"
              required
              placeholder="Ex: FILT-AR-MAN-TGS"
              value={sku}
              onChange={e => setSku(e.target.value)}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm uppercase"
            />
          </div>
          
          <div>
            <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Designação da Peça / Material</label>
            <input
              type="text"
              required
              placeholder="Ex: Filtro de Ar MAN TGS"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border border-border rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Unidade de Medida</label>
              <select 
                value={unit} 
                onChange={e => setUnit(e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm"
              >
                <option value="UN">Unidade (UN)</option>
                <option value="LT">Litros (LT)</option>
                <option value="MT">Metros (MT)</option>
                <option value="KG">Quilos (KG)</option>
                <option value="CX">Caixa (CX)</option>
              </select>
            </div>
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
              {loading ? "A processar..." : <><CheckCircle size={16} /> Cadastrar Material</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
