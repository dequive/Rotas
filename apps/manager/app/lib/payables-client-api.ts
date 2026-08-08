"use client";

import { bffFetch } from "./bff";
import type { InvoicePaymentRequest } from "./payables-api";

export function paySupplierInvoice(invoiceId: string, payload: InvoicePaymentRequest) {
  return bffFetch(`/api/v1/payables/invoices/${invoiceId}/pay`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
