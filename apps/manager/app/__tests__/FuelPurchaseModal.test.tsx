import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FuelPurchaseModal } from "../components/FuelPurchaseModal";

describe("FuelPurchaseModal", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 201 })));
    vi.stubGlobal("crypto", { randomUUID: () => "fuel-idempotency-key" });
  });

  it("submits the canonical fuel purchase contract through the Manager BFF", async () => {
    render(<FuelPurchaseModal onSuccess={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /registar compra/i }));
    fireEvent.change(screen.getByLabelText(/fornecedor/i), {
      target: { value: "Petromoc" },
    });
    fireEvent.change(screen.getByLabelText(/referência da compra/i), {
      target: { value: "OC-2026-001" },
    });
    fireEvent.change(screen.getByLabelText(/litros encomendados/i), {
      target: { value: "1000" },
    });
    fireEvent.change(screen.getByLabelText(/preço unitário/i), {
      target: { value: "85.50" },
    });
    fireEvent.change(screen.getByLabelText(/data da encomenda/i), {
      target: { value: "2026-08-20T10:30" },
    });
    const dialog = screen.getByRole("dialog");
    fireEvent.submit(within(dialog).getByRole("button", { name: /registar compra/i }).closest("form")!);

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/fuel-purchases");
    expect(init?.headers).toEqual({
      "Content-Type": "application/json",
      "Idempotency-Key": "fuel-idempotency-key",
    });
    expect(JSON.parse(String(init?.body))).toEqual({
      supplier_name: "Petromoc",
      purchase_reference: "OC-2026-001",
      fuel_type: "gasoleo",
      ordered_liters: 1000,
      unit_price: 85.5,
      ordered_at: "2026-08-20T08:30:00.000Z",
      notes: null,
    });
  });
});
