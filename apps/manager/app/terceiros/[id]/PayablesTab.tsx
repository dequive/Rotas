"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { PurchaseOrderModal } from "./PurchaseOrderModal";
import { SupplierPaymentModal } from "./SupplierPaymentModal";
import { FileDown } from "lucide-react";
import { bffRequest } from "@/app/lib/bff";

interface SupplierInvoice {
  id: string;
  invoice_number: string;
  description: string;
  amount: string;
  currency: string;
  status: "draft" | "approved" | "pending" | "paid" | "void";
  issued_at: string;
}

interface PurchaseOrder {
  id: string;
  order_number: string;
  description: string;
  estimated_cost: string;
  status: "draft" | "sent" | "fulfilled" | "cancelled";
  created_at: string;
}

function fmt(v: string, currency = "MZN") {
  return parseFloat(v || "0").toLocaleString("pt-MZ", {
    style: "currency",
    currency,
  });
}

const statusColors: Record<string, string> = {
  draft: "bg-surface-3 text-muted",
  sent: "bg-blue-500/10 text-blue-500",
  approved: "bg-blue-500/10 text-blue-500",
  fulfilled: "bg-green-500/10 text-green-500",
  paid: "bg-green-500/10 text-green-500",
  cancelled: "bg-red-500/10 text-red-500",
};

export default function PayablesTab({ thirdPartyId }: { thirdPartyId: string }) {
  const [invoices, setInvoices] = useState<SupplierInvoice[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPoModalOpen, setIsPoModalOpen] = useState(false);
  const [invoiceToPay, setInvoiceToPay] = useState<SupplierInvoice | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch both POs and Invoices for this supplier
      // Note: Backend endpoints need to exist for these
      const [invRes, ordRes] = await Promise.all([
        bffRequest(`/api/v1/payables/invoices?third_party_id=${thirdPartyId}`),
        bffRequest(`/api/v1/payables/orders?third_party_id=${thirdPartyId}`)
      ]);

      if (invRes.ok) {
        const invData = await invRes.json();
        setInvoices(invData.items || invData);
      }
      if (ordRes.ok) {
        const ordData = await ordRes.json();
        setOrders(ordData.items || ordData);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [thirdPartyId]);

  const handleDownloadPDF = async (poId: string) => {
    try {
      const res = await bffRequest(`/api/v1/payables/purchase-orders/${poId}/pdf`);
      if (!res.ok) throw new Error("Erro ao gerar PDF");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Requisicao_${poId.substring(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      console.error(e);
      alert("Falha ao gerar o PDF da requisição.");
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="mt-4 flex items-center justify-center h-32 bg-surface border border-border rounded-lg">
        <span className="text-sm text-muted animate-pulse">A carregar documentos...</span>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-6">
      
      {/* Invoices Section */}
      <div className="bg-surface border border-border rounded-lg p-6 shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-base font-semibold text-ink m-0">Faturas Recebidas (Custo Efetivo)</h2>
          <button className="h-9 px-3.5 rounded-md border-none bg-amber text-ink text-[13px] font-bold cursor-pointer hover:bg-amber-dark transition-colors">
            + Nova Fatura
          </button>
        </div>
        
        {invoices.length === 0 ? (
          <div className="py-8 text-center border border-dashed border-border rounded-md bg-surface-2">
            <p className="text-[13px] text-muted m-0">Nenhuma fatura recebida deste fornecedor.</p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-border rounded-md">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="bg-surface-2 border-b border-border">
                  <th className="py-2.5 px-4 font-semibold text-ink">Data</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Número</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Descrição</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Valor</th>
                  <th className="py-2.5 px-4 font-semibold text-ink text-right">Estado</th>
                  <th className="py-2.5 px-4 font-semibold text-ink text-center">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="py-3 px-4 text-muted whitespace-nowrap">
                      {new Date(inv.issued_at).toLocaleDateString("pt-MZ")}
                    </td>
                    <td className="py-3 px-4 font-medium text-ink">{inv.invoice_number || "-"}</td>
                    <td className="py-3 px-4 text-muted max-w-xs truncate">{inv.description || "-"}</td>
                    <td className="py-3 px-4 font-mono text-ink">{fmt(inv.amount, inv.currency)}</td>
                    <td className="py-3 px-4 text-right">
                      <span className={cn("px-2 py-1 rounded text-[11px] font-semibold uppercase tracking-wider", statusColors[inv.status])}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {inv.status === "pending" && (
                        <button
                          onClick={() => setInvoiceToPay(inv)}
                          className="h-7 px-3 rounded text-[11px] font-bold uppercase tracking-wider bg-green-100 text-green-700 hover:bg-green-200 transition-colors border border-green-200"
                        >
                          Pagar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Purchase Orders Section */}
      <div className="bg-surface border border-border rounded-lg p-6 shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-base font-semibold text-ink m-0">Requisições Emitidas (Estimativa)</h2>
          <button 
            onClick={() => setIsPoModalOpen(true)}
            className="h-9 px-3.5 rounded-md border border-border bg-surface text-ink text-[13px] font-semibold cursor-pointer hover:bg-surface-2 transition-colors"
          >
            + Nova Requisição
          </button>
        </div>
        
        {orders.length === 0 ? (
          <div className="py-8 text-center border border-dashed border-border rounded-md bg-surface-2">
            <p className="text-[13px] text-muted m-0">Nenhuma requisição pendente.</p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-border rounded-md">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="bg-surface-2 border-b border-border">
                  <th className="py-2.5 px-4 font-semibold text-ink">Data</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Nº Req</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Descrição</th>
                  <th className="py-2.5 px-4 font-semibold text-ink">Estimativa</th>
                  <th className="py-2.5 px-4 font-semibold text-ink text-right">Estado</th>
                  <th className="py-2.5 px-4 font-semibold text-ink text-center">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-surface-2/50 transition-colors">
                    <td className="py-3 px-4 text-muted whitespace-nowrap">
                      {new Date(ord.created_at).toLocaleDateString("pt-MZ")}
                    </td>
                    <td className="py-3 px-4 font-medium text-ink">{ord.order_number}</td>
                    <td className="py-3 px-4 text-muted max-w-xs truncate">{ord.description || "-"}</td>
                    <td className="py-3 px-4 font-mono text-ink">{fmt(ord.estimated_cost, "MZN")}</td>
                    <td className="py-3 px-4 text-right">
                      <span className={cn("px-2 py-1 rounded text-[11px] font-semibold uppercase tracking-wider", statusColors[ord.status])}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => handleDownloadPDF(ord.id)}
                        className="h-7 px-2 rounded text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors inline-flex items-center gap-1"
                        title="Descarregar PDF"
                      >
                        <FileDown size={14} /> PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <PurchaseOrderModal 
        isOpen={isPoModalOpen}
        onClose={() => {
          setIsPoModalOpen(false);
          fetchData(); // Refresh the list
        }}
        thirdPartyId={thirdPartyId}
      />

      {invoiceToPay && (
        <SupplierPaymentModal 
          isOpen={true}
          onClose={() => {
            setInvoiceToPay(null);
            fetchData(); // Refresh to update invoice status
          }}
          thirdPartyId={thirdPartyId}
          invoiceId={invoiceToPay.id}
          maxAmount={Number(invoiceToPay.amount)}
        />
      )}
    </div>
  );
}
