import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { bffRequest } from "../lib/bff";
import type { WorkshopQuote } from "../lib/workshop-api";
import { QuoteMasterDetailClient } from "../oficina/components/QuoteMasterDetailClient";

vi.mock("../lib/bff", () => ({
  bffRequest: vi.fn(),
}));

const convertedQuote: WorkshopQuote = {
  id: "quote-1",
  quote_number: "ORC-2026-0042",
  vehicle_id: "vehicle-1",
  client_id: "client-1",
  reception_id: "reception-1",
  related_work_order_id: "work-order-1",
  status: "converted",
  is_supplemental: false,
  valid_until: null,
  labor_total: 10_000,
  parts_total: 2_000,
  tax_total: 1_920,
  total_amount: 13_920,
  notes: "Revisão autorizada",
  acceptance_channel: "whatsapp",
  accepted_by_person_name: "Maria Santos",
  created_at: "2026-07-26T08:00:00Z",
  items: [
    {
      id: "item-1",
      item_type: "labor",
      description: "Revisão geral",
      quantity: 1,
      unit_price: 10_000,
      warranty_months: 3,
      warranty_km: 5_000,
    },
  ],
};

describe("QuoteMasterDetailClient", () => {
  beforeEach(() => {
    vi.mocked(bffRequest).mockReset();
  });

  it("carrega o detalhe real e mantém orçamento convertido imutável", async () => {
    vi.mocked(bffRequest).mockResolvedValue(
      new Response(JSON.stringify(convertedQuote), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(
      <QuoteMasterDetailClient
        initialQuotes={[{ ...convertedQuote, items: [] }]}
        vehicleOptions={[
          {
            id: "vehicle-1",
            plate: "ABC-12-34",
            brand: "Toyota",
            model: "Hilux",
          },
        ]}
      />,
    );

    await waitFor(() => {
      expect(bffRequest).toHaveBeenCalledWith(
        "/api/v1/workshop/quotes/quote-1",
      );
    });

    expect(await screen.findByText("Documento imutável")).toBeInTheDocument();
    expect(screen.getByText("Revisão geral")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /criar suplemento/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /aprovar e gerar os/i }),
    ).not.toBeInTheDocument();
  });

  it("aplica pesquisa local sem inventar resultados", () => {
    vi.mocked(bffRequest).mockResolvedValue(
      new Response(JSON.stringify(convertedQuote), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const secondQuote: WorkshopQuote = {
      ...convertedQuote,
      id: "quote-2",
      quote_number: "ORC-2026-0099",
      vehicle_id: "vehicle-2",
      related_work_order_id: "work-order-2",
    };

    render(
      <QuoteMasterDetailClient
        initialQuotes={[
          { ...convertedQuote, items: [] },
          { ...secondQuote, items: [] },
        ]}
        vehicleOptions={[
          { id: "vehicle-1", plate: "ABC-12-34" },
          { id: "vehicle-2", plate: "XYZ-98-76" },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Pesquisar orçamentos"), {
      target: { value: "XYZ-98-76" },
    });

    expect(screen.getByText("ORC-2026-0099")).toBeInTheDocument();
    expect(screen.queryByText("ORC-2026-0042")).not.toBeInTheDocument();
  });
});
