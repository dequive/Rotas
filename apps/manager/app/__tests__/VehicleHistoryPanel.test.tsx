import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import VehicleHistoryPanel from "../oficina/components/VehicleHistoryPanel";

describe("VehicleHistoryPanel Component", () => {
  it("renders empty state instruction when no vehicleId is selected", () => {
    render(<VehicleHistoryPanel vehicleId={null} />);
    expect(screen.getByText(/Selecione uma viatura para visualizar o histórico/i)).toBeDefined();
  });

  it("renders populated vehicle history tabs, active warranty badge, and reception records", async () => {
    // Mock global fetch returning populated vehicle history
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          vehicle_id: "veh-123",
          plate: "AFM-8821-TR",
          current_odometer_km: 52000,
          receptions: [
            {
              id: "rec-1",
              reception_number: "REC-2026-0004",
              received_at: "2026-06-01T10:00:00Z",
              odometer_at_reception: 50000,
              reported_issues: "Revisão geral e pastilhas",
              status: "delivered",
            },
          ],
          work_orders: [
            {
              id: "wo-1",
              work_order_number: "OS-2026-0012",
              status: "closed",
              created_at: "2026-06-01T12:00:00Z",
              total_labor_minutes: 120,
              actual_cost: 15000,
            },
          ],
          parts_used: [
            {
              id: "part-1",
              part_name: "Filtro de Óleo 1.6 DCI",
              quantity: 1,
              unit_cost: 1500,
              created_at: "2026-06-01T12:00:00Z",
            },
          ],
          warranties: [
            {
              id: "war-1",
              warranty_type: "parts",
              title: "Garantia (parts)",
              expires_at: "2026-12-01T10:00:00Z",
              status: "active",
              notes: "Garantia de 6 meses",
            },
          ],
        }),
      }),
    );

    render(<VehicleHistoryPanel vehicleId="veh-123" />);

    await waitFor(() => {
      expect(screen.getByText("AFM-8821-TR")).toBeDefined();
      expect(screen.getByText("52000 km")).toBeDefined();
      expect(screen.getByText(/🛡️ Garantia Ativa/i)).toBeDefined();
      expect(screen.getByText("REC-2026-0004")).toBeDefined();
    });

    vi.unstubAllGlobals();
  });

  it("renders empty history state without crashing when vehicle has zero interventions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          vehicle_id: "veh-brand-new",
          plate: "NEW-000",
          current_odometer_km: 100,
          receptions: [],
          work_orders: [],
          parts_used: [],
          warranties: [],
        }),
      }),
    );

    render(<VehicleHistoryPanel vehicleId="veh-brand-new" />);

    await waitFor(() => {
      expect(screen.getByText("NEW-000")).toBeDefined();
      expect(screen.getByText(/Primeira entrada desta viatura na oficina/i)).toBeDefined();
    });

    vi.unstubAllGlobals();
  });

  it("shows unavailable state and never fabricates history when API fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("history-offline")));

    render(<VehicleHistoryPanel vehicleId="veh-real" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Serviço indisponível");
    expect(screen.queryByText("AFM-8821-TR")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
