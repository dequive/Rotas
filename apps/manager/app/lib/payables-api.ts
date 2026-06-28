import { apiFetch } from "./api";

export interface SupplierInvoice {
  id: string;
  third_party_id: string;
  invoice_number: string | null;
  description: string | null;
  amount: number;
  currency: string;
  issued_at: string;
  due_date: string | null;
  status: string;
  created_at: string;
}

export interface InvoicePaymentRequest {
  amount: number;
  payment_method: string;
  value_date: string;
  reference?: string;
  notes?: string;
}

export async function loadSupplierInvoices(): Promise<SupplierInvoice[]> {
  try {
    return await apiFetch<SupplierInvoice[]>("/api/v1/payables/invoices", { revalidate: 0 });
  } catch {
    return [];
  }
}

export async function paySupplierInvoice(invoiceId: string, payload: InvoicePaymentRequest) {
  return apiFetch(`/api/v1/payables/invoices/${invoiceId}/pay`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
