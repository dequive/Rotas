import { HttpContractError } from "@rotas/http-contract";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  listDriverAdvanceRecords,
  listDriverChecklistRecords,
  listDriverExpenseRecords,
  listDriverFuelRecords,
} from "../api";
import {
  getCurrentIdentityScope,
  getDriverReadCache,
  saveDriverReadCache,
} from "../db";
import { RecordsView } from "../views/RecordsView";

vi.mock("../api", () => ({
  listDriverChecklistRecords: vi.fn(),
  listDriverFuelRecords: vi.fn(),
  listDriverExpenseRecords: vi.fn(),
  listDriverAdvanceRecords: vi.fn(),
}));

vi.mock("../db", () => ({
  getCurrentIdentityScope: vi.fn(() => ({
    tenantId: "tenant-1",
    driverId: "driver-1",
    sessionId: "session-1",
  })),
  getDriverReadCache: vi.fn(),
  saveDriverReadCache: vi.fn(),
}));

const emptyPage = { items: [], total: 0, limit: 20, offset: 0 };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(getCurrentIdentityScope).mockReturnValue({
    tenantId: "tenant-1",
    driverId: "driver-1",
    sessionId: "session-1",
  });
  vi.mocked(getDriverReadCache).mockResolvedValue(undefined);
  vi.mocked(saveDriverReadCache).mockResolvedValue(undefined);
});

describe("Diário operacional do motorista", () => {
  it("mostra os quatro tipos sem códigos internos e preserva ajustes", async () => {
    vi.mocked(listDriverChecklistRecords).mockResolvedValue({
      ...emptyPage,
      items: [{
        id: "check-1", trip_id: "trip-1", vehicle_id: "vehicle-1",
        checklist_type: "pre_trip", status: "completed",
        started_at: "2026-08-24T06:50:00Z", completed_at: "2026-08-24T07:00:00Z",
        created_at: "2026-08-24T06:50:00Z",
      }],
      total: 1,
    });
    vi.mocked(listDriverFuelRecords).mockResolvedValue({
      ...emptyPage,
      items: [{
        id: "fuel-1", trip_id: "trip-1", vehicle_id: "vehicle-1",
        fuel_date: "2026-08-24T08:00:00Z", station_name: "Posto Maputo",
        fuel_type: "diesel", liters: "80.00", total_cost: "7200.00",
        km_at_refuel: 45210, has_receipt: true, is_verified: true,
        is_flagged: false, created_at: "2026-08-24T08:00:00Z",
      }],
      total: 1,
    });
    vi.mocked(listDriverExpenseRecords).mockResolvedValue({
      ...emptyPage,
      items: [{
        id: "expense-1", trip_id: "trip-1", expense_type: "toll",
        description: "Portagem", amount: "-250.00", currency: "MZN",
        payment_method: "cash", has_receipt: true, entry_type: "adjustment",
        corrects_id: "expense-original", correction_reason: "Valor corrigido",
        recorded_by_type: "manager", incurred_at: "2026-08-24T09:00:00Z",
        created_at: "2026-08-24T09:00:00Z",
      }],
      total: 1,
    });
    vi.mocked(listDriverAdvanceRecords).mockResolvedValue({
      ...emptyPage,
      items: [{
        id: "advance-1", trip_id: "trip-1", total_amount: "3000.00",
        allowance_amount: "3000.00", expense_amount: "0.00", currency: "MZN",
        status: "issued", issued_at: "2026-08-24T06:00:00Z",
      }],
      total: 1,
    });

    render(<RecordsView />);

    expect(await screen.findByText("Checklist antes da viagem")).toBeTruthy();
    expect(screen.getByText("80,00 L")).toBeTruthy();
    expect(screen.getByText("Ajuste de despesa")).toBeTruthy();
    expect(screen.getByText("-250,00 MZN")).toBeTruthy();
    expect(screen.getByText("Despacho de viagem")).toBeTruthy();
    expect(screen.queryByText(/pre_trip|completed|adjustment|issued/)).toBeNull();
  });

  it("recupera dados guardados somente para a identidade atual e sinaliza degradação", async () => {
    vi.mocked(listDriverChecklistRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(listDriverFuelRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(listDriverExpenseRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(listDriverAdvanceRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(getDriverReadCache).mockResolvedValue({
      id: "tenant-1:driver-1:session-1:records:all:all:0",
      key: "records:all:all:0",
      tenantId: "tenant-1",
      driverId: "driver-1",
      sessionId: "session-1",
      cachedAt: "2026-08-24T10:00:00Z",
      data: {
        items: [{
          kind: "advance",
          record: {
            id: "advance-1", trip_id: "trip-1", total_amount: "3000.00",
            allowance_amount: "3000.00", expense_amount: "0.00", currency: "MZN",
            status: "issued", issued_at: "2026-08-24T06:00:00Z",
          },
        }],
        total: 1,
      },
    });

    render(<RecordsView />);

    expect(await screen.findByText("Despacho de viagem")).toBeTruthy();
    expect(screen.getByText(/dados guardados.*somente leitura/i)).toBeTruthy();
    expect(getDriverReadCache).toHaveBeenCalledWith(
      expect.objectContaining({ driverId: "driver-1", sessionId: "session-1" }),
      "records:all:all:0",
    );
  });

  it("distingue vazio, indisponível e sem permissão", async () => {
    vi.mocked(listDriverChecklistRecords).mockResolvedValue(emptyPage);
    vi.mocked(listDriverFuelRecords).mockResolvedValue(emptyPage);
    vi.mocked(listDriverExpenseRecords).mockResolvedValue(emptyPage);
    vi.mocked(listDriverAdvanceRecords).mockResolvedValue(emptyPage);

    const { rerender } = render(<RecordsView />);
    expect(await screen.findByText("Ainda não há registos")).toBeTruthy();

    vi.mocked(listDriverChecklistRecords).mockRejectedValue(
      new HttpContractError("Sem permissão", 403, "forbidden"),
    );
    vi.mocked(listDriverFuelRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(listDriverExpenseRecords).mockRejectedValue(new Error("offline"));
    vi.mocked(listDriverAdvanceRecords).mockRejectedValue(new Error("offline"));
    rerender(<RecordsView refreshToken={1} />);
    expect(await screen.findByText("Sem permissão para consultar registos")).toBeTruthy();

    vi.mocked(listDriverChecklistRecords).mockRejectedValue(new Error("offline"));
    rerender(<RecordsView refreshToken={2} />);
    expect(await screen.findByText("Não foi possível carregar os registos")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
  });
});
