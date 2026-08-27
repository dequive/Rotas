"use client";

import { useState } from "react";
import { X, ShoppingCart, CheckCircle2 } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";
import { buildPurchaseOrderRequest } from "@/app/lib/finance-contracts";

export function PurchaseOrderModal({
  isOpen,
  onClose,
  thirdPartyId,
}: {
  isOpen: boolean;
  onClose: () => void;
  thirdPartyId: string;
}) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Form state
  const [orderNumber, setOrderNumber] = useState("");
  const [description, setDescription] = useState("");
  const [estimatedCost, setEstimatedCost] = useState("");

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description || !estimatedCost) {
      alert("A descrição e o custo estimado são obrigatórios.");
      return;
    }

    setLoading(true);
    try {
      const res = await bffRequest("/api/v1/payables/purchase-orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildPurchaseOrderRequest({
          thirdPartyId,
          orderNumber: orderNumber || `PO-${Date.now().toString().slice(-6)}`,
          description,
          estimatedAmount: parseFloat(estimatedCost),
          issuedAt: new Date().toISOString(),
        })),
      });

      if (!res.ok) throw new Error("Erro ao gerar a requisição.");

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
        // Here we could trigger a callback to refresh the parent list
      }, 2000);
    } catch (err) {
      console.error(err);
      alert("Falha de comunicação com o servidor.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
        
        <div className="border-b border-slate-200 p-4 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800 flex items-center gap-2">
            <ShoppingCart size={18} className="text-slate-500" />
            Nova Requisição de Compra
          </h2>
          <button 
            onClick={onClose}
            className="p-1 hover:bg-slate-100 rounded-md text-slate-500 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {success ? (
          <div className="p-12 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-4">
              <CheckCircle2 size={32} />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Enviada!</h3>
            <p className="text-sm text-slate-500 mt-2">
              A requisição foi gravada e o fornecedor será notificado.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Nº da Requisição (Opcional)
              </label>
              <input 
                type="text" 
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                placeholder="Gerado automaticamente se vazio"
                className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none w-full"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Descrição do Pedido *
              </label>
              <textarea 
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex: Aquisição de 4 Pneus Bridgestone 295/80R22.5"
                className="p-3 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none w-full resize-none"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Custo Estimado *
              </label>
              <div className="relative">
                <input 
                  type="number" 
                  step="0.01"
                  value={estimatedCost}
                  onChange={(e) => setEstimatedCost(e.target.value)}
                  placeholder="0.00"
                  className="h-10 pl-3 pr-12 rounded-lg border border-slate-200 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none w-full font-mono font-medium text-slate-900"
                  required
                />
                <span className="absolute right-3 top-2.5 text-slate-400 font-mono text-sm">MZN</span>
              </div>
              <p className="text-[11px] text-muted mt-1">Este valor servirá para orçamentar a tarefa até a fatura real chegar.</p>
            </div>

            <div className="pt-2 flex justify-end gap-3 mt-2">
              <button 
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button 
                type="submit"
                disabled={loading}
                className="px-6 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {loading ? "A gerar..." : "Gerar Requisição"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
