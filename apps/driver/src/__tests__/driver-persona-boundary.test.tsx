import "fake-indexeddb/auto";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { db } from "../db";

vi.mock("../hooks/useNetworkStatus", () => ({
  useNetworkStatus: () => ({ isOnline: false }),
}));

vi.mock("../hooks/useSyncStatus", () => ({
  useSyncStatus: () => ({
    bannerState: "offline",
    pendingCount: 0,
    errorCount: 0,
    workboxInstance: null,
  }),
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    getAuth: () => ({
      accessToken: "token",
      tenantId: "tenant-1",
      driverId: "driver-1",
      deviceId: "device-1",
      driverName: "Motorista Teste",
      sessionId: "session-1",
    }),
    bootstrap: vi.fn().mockResolvedValue({
      profile: {
        tenant_id: "tenant-1",
        driver_id: "driver-1",
        device_id: "device-1",
      },
      checklistTemplates: [],
      activeTrip: {
        id: "trip-1",
        origin: "Maputo",
        destination: "Matola",
        status: "dispatched",
        load_state: "loaded_empty",
        vehicle_id: "vehicle-1",
        vehicle_plate: "ABC-12-34",
      },
      vehicles: [],
    }),
  };
});

describe("fronteira da persona Motorista", () => {
  beforeEach(async () => {
    localStorage.setItem("rotas_tenant_id", "tenant-1");
    localStorage.setItem("rotas_driver_id", "driver-1");
    localStorage.setItem("rotas_session_id", "session-1");
    await db.syncQueue.clear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("mostra a viagem atribuída sem ações administrativas ou cobrança", async () => {
    render(<App />);

    expect(await screen.findByText("Maputo → Matola")).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /Nova viagem/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Load Permit/i })).toBeNull();
      expect(screen.queryByRole("button", { name: /Manifesto/i })).toBeNull();
      expect(screen.queryByText(/Estado de cobrança/i)).toBeNull();
    });
  });

  it("não manda o motorista criar uma viagem quando nenhuma foi atribuída", async () => {
    const { bootstrap } = await import("../api");
    vi.mocked(bootstrap).mockResolvedValueOnce({
      profile: {
        tenant_id: "tenant-1",
        driver_id: "driver-1",
        device_id: "device-1",
      },
      checklistTemplates: [],
      activeTrip: null,
      vehicles: [],
    });

    render(<App />);

    expect(await screen.findByText("Sem viagem atribuída")).toBeTruthy();
    expect(screen.getByText(/As novas viagens são atribuídas pelo gestor/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Nova viagem/i })).toBeNull();
  });
});
