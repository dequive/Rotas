import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getDriverTripDocuments,
  listDriverTripHistory,
  listDriverTrips,
  requestDriverTripDocument,
} from "../api";
import { TripsView } from "../views/TripsView";

vi.mock("../api", () => ({
  listDriverTrips: vi.fn(),
  listDriverTripHistory: vi.fn(),
  getDriverTripDocuments: vi.fn(),
  requestDriverTripDocument: vi.fn(),
  downloadDriverTripDocument: vi.fn(),
}));

const trip = {
  id: "trip-1",
  vehicle_id: "vehicle-1",
  driver_id: "driver-1",
  origin: "Maputo",
  destination: "Matola",
  cargo_type: "cimento",
  cargo_class: null,
  cargo_weight: 1200,
  load_state: "loaded",
  requires_load_permit: true,
  requires_cargo_manifest: true,
  waybill_number: "GT-001",
  km_start: null,
  km_end: null,
  status: "dispatched",
  planned_departure: "2026-08-23T08:00:00Z",
  actual_departure: null,
  planned_arrival: null,
  actual_arrival: null,
  recipient_name: "Cliente",
  cargo_status: null,
  created_at: "2026-08-23T07:00:00Z",
  updated_at: "2026-08-23T07:00:00Z",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Minhas Viagens", () => {
  it("não mostra documentação incompleta quando todos os requisitos existem", async () => {
    vi.mocked(listDriverTrips).mockResolvedValue({
      items: [trip], total: 1, limit: 20, offset: 0,
    });
    vi.mocked(getDriverTripDocuments).mockResolvedValue({
      trip_id: trip.id,
      complete: true,
      can_request: true,
      missing_required: [],
      requirements: [
        { document_type: "load_permit", present: true },
        { document_type: "cargo_manifest", present: true },
      ],
      documents: [
        {
          id: "doc-1", document_type: "load_permit", document_number: "LP-1",
          status: "valid", file_id: null, issued_at: "2026-08-23T07:30:00Z",
        },
        {
          id: "doc-2", document_type: "cargo_manifest", document_number: "MAN-1",
          status: "issued", file_id: null, issued_at: "2026-08-23T07:35:00Z",
        },
      ],
      requests: [],
    });

    render(<TripsView mode="assigned" onBack={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /Maputo para Matola/i }));

    expect(await screen.findByText("Documentação completa")).toBeTruthy();
    expect(screen.queryByText(/Documentação incompleta/i)).toBeNull();
    expect(screen.getAllByText("Load Permit").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Manifesto de carga").length).toBeGreaterThanOrEqual(1);
  });

  it("permite solicitar apenas um requisito realmente em falta", async () => {
    vi.mocked(listDriverTrips).mockResolvedValue({
      items: [trip], total: 1, limit: 20, offset: 0,
    });
    const missingDocuments: Awaited<ReturnType<typeof getDriverTripDocuments>> = {
      trip_id: trip.id,
      complete: false,
      can_request: true,
      missing_required: ["transport_document:guia_de_transporte"],
      requirements: [
        { document_type: "transport_document:guia_de_transporte", present: false },
      ],
      documents: [],
      requests: [],
    };
    vi.mocked(getDriverTripDocuments)
      .mockResolvedValueOnce(missingDocuments)
      .mockResolvedValueOnce({
        ...missingDocuments,
        requests: [{
          id: "request-1", trip_id: trip.id,
          document_type: "transport_document:guia_de_transporte",
          status: "open", note: null, created_at: "2026-08-23T08:00:00Z",
        }],
      });
    vi.mocked(requestDriverTripDocument).mockResolvedValue({
      id: "request-1", trip_id: trip.id,
      document_type: "transport_document:guia_de_transporte",
      status: "open", note: null, created_at: "2026-08-23T08:00:00Z",
    });

    render(<TripsView mode="assigned" onBack={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /Maputo para Matola/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Solicitar Guia de transporte/i }));

    await waitFor(() => {
      expect(requestDriverTripDocument).toHaveBeenCalledWith(
        trip.id,
        "transport_document:guia_de_transporte",
      );
    });
    expect(await screen.findByText("Pedido enviado")).toBeTruthy();
  });

  it("apresenta viagem concluída no histórico como somente leitura", async () => {
    vi.mocked(listDriverTripHistory).mockResolvedValue({
      items: [{ ...trip, status: "closed" }], total: 1, limit: 20, offset: 0,
    });
    vi.mocked(getDriverTripDocuments).mockResolvedValue({
      trip_id: trip.id,
      complete: false,
      can_request: false,
      missing_required: ["load_permit"],
      requirements: [{ document_type: "load_permit", present: false }],
      documents: [],
      requests: [],
    });

    render(<TripsView mode="history" onBack={() => undefined} />);
    fireEvent.click(await screen.findByRole("button", { name: /Maputo para Matola/i }));

    expect(await screen.findByText(/Viagem fechada — somente leitura/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Solicitar/i })).toBeNull();
  });
});
