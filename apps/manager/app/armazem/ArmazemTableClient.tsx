"use client";

import { useState } from "react";
import { PackagePlus, Truck, Search, AlertCircle } from "lucide-react";
import type { Item, Warehouse } from "../lib/inventory-api";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { NewPartModal } from "@/app/components/NewPartModal";
import { GoodsReceiptModal } from "@/app/components/GoodsReceiptModal";

export function ArmazemTableClient({ initialItems, warehouses }: { initialItems: Item[], warehouses: Warehouse[] }) {
  const [search, setSearch] = useState("");
  const [isNewPartModalOpen, setIsNewPartModalOpen] = useState(false);
  const [receivingPart, setReceivingPart] = useState<Item | null>(null);

  const filtered = initialItems.filter(p => 
    p.name.toLowerCase().includes(search.toLowerCase()) || 
    (p.sku && p.sku.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Barra de Topo */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center bg-surface border border-border p-4 rounded-lg">
        <div className="relative w-full sm:max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={18} />
          <input
            type="text"
            placeholder="Pesquisar por SKU ou nome da peça..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg text-sm bg-surface-2 focus:bg-surface focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-all"
          />
        </div>
        <button
          onClick={() => setIsNewPartModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
        >
          <PackagePlus size={18} /> Cadastrar Nova Peça
        </button>
      </div>

      {/* Tabela Viva */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-xs uppercase text-muted border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">SKU</th>
                <th className="px-4 py-3 text-left font-semibold">Designação do Material</th>
                <th className="px-4 py-3 text-right font-semibold">Custo Médio Unit.</th>
                <th className="px-4 py-3 text-center font-semibold">Unidade</th>
                <th className="px-4 py-3 text-right font-semibold">Stock Físico</th>
                <th className="px-4 py-3 text-center font-semibold">Status</th>
                <th className="px-4 py-3 text-right font-semibold">Acções</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted">
                    Nenhuma peça encontrada. Comece por "Cadastrar Nova Peça".
                  </td>
                </tr>
              ) : (
                filtered.map(part => {
                  const currentStock = Number(part.current_stock);
                  // TODO: use real minimum_stock from Item when available
                  const minStock = 5; 
                  const isLowStock = currentStock <= minStock;
                  const isZero = currentStock === 0;

                  return (
                    <tr key={part.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-mono text-muted text-xs">{part.sku || "N/A"}</td>
                      <td className="px-4 py-3 font-medium text-ink">{part.name}</td>
                      <td className="px-4 py-3 text-right text-muted font-mono">
                        {Number(part.average_unit_cost).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                      </td>
                      <td className="px-4 py-3 text-center text-muted text-xs uppercase tracking-wider">{part.unit_of_measure}</td>
                      <td className={`px-4 py-3 text-right font-bold text-lg ${isZero ? "text-red-600" : isLowStock ? "text-amber-600" : "text-green-600"}`}>
                        {currentStock.toLocaleString("pt-MZ")}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {isZero ? (
                          <StatusBadge status="erro" label="Ruptura" />
                        ) : isLowStock ? (
                          <StatusBadge status="alerta" label="Baixo" />
                        ) : (
                          <StatusBadge status="concluida" label="Normal" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setReceivingPart(part)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-surface border border-border hover:border-amber-500 hover:text-amber-600 rounded-md text-xs font-semibold transition-all shadow-sm"
                        >
                          <Truck size={14} /> Dar Entrada
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isNewPartModalOpen && (
        <NewPartModal
          onClose={() => setIsNewPartModalOpen(false)}
          onSuccess={() => window.location.reload()}
        />
      )}

      {receivingPart && (
        <GoodsReceiptModal
          part={receivingPart}
          warehouses={warehouses}
          onClose={() => setReceivingPart(null)}
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
}
