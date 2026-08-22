import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  apiFetch: apiFetchMock,
}));

import { loadBillingDocuments } from "../lib/billing-api";

describe("billing API response contracts", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

  it("unwraps the paginated billing document response", async () => {
    apiFetchMock.mockResolvedValue({
      items: [
        {
          id: "document-1",
          contract_reference: "CTR-001",
          client_name: "Cliente Maputo",
          client_id: "client-1",
          billing_period_start: "2026-07-01T00:00:00Z",
          billing_period_end: "2026-08-01T00:00:00Z",
          total_amount: "12500.00",
          status: "issued",
          item_count: 3,
          invoice_number: "FT 2026/0001",
        },
      ],
      total: 1,
    });

    await expect(loadBillingDocuments()).resolves.toEqual([
      {
        id: "document-1",
        reference: "BIL-CTR-001-document",
        invoiceNumber: "FT 2026/0001",
        client: "Cliente Maputo",
        clientId: "client-1",
        period: "julho de 2026",
        trips: 3,
        amount: 12500,
        status: "Emitido",
      },
    ]);
    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/billing/documents?limit=20",
      { revalidate: 15 },
    );
  });
});
