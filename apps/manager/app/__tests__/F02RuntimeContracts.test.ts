import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  apiFetch: apiFetchMock,
}));

import { loadClients } from "../lib/clients-api";
import { loadContracts } from "../lib/contracts-api";
import { loadControlTower } from "../lib/control-tower-api";
import {
  assignTripOrder,
  confirmTripOrder,
  createTripOrder,
  loadPendingTripOrders,
} from "../lib/trip-orders-api";
import { closeTrip, loadTrips, startTrip } from "../lib/trips-api";

describe("F-02 runtime contracts", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue([]);
  });

  it("does not serve stale operational lists after a successful mutation", async () => {
    await loadClients();
    await loadContracts();
    await loadPendingTripOrders();
    await loadTrips();

    expect(apiFetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/clients?limit=200",
      { revalidate: 0 },
    );
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/contracts/?limit=200",
      { revalidate: 0 },
    );
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/trip-orders?status=draft&limit=50",
      { revalidate: 0 },
    );
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      4,
      "/api/v1/trip-orders?status=confirmed&limit=50",
      { revalidate: 0 },
    );
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/v1/trip-orders?status=planning&limit=50",
      { revalidate: 0 },
    );
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      6,
      "/api/v1/trips?limit=200",
      { revalidate: 0 },
    );
  });

  it("does not cache the dispatch authorization queue across mutations", async () => {
    apiFetchMock.mockResolvedValue({
      date: "2026-08-21",
      summary: {
        trip_orders_open: 0,
        dispatch_pending: 0,
        dispatch_blocked: 0,
        trips_in_execution: 0,
        incidents_open: 0,
        delivery_proofs_pending_validation: 0,
        billing_ready: 0,
        active_waivers: 0,
        operational_exceptions_open: 0,
        vehicle_documents_expiring: 0,
        driver_documents_expiring: 0,
        vehicles_active: 0,
        drivers_active: 0,
        trips_created_today: 0,
        costs_reconciled_trips: 0,
        transport_cost_total: 0,
        contract_revenue_total: 0,
        margin_total: 0,
        negative_margin_trips: 0,
        closed_trips_unreconciled: 0,
      },
      queues: {
        blocked_dispatch: [],
        open_incidents: [],
        pending_delivery_validation: [],
        operational_exceptions: [],
        vehicle_documents_expiring: [],
        driver_documents_expiring: [],
      },
    });

    await loadControlTower();

    expect(apiFetchMock).toHaveBeenCalledWith("/api/v1/control-tower", {
      revalidate: 0,
    });
  });

  it("sends the assignment field names required by the backend contract", async () => {
    apiFetchMock.mockResolvedValue({ trip_order: {}, trip: {} });

    await assignTripOrder("order-1", "vehicle-1", "driver-1");

    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/v1/trip-orders/order-1/assign",
      {
        method: "POST",
        body: JSON.stringify({
          vehicle_id: "vehicle-1",
          driver_id: "driver-1",
        }),
      },
    );
  });

  it("creates and confirms a trip order through the documented endpoints", async () => {
    const payload = {
      cargo_risk_level: "normal",
      client_id: "client-1",
      contract_id: "contract-1",
      destination: "Beira",
      origin: "Maputo",
      priority: "normal",
      requested_pickup_date: "2026-08-21",
      requires_customs_clearance: false,
      requires_load_permit: true,
      requires_police_clearance: false,
      source: "manual",
    };
    apiFetchMock
      .mockResolvedValueOnce({ id: "order-1", status: "draft" })
      .mockResolvedValueOnce({ id: "order-1", status: "confirmed" });

    await createTripOrder(payload);
    await confirmTripOrder("order-1", { reason: "Pedido validado" });

    expect(apiFetchMock).toHaveBeenNthCalledWith(1, "/api/v1/trip-orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    expect(apiFetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/trip-orders/order-1/confirm",
      {
        method: "POST",
        body: JSON.stringify({ reason: "Pedido validado" }),
      },
    );
  });

  it("sends the odometer required to start a trip", async () => {
    apiFetchMock.mockResolvedValue({});

    await startTrip("trip-1", {
      km_start: 12345,
      override_missing_load_permit: false,
    });

    expect(apiFetchMock).toHaveBeenCalledWith("/api/v1/trips/trip-1/start", {
      method: "POST",
      body: JSON.stringify({
        km_start: 12345,
        override_missing_load_permit: false,
      }),
    });
  });

  it("uses the operational-close payload accepted by the backend", async () => {
    apiFetchMock.mockResolvedValue({});

    await closeTrip("trip-1", { notes: "POD validado" });

    expect(apiFetchMock).toHaveBeenCalledWith("/api/v1/trips/trip-1/close", {
      method: "POST",
      body: JSON.stringify({ notes: "POD validado" }),
    });
  });
});
