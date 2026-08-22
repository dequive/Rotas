import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Contract } from "../lib/contracts-api";

const state = vi.hoisted(() => ({
  createTripOrder: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: state.refresh }),
}));

vi.mock("../lib/trip-orders-client", () => ({
  createTripOrder: state.createTripOrder,
}));

import { TripOrderFormModal } from "../components/TripOrderFormModal";

const contracts: Contract[] = [
  {
    id: "contract-1",
    client_id: "client-1",
    client_name: "Cliente Comercial",
    contract_reference: "CTR-001",
    title: "Transporte nacional",
    status: "active",
    service_type: "cargo_transport",
    billing_cycle: "per_trip",
    billing_basis: "trip",
    currency: "MZN",
    default_unit_price: 1000,
    requires_load_permit: true,
    requires_delivery_proof: true,
    starts_at: null,
    ends_at: null,
  },
];

describe("TripOrderFormModal", () => {
  beforeEach(() => {
    state.createTripOrder.mockReset();
    state.createTripOrder.mockResolvedValue({ id: "order-1", status: "draft" });
    state.refresh.mockReset();
  });

  it("creates a draft order linked to the selected client contract", async () => {
    render(<TripOrderFormModal contracts={contracts} />);

    fireEvent.click(screen.getByRole("button", { name: /nova ordem/i }));
    fireEvent.change(screen.getByLabelText("Contrato"), {
      target: { value: "contract-1" },
    });
    fireEvent.change(screen.getByLabelText("Referência do cliente"), {
      target: { value: "PO-778" },
    });
    fireEvent.change(screen.getByLabelText("Origem"), {
      target: { value: "Maputo" },
    });
    fireEvent.change(screen.getByLabelText("Destino"), {
      target: { value: "Beira" },
    });
    fireEvent.change(screen.getByLabelText("Data de recolha"), {
      target: { value: "2026-08-21" },
    });
    fireEvent.change(screen.getByLabelText("Peso estimado (kg)"), {
      target: { value: "1200" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar rascunho" }));

    await waitFor(() => {
      expect(state.createTripOrder).toHaveBeenCalledWith(
        expect.objectContaining({
          client_id: "client-1",
          contract_id: "contract-1",
          customer_reference: "PO-778",
          origin: "Maputo",
          destination: "Beira",
          estimated_weight: 1200,
          requested_pickup_date: "2026-08-21",
          requires_load_permit: true,
          source: "manual",
        }),
      );
    });
    expect(state.refresh).toHaveBeenCalledOnce();
  });
});
