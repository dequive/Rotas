import "fake-indexeddb/auto";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SyncIssuesPanel } from "../components/SyncIssuesPanel";
import { db } from "../db";

describe("SyncIssuesPanel", () => {
  beforeEach(async () => {
    await db.syncQueue.clear();
    await db.photoQueue.clear();
    await db.pendingFuelLogs.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("mostra dead-letter e permite reenfileirar com nova chave", async () => {
    const originalKey = crypto.randomUUID();
    const id = await db.syncQueue.add({
      localId: "trip_dead",
      idempotencyKey: originalKey,
      operation: "create",
      entityType: "trip",
      payload: { destination: "Beira" },
      retryCount: 5,
      status: "dead_letter",
      lastError: "network_error",
      deadLetteredAt: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    });

    render(<SyncIssuesPanel />);

    expect(
      await screen.findByText("1 registo(s) não sincronizado(s)"),
    ).toBeDefined();
    expect(screen.getByText("dead letter")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Reenfileirar" }));

    await waitFor(async () => {
      const item = await db.syncQueue.get(id);
      expect(item?.status).toBe("retrying");
      expect(item?.retryCount).toBe(0);
      expect(item?.idempotencyKey).not.toBe(originalKey);
    });
  });

  it("descarta operação e evidências locais apenas após confirmação", async () => {
    const id = await db.syncQueue.add({
      localId: "fuel_dead",
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "fuel_log",
      payload: { liters: 10 },
      retryCount: 5,
      status: "dead_letter",
      createdAt: new Date().toISOString(),
    });
    await db.photoQueue.add({
      localId: "photo_dead",
      entityType: "fuel_log",
      entityLocalId: "fuel_dead",
      blob: new Blob(["photo"]),
      fileType: "receipt",
      retryCount: 5,
      status: "dead_letter",
      createdAt: new Date().toISOString(),
    });
    await db.pendingFuelLogs.add({
      localId: "fuel_dead",
      vehicleId: "vehicle-1",
      driverId: "driver-1",
      fuelType: "diesel",
      liters: 10,
      totalCost: 500,
      kmAtRefuel: 100,
      status: "dead_letter",
      createdAt: new Date().toISOString(),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<SyncIssuesPanel />);
    await screen.findByText("fuel log");
    fireEvent.click(screen.getByRole("button", { name: "Descartar" }));

    await waitFor(async () => {
      expect(await db.syncQueue.get(id)).toBeUndefined();
      expect(await db.photoQueue.count()).toBe(0);
      expect(await db.pendingFuelLogs.count()).toBe(0);
    });
  });
});
