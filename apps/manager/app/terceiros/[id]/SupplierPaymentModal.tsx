"use client";

import { useState } from "react";
import { X, Landmark, CheckCircle2 } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

export function SupplierPaymentModal({
  isOpen,
  onClose,
  thirdPartyId,
  invoiceId,
  maxAmount,
}: {
  isOpen: boolean;
  onClose: () => void;
  thirdPartyId: string;
  invoiceId: string;
  maxAmount: number;
}) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Form State
  const [amount, setAmount] = useState(maxAmount.toString());
  const [paymentDate, setPaymentDate] = useState("");
  const [reference, setReference] = useState("");

  if (!isOpen) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!amount || !paymentDate) {
      alert("Por favor preencha o valor e a data.");
      return;
    }

    setLoading(true);
    try {
      const res = await bffRequest("/api/v1/payables/payments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          third_party_id: thirdPartyId,
          supplier_invoice_id: invoiceId,
          amount: parseFloat(amount),
          currency: "MZN",
          payment_date: new Date(paymentDate).toISOString(),
          reference: reference,
        }),
      });

      if (!res.ok) throw new Error("Erro ao registar pagamento.");

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
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
            <Landmark size={18} className="text-slate-500" />
            Registar Pagamento
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
            <h3 className="text-lg font-bold text-slate-900">Pago com Sucesso!</h3>
            <p className="text-sm text-slate-500 mt-2">
              A conta do fornecedor foi regularizada e o movimento lançado no Ledger.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
            <div className="flex gap-4">
              <div className="flex flex-col gap-1.5 flex-1">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Valor a Pagar *
                </label>
                <div className="relative">
                  <input 
                    type="number" 
                    step="0.01"
                    max={maxAmount}
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="h-10 pl-3 pr-12 rounded-lg border border-slate-200 text-sm focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none w-full font-mono font-medium text-slate-900"
                    required
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-mono text-sm">MZN</span>
                </div>
              </div>
              <div className="flex flex-col gap-1.5 w-1/2">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Data *
                </label>
                <input 
                  type="date" 
                  value={paymentDate}
                  onChange={(e) => setPaymentDate(e.target.value)}
                  className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none w-full"
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                Referência (Ex: Nº Transferência ou Cheque)
              </label>
              <input 
                type="text" 
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="Ex: TRF-MillenniumBIM-10293"
                className="h-10 px-3 rounded-lg border border-slate-200 text-sm focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none w-full"
              />
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
                className="px-6 py-2 text-sm font-bold text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {loading ? "A processar..." : "Confirmar Pagamento"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
