import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Trip } from "../lib/trips-api";

const state = vi.hoisted(() => ({
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: state.refresh }),
}));

import { TripActionButton } from "../components/TripActionButton";

const trip: Trip = {
  id: "trip-1",
  tenant_id: "tenant-1",
  trip_order_id: "order-1",
  contract_id: "contract-1",
  vehicle_id: "vehicle-1",
  driver_id: "driver-1",
  origin: "Maputo",
  destination: "Beira",
  cargo_type: "Carga geral",
  load_state: "full",
  status: "planned",
  billing_status: "not_billable",
  actual_departure: null,
  actual_arrival: null,
  km_start: null,
  km_end: null,
  created_at: "2026-08-21T08:00:00Z",
};

describe("TripActionButton dispatch gate", () => {
  beforeEach(() => {
    state.refresh.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue({}) }),
    );
  });

  it("requests clearance instead of starting a planned trip", async () => {
    render(<TripActionButton trip={trip} />);

    fireEvent.click(screen.getByRole("button", { name: "Solicitar saída" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _action: "request_clearance", id: "trip-1" }),
      });
    });
    expect(screen.queryByRole("button", { name: "Iniciar" })).not.toBeInTheDocument();
  });

  it("requires an odometer reading before starting a dispatched trip", async () => {
    render(<TripActionButton trip={{ ...trip, status: "dispatched" }} />);

    fireEvent.click(screen.getByRole("button", { name: "Iniciar" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Km inicial" }), {
      target: { value: "1250" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar início" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/trips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ _action: "start", id: "trip-1", km_start: 1250 }),
      });
    });
  });
});
