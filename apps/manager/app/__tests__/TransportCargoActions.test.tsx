import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  bffRequest: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: state.refresh }),
}));

vi.mock("../lib/bff", () => ({
  bffRequest: state.bffRequest,
}));

import { TransportCargoActions } from "../components/TransportCargoActions";

describe("TransportCargoActions dispatch approval", () => {
  beforeEach(() => {
    state.bffRequest.mockReset();
    state.refresh.mockReset();
    state.bffRequest.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ clearance_status: "approved" }),
    });
  });

  it("requires explicit attestation of every dispatch check", async () => {
    render(
      <TransportCargoActions
        action={{ kind: "approve-dispatch-clearance", tripId: "trip-1" }}
        apiConfig={{ tenantId: "tenant-1" }}
        label="Aprovar saída"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Aprovar saída" }));
    expect(state.bffRequest).not.toHaveBeenCalled();

    const checks = [
      "Viatura verificada",
      "Motorista verificado",
      "Documentos verificados",
      "Load permit verificado",
      "Carga verificada",
      "Adiantamento de combustível verificado",
      "Risco da rota verificado",
    ];
    for (const label of checks) {
      fireEvent.click(screen.getByRole("checkbox", { name: label }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Confirmar aprovação" }));

    await waitFor(() => {
      expect(state.bffRequest).toHaveBeenCalledWith(
        "/api/v1/trips/trip-1/dispatch-clearance/approve",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            vehicle_checked: true,
            driver_checked: true,
            documents_checked: true,
            load_permit_checked: true,
            cargo_checked: true,
            fuel_advance_checked: true,
            route_risk_checked: true,
          }),
        }),
      );
    });
    expect(state.refresh).toHaveBeenCalledOnce();
  });

  it("uses a new idempotency key when a blocked clearance is re-evaluated", async () => {
    render(
      <TransportCargoActions
        action={{ kind: "approve-dispatch-clearance", tripId: "trip-1" }}
        apiConfig={{ tenantId: "tenant-1" }}
        label="Reavaliar saída"
      />,
    );

    for (let attempt = 0; attempt < 2; attempt += 1) {
      fireEvent.click(screen.getByRole("button", { name: "Reavaliar saída" }));
      for (const checkbox of screen.getAllByRole("checkbox")) {
        fireEvent.click(checkbox);
      }
      fireEvent.click(screen.getByRole("button", { name: "Confirmar aprovação" }));
      await waitFor(() => expect(state.bffRequest).toHaveBeenCalledTimes(attempt + 1));
    }

    const firstHeaders = new Headers(state.bffRequest.mock.calls[0]?.[1]?.headers);
    const secondHeaders = new Headers(state.bffRequest.mock.calls[1]?.[1]?.headers);
    expect(firstHeaders.get("Idempotency-Key")).toBeTruthy();
    expect(secondHeaders.get("Idempotency-Key")).toBeTruthy();
    expect(secondHeaders.get("Idempotency-Key")).not.toBe(
      firstHeaders.get("Idempotency-Key"),
    );
  });
});
