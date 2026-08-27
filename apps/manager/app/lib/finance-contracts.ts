interface JournalLineRequest {
  account_id: string;
  debit: number;
  credit: number;
}

export function buildJournalEntryRequest(input: {
  journalType: string;
  date: string;
  reference: string;
  description: string;
  lines: JournalLineRequest[];
}) {
  return {
    journal_type: input.journalType,
    date: new Date(input.date).toISOString(),
    reference: input.reference,
    description: input.description,
    lines: input.lines,
  };
}

export function buildPurchaseOrderRequest(input: {
  thirdPartyId: string;
  orderNumber: string;
  description: string;
  estimatedAmount: number;
  issuedAt: string;
}) {
  return {
    third_party_id: input.thirdPartyId,
    po_number: input.orderNumber,
    description: input.description,
    estimated_amount: input.estimatedAmount,
    currency: "MZN",
    issued_at: input.issuedAt,
  };
}

export function buildInvoicePaymentRequest(input: {
  amount: number;
  paymentMethod: string;
  valueDate: string;
  reference: string;
  notes?: string;
}) {
  return {
    amount: input.amount,
    payment_method: input.paymentMethod,
    value_date: new Date(input.valueDate).toISOString(),
    reference: input.reference || null,
    notes: input.notes?.trim() || null,
  };
}
