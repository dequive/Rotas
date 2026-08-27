import { describe, expect, it } from "vitest";
import {
  buildInvoicePaymentRequest,
  buildJournalEntryRequest,
  buildPurchaseOrderRequest,
} from "../lib/finance-contracts";

describe("finance API contracts", () => {
  it("builds the canonical accounting journal-entry payload", () => {
    expect(
      buildJournalEntryRequest({
        journalType: "OD",
        date: "2026-08-20",
        reference: "DOC-1",
        description: "Ajuste",
        lines: [{ account_id: "account-1", debit: 100, credit: 0 }],
      }),
    ).toEqual({
      journal_type: "OD",
      date: "2026-08-20T00:00:00.000Z",
      reference: "DOC-1",
      description: "Ajuste",
      lines: [{ account_id: "account-1", debit: 100, credit: 0 }],
    });
  });

  it("builds the canonical purchase-order payload", () => {
    expect(
      buildPurchaseOrderRequest({
        thirdPartyId: "supplier-1",
        orderNumber: "PO-1",
        description: "Pneus",
        estimatedAmount: 2500,
        issuedAt: "2026-08-20T10:00:00.000Z",
      }),
    ).toEqual({
      third_party_id: "supplier-1",
      po_number: "PO-1",
      description: "Pneus",
      estimated_amount: 2500,
      currency: "MZN",
      issued_at: "2026-08-20T10:00:00.000Z",
    });
  });

  it("uses the atomic invoice-payment payload", () => {
    expect(
      buildInvoicePaymentRequest({
        amount: 500,
        paymentMethod: "bank_transfer",
        valueDate: "2026-08-20",
        reference: "TRF-1",
      }),
    ).toEqual({
      amount: 500,
      payment_method: "bank_transfer",
      value_date: "2026-08-20T00:00:00.000Z",
      reference: "TRF-1",
      notes: null,
    });
  });
});
