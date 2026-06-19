"use client";

import { useState } from "react";
import { registerPayment, type ClientPaymentPayload } from "@/app/lib/billing-api";

interface PaymentModalProps {
  clientId: string;
  clientName: string;
  invoiceId?: string;
  invoiceNumber?: string | null;
  invoiceTotal?: string | null;
  invoiceOutstanding?: string | null;
  advanceMode?: boolean;
  onSuccess?: () => void;
  trigger?: React.ReactNode;
}

export function PaymentModal({
  clientId,
  clientName,
  invoiceId,
  invoiceNumber,
  invoiceTotal: _invoiceTotal,
  invoiceOutstanding,
  advanceMode = false,
  onSuccess,
  trigger,
}: PaymentModalProps) {
  const [open, setOpen] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [amount, setAmount] = useState("");
  const [valueDate, setValueDate] = useState(new Date().toISOString().slice(0, 10));
  const [paymentMethod, setPaymentMethod] = useState<"bank_transfer" | "cheque" | "cash">("bank_transfer");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");

  const handleOpen = () => {
    setIdempotencyKey(crypto.randomUUID());
    setError(null);
    setAmount("");
    setValueDate(new Date().toISOString().slice(0, 10));
    setPaymentMethod("bank_transfer");
    setReference("");
    setNotes("");
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate amount against outstanding balance when in invoice mode
    if (!advanceMode && invoiceOutstanding) {
      const amountNum = parseFloat(amount);
      const outstandingNum = parseFloat(invoiceOutstanding);
      if (!isNaN(amountNum) && !isNaN(outstandingNum) && amountNum > outstandingNum) {
        setError("O valor excede o saldo em aberto");
        return;
      }
    }

    setLoading(true);
    setError(null);
    try {
      const payload: ClientPaymentPayload = {
        client_id: clientId,
        billing_document_id: advanceMode ? null : (invoiceId ?? null),
        amount: amount,
        value_date: new Date(valueDate).toISOString(),
        payment_method: paymentMethod,
        reference: reference || null,
        notes: notes || null,
      };
      await registerPayment(payload, idempotencyKey);
      setOpen(false);
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registar pagamento");
    } finally {
      setLoading(false);
    }
  };

  // Build modal title
  const modalTitle = advanceMode
    ? `Registar Adiantamento — ${clientName}`
    : invoiceNumber
    ? `Registar Pagamento — Fatura ${invoiceNumber}`
    : `Registar Pagamento — ${clientName}`;

  return (
    <>
      {trigger ? (
        <span onClick={handleOpen} style={{ cursor: "pointer" }}>
          {trigger}
        </span>
      ) : (
        <button
          type="button"
          onClick={handleOpen}
          className="text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded px-2 py-1"
        >
          {advanceMode ? "Registar Adiantamento" : "Registar Pagamento"}
        </button>
      )}

      {open && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={(e) => {
            if (e.target === e.currentTarget) handleClose();
          }}
        >
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {modalTitle}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Amount */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Valor (MZN)
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
                {!advanceMode && invoiceOutstanding && (
                  <p className="mt-1 text-[11px] font-mono text-gray-500">
                    Saldo em aberto: MZN {parseFloat(invoiceOutstanding).toLocaleString("pt-MZ", { minimumFractionDigits: 2 })}
                  </p>
                )}
              </div>

              {/* Value date */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Data valor
                </label>
                <input
                  type="date"
                  value={valueDate}
                  onChange={(e) => setValueDate(e.target.value)}
                  required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>

              {/* Payment method */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Método
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value as "bank_transfer" | "cheque" | "cash")}
                  required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 bg-white"
                >
                  <option value="bank_transfer">Transferência Bancária</option>
                  <option value="cheque">Cheque</option>
                  <option value="cash">Numerário</option>
                </select>
              </div>

              {/* Reference */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Referência <span className="font-normal normal-case text-gray-400">(opcional)</span>
                </label>
                <input
                  type="text"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Nº de transferência, cheque, etc."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  Notas <span className="font-normal normal-case text-gray-400">(opcional)</span>
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Observações adicionais..."
                  rows={2}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 resize-none"
                />
              </div>

              {/* Error */}
              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="flex-1 border border-gray-200 rounded-lg px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 bg-amber-500 hover:bg-amber-600 text-white rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50 transition-colors"
                >
                  {loading ? "A registar..." : "Registar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
