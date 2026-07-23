import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkOrderDetail, WorkOrderProfitability } from "../lib/workshop-api";
import { WorkOrderDetailClient } from "../oficina/components/WorkOrderDetailClient";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("../oficina/ordens-servico/[id]/actions", () => ({
  addLaborSession: vi.fn(),
  issuePart: vi.fn(),
  retryBilling: vi.fn(),
  returnPart: vi.fn(),
  transitionWorkOrder: vi.fn(),
}));

const detail: WorkOrderDetail = {
  work_order: {
    id: "wo-1",
    work_order_number: "OS-2026-0042",
    status: "in_progress",
    diagnosis: "Filtro saturado",
    planned_work: "Substituir filtro",
    estimated_cost: 3000,
    actual_cost: null,
    origin_type: "quote",
    billing_status: "not_required",
    billing_error: null,
    document_id: null,
    invoice_number: null,
    invoice_status: null,
    quality_notes: null,
    created_at: "2026-07-23T08:00:00Z",
    updated_at: "2026-07-23T08:00:00Z",
  },
  vehicle: {
    id: "vehicle-1",
    plate: "ABC-12-34",
    brand: "Toyota",
    model: "Hilux",
    current_km: 72000,
    odometer_at_reception: 71980,
  },
  client: {
    id: "client-1",
    trading_name: "Cliente Maputo",
    legal_name: null,
    client_type: "organization",
    nuit: null,
    is_fleet_owned: false,
  },
  reception: null,
  quote: null,
  tasks: [
    {
      id: "task-1",
      description: "Substituir filtro",
      status: "in_progress",
      assigned_to: "user-1",
      assigned_mechanic_name: "Mecânico Um",
      estimated_minutes: 60,
      actual_minutes: 30,
      labor_sessions: [],
    },
  ],
  parts_issued: [
    {
      inventory_id: "part-1",
      sku: "FLT-001",
      name: "Filtro de óleo",
      unit: "unit",
      issued_quantity: 2,
      returned_quantity: 1,
      net_quantity: 1,
      net_cost: 500,
    },
  ],
  unreturned_tools: [],
  blockers: { incomplete_tasks: 1, unreturned_tools: 0 },
};

const profitability: WorkOrderProfitability = {
  work_order_id: "wo-1",
  work_order_number: "OS-2026-0042",
  total_revenue: 3000,
  total_labor_minutes: 30,
  total_labor_cost: 400,
  total_parts_cost: 500,
  total_cost: 900,
  gross_profit_mzn: 2100,
  gross_profit_margin_percent: 70,
  is_profitable: true,
};

describe("WorkOrderDetailClient", () => {
  it("mostra operação, consumo líquido e rentabilidade real", () => {
    render(
      <WorkOrderDetailClient
        detail={detail}
        profitability={profitability}
        role="manager"
        userId="user-1"
      />,
    );

    expect(screen.getByText("OS-2026-0042")).toBeDefined();
    expect(screen.getByText("Substituir filtro")).toBeDefined();
    expect(screen.getByText(/1 tarefa\(s\) incompleta\(s\)/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Peças" }));
    expect(screen.getByText("FLT-001")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("1 unit")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Rentabilidade" }));
    expect(screen.getByText("Margem bruta")).toBeDefined();
    expect(
      screen.getByText((_, element) => element?.textContent === "2100,00 MT"),
    ).toBeDefined();
  });
});
