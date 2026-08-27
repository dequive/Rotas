import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/drivers-api", () => ({
  loadDriverScorecard: vi.fn().mockResolvedValue({
    driver_id: "driver-1",
    score: null,
    tier: "insuficiente",
    period_days: 30,
    completed_trips: 0,
    message: "Mínimo 3 viagens em 30 dias para score válido",
    metrics: {},
  }),
}));

import { DriverScorecardPanel } from "../components/DriverScorecardPanel";

describe("DriverScorecardPanel", () => {
  it("não lê métricas ausentes quando os dados são insuficientes", async () => {
    render(
      <DriverScorecardPanel
        drivers={[{ id: "driver-1", full_name: "Motorista E2E" }]}
      />,
    );

    expect(
      await screen.findByText("Mínimo 3 viagens em 30 dias para score válido"),
    ).toBeDefined();
    expect(screen.queryByText("Proof de entrega")).toBeNull();
    expect(screen.getByText("Dados insuficientes")).toBeDefined();
  });
});
