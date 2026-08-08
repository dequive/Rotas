"use client";

import { useState } from "react";
import { X, FileText, CheckCircle2 } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

export function ExternalCostModal({
  isOpen,
  onClose,
  workOrderId,
}: {
  isOpen: boolean;
  onClose: () => void;
  workOrderId: string;
}) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Form State
  const [thirdPartyId, setThirdPartyId] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!thirdPartyId || !amount || !issuedAt) {
      alert("Por favor, preencha os campos obrigatórios (Fornecedor, Data, Valor).");
      return;
    }

    setLoading(true);
    try {
      const res = await bffRequest("/api/v1/payables/invoices", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          third_party_id: thirdPartyId,
          work_order_id: workOrderId,
          invoice_number: invoiceNumber,
          description: description,
          amount: parseFloat(amount),
          currency: "MZN",
          issued_at: new Date(issuedAt).toISOString(),
        }),
      });

      if (!res.ok) throw new Error("Erro ao registar a fatura.");
      
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
        // Option to refresh the execution panel here
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
            <FileText size={18} className="text-slate-500" />
            Registar Fatura de Fornecedor
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
            <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-4">
              <CheckCircle2 size={32} />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Sucesso!</h3>
            <p className="text-sm text-slate-500 mt-2">
              A fatura foi registada e encaminhada para o Razão Geral.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Fornecedor (Entidade) *
              </label>
              <select 
                value={thirdPartyId}
                onChange={(e) => setThirdPartyId(e.target.value)}
                className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 outline-none w-full"
                required
              >
                <option value="">Selecione o Fornecedor...</option>
                {/* Num cenário real isto seria carregado via API listando as Entidades com role 'supplier' */}
                <option value="605c0836-e6c1-4b71-a46b-8cf34861e670">Puma Energy</option>
                <option value="fake-id-2">Oficina Auto-Fix</option>
                <option value="fake-id-3">Loja de Peças Central</option>
              </select>
            </div>

            <div className="flex gap-4">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Nº da Fatura
                </label>
                <input 
                  type="text" 
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  placeholder="Ex: FT-2023/1"
                  className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 outline-none w-full"
                />
              </div>
              <div className="flex flex-col gap-1.5 w-1/3">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Data *
                </label>
                <input 
                  type="date" 
                  value={issuedAt}
                  onChange={(e) => setIssuedAt(e.target.value)}
                  className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 outline-none w-full"
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Descrição do Serviço / Compra
              </label>
              <textarea 
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex: Substituição das pastilhas de travão e mão de obra associada."
                className="p-3 rounded-lg border border-slate-200 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 outline-none w-full resize-none"
              />
            </div>

            <div className="flex gap-4">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Valor Total *
                </label>
                <div className="relative">
                  <input 
                    type="number" 
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    className="h-10 pl-3 pr-12 rounded-lg border border-slate-200 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500 outline-none w-full font-mono font-medium text-slate-900"
                    required
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-mono text-sm">MZN</span>
                </div>
              </div>
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
                className="px-6 py-2 text-sm font-bold text-white bg-amber-500 hover:bg-amber-600 rounded-lg transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {loading ? "A registar..." : "Registar Fatura"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
