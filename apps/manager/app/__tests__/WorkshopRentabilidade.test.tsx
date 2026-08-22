import { describe, it, expect, vi } from "vitest";

vi.mock("../lib/auth", () => ({
  requireSession: vi.fn().mockResolvedValue({
    accessToken: "mock-token",
    tenantId: "tenant-123",
    role: "admin",
  }),
}));

import { getWorkshopProfitabilitySummary } from "../lib/workshop-api";

describe("Workshop Profitability API Helper", () => {
  it("fetches and parses workshop profitability summary successfully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          summary: {
            confirmed_revenue: 12000,
            projected_revenue: 5000,
            total_labor_cost: 3000,
            total_parts_cost: 2000,
            total_cost: 5000,
            confirmed_gross_profit: 7000,
            confirmed_gross_margin_pct: 58.33,
            negative_margin_count: 0,
            total_work_orders: 1,
          },
          work_orders: [
            {
              work_order_id: "wo-1",
              work_order_number: "OS-2026-0001",
              status: "closed",
              created_at: "2026-07-23T10:00:00Z",
              client_name: "Cliente Teste Lda",
              vehicle_name: "Volvo FH (ABC-123)",
              confirmed_revenue: 12000,
              projected_revenue: 0,
              effective_revenue: 12000,
              total_labor_cost: 3000,
              total_parts_cost: 2000,
              total_cost: 5000,
              margin_mzn: 7000,
              margin_pct: 58.33,
              is_profitable: true,
            },
          ],
        }),
      })
    );

    const result = await getWorkshopProfitabilitySummary({ status: "closed" });

    expect(result).not.toBeNull();
    expect(result?.summary.confirmed_revenue).toBe(12000);
    expect(result?.summary.projected_revenue).toBe(5000);
    expect(result?.summary.confirmed_gross_profit).toBe(7000);
    expect(result?.work_orders).toHaveLength(1);
    expect(result?.work_orders[0].work_order_number).toBe("OS-2026-0001");
    expect(result?.work_orders[0].is_profitable).toBe(true);
  });

  it("handles fetch errors gracefully returning null", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network Error"))
    );

    const result = await getWorkshopProfitabilitySummary();
    expect(result).toBeNull();
  });
});
