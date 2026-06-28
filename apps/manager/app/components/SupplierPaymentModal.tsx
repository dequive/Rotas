"use client";

import { useState } from "react";
import { X, CheckCircle, CreditCard } from "lucide-react";
import { SupplierInvoice, paySupplierInvoice } from "../lib/payables-api";

export function SupplierPaymentModal({
  invoice,
  supplierName,
  onClose,
  onSuccess,
}: {
  invoice: SupplierInvoice;
  supplierName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [amount, setAmount] = useState(invoice.amount.toString());
  const [method, setMethod] = useState("bank_transfer");
  const [reference, setReference] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));

  const handlePay = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await paySupplierInvoice(invoice.id, {
        amount: Number(amount),
        payment_method: method,
        value_date: new Date(date).toISOString(),
        reference,
      });
      onSuccess();
    } catch (err) {
      alert("Erro ao processar pagamento!");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-surface rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-2">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <CreditCard className="text-amber-600" /> Liquidar Fatura
          </h3>
          <button onClick={onClose} className="text-muted hover:text-ink"><X size={20} /></button>
        </div>

        <form onSubmit={handlePay} className="p-6 space-y-4">
          <div className="bg-amber-50/50 border border-amber-100 rounded-lg p-3 text-sm">
            <p className="text-muted">A liquidar fatura <strong>{invoice.invoice_number || 'S/N'}</strong> de:</p>
            <p className="font-semibold text-amber-900 text-lg">{supplierName}</p>
            <p className="text-amber-800/70 text-xs">Total da Fatura: {Number(invoice.amount).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Valor a Pagar (MZN)</label>
              <input
                type="number"
                step="0.01"
                required
                value={amount}
                onChange={e => setAmount(e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 text-lg font-bold"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Data-Valor</label>
                <input
                  type="date"
                  required
                  value={date}
                  onChange={e => setDate(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Meio de Pagamento</label>
                <select 
                  value={method} 
                  onChange={e => setMethod(e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                >
                  <option value="bank_transfer">Transferência Bancária</option>
                  <option value="cheque">Cheque</option>
                  <option value="cash">Numerário (Caixa)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1">Referência (Comprovativo)</label>
              <input
                type="text"
                placeholder="Ex: OP-2026/12"
                value={reference}
                onChange={e => setReference(e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm"
              />
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
              {loading ? "A processar..." : <><CheckCircle size={16} /> Confirmar Lançamento</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
