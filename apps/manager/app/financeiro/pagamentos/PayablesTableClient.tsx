"use client";

import { useState } from "react";
import type { SupplierInvoice } from "@/app/lib/payables-api";
import { SupplierPaymentModal } from "@/app/components/SupplierPaymentModal";
import { StatusBadge } from "@/app/components/ui/StatusBadge";
import { Building2, DollarSign } from "lucide-react";

export type InvoiceWithSupplier = SupplierInvoice & { supplierName: string };

export function PayablesTableClient({ initialInvoices }: { initialInvoices: InvoiceWithSupplier[] }) {
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceWithSupplier | null>(null);

  const pending = initialInvoices.filter(i => i.status !== "paid");
  const paid = initialInvoices.filter(i => i.status === "paid");

  return (
    <div className="space-y-8">
      {/* Pending Invoices */}
      <section className="bg-surface border border-border rounded-lg overflow-hidden">
        <div className="p-4 border-b border-border bg-surface-2">
          <h2 className="font-semibold flex items-center gap-2">
            <DollarSign className="text-amber-600" /> Faturas por Liquidar ({pending.length})
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-xs uppercase text-muted border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Fornecedor</th>
                <th className="px-4 py-3 text-left font-semibold">Nº Fatura</th>
                <th className="px-4 py-3 text-left font-semibold">Emissão</th>
                <th className="px-4 py-3 text-left font-semibold">Vencimento</th>
                <th className="px-4 py-3 text-left font-semibold">Valor</th>
                <th className="px-4 py-3 text-left font-semibold">Estado</th>
                <th className="px-4 py-3 text-right font-semibold">Acções</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {pending.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted">Não há faturas pendentes de pagamento.</td>
                </tr>
              ) : (
                pending.map(inv => (
                  <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium flex items-center gap-2">
                      <Building2 size={16} className="text-muted" />
                      {inv.supplierName}
                    </td>
                    <td className="px-4 py-3 text-muted">{inv.invoice_number || 'S/N'}</td>
                    <td className="px-4 py-3">{inv.issued_at.slice(0, 10)}</td>
                    <td className="px-4 py-3">
                      {inv.due_date ? inv.due_date.slice(0, 10) : <span className="text-muted">—</span>}
                    </td>
                    <td className="px-4 py-3 font-bold text-ink">
                      {Number(inv.amount).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge 
                        status={inv.status === "partially_paid" ? "pending" : "alerta"} 
                        label={inv.status === "partially_paid" ? "Parcial" : "Pendente"} 
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button 
                        onClick={() => setSelectedInvoice(inv)}
                        className="px-3 py-1.5 bg-amber-100 text-amber-800 hover:bg-amber-200 font-medium rounded-md text-xs transition-colors"
                      >
                        Pagar
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Paid Invoices */}
      {paid.length > 0 && (
        <section className="bg-surface border border-border rounded-lg overflow-hidden opacity-70 hover:opacity-100 transition-opacity">
          <div className="p-4 border-b border-border bg-surface-2">
            <h2 className="font-semibold flex items-center gap-2">
              <DollarSign className="text-green-600" /> Faturas Liquidadas (Histórico)
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs uppercase text-muted border-b border-border">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Fornecedor</th>
                  <th className="px-4 py-3 text-left font-semibold">Nº Fatura</th>
                  <th className="px-4 py-3 text-left font-semibold">Valor</th>
                  <th className="px-4 py-3 text-left font-semibold">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paid.map(inv => (
                  <tr key={inv.id}>
                    <td className="px-4 py-3 font-medium text-muted">{inv.supplierName}</td>
                    <td className="px-4 py-3 text-muted">{inv.invoice_number || 'S/N'}</td>
                    <td className="px-4 py-3 text-muted">
                      {Number(inv.amount).toLocaleString("pt-MZ", { style: "currency", currency: "MZN" })}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status="concluida" label="Pago" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {selectedInvoice && (
        <SupplierPaymentModal
          invoice={selectedInvoice}
          supplierName={selectedInvoice.supplierName}
          onClose={() => setSelectedInvoice(null)}
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
}
