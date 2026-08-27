import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TripOrder } from "../lib/trip-orders-api";

const state = vi.hoisted(() => ({
  assignTripOrder: vi.fn(),
  confirmTripOrder: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: state.refresh }),
}));

vi.mock("../lib/trip-orders-client", () => ({
  assignTripOrder: state.assignTripOrder,
  confirmTripOrder: state.confirmTripOrder,
}));

import { DispatchBoard } from "../components/DispatchBoard";

const draftOrder: TripOrder = {
  id: "order-1",
  tenant_id: "tenant-1",
  contract_id: "contract-1",
  client_id: "client-1",
  customer_reference: "PO-778",
  origin: "Maputo",
  destination: "Beira",
  cargo_type: "Carga geral",
  estimated_weight: 1200,
  status: "draft",
  requested_pickup_date: "2026-08-21",
  created_at: "2026-08-20T12:00:00Z",
};

describe("DispatchBoard", () => {
  beforeEach(() => {
    state.confirmTripOrder.mockReset();
    state.confirmTripOrder.mockResolvedValue({ ...draftOrder, status: "confirmed" });
    state.refresh.mockReset();
  });

  it("lets an operator confirm a draft before assigning resources", async () => {
    render(<DispatchBoard pendingOrders={[draftOrder]} vehicles={[]} drivers={[]} />);

    fireEvent.click(screen.getByRole("button", { name: "Confirmar ordem" }));

    await waitFor(() => {
      expect(state.confirmTripOrder).toHaveBeenCalledWith("order-1", {
        reason: "Confirmada no quadro de despacho",
      });
    });
    expect(state.refresh).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: /atribuir motorista/i })).not.toBeInTheDocument();
  });
});
