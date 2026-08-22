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

const identityScope = {
  tenantId: "tenant-1",
  driverId: "driver-1",
  sessionId: "session-1",
};

describe("SyncIssuesPanel", () => {
  beforeEach(async () => {
    await db.syncQueue.clear();
    await db.photoQueue.clear();
    await db.pendingFuelLogs.clear();
    localStorage.setItem("rotas_tenant_id", identityScope.tenantId);
    localStorage.setItem("rotas_driver_id", identityScope.driverId);
    localStorage.setItem("rotas_session_id", identityScope.sessionId);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("mostra dead-letter e permite reenfileirar com nova chave", async () => {
    const originalKey = crypto.randomUUID();
    const id = await db.syncQueue.add({
      ...identityScope,
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
      ...identityScope,
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
      ...identityScope,
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
      tenantId: identityScope.tenantId,
      sessionId: identityScope.sessionId,
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

describe("SyncIssuesPanel — mensagens accionáveis", () => {
  beforeEach(async () => {
    await db.syncQueue.clear();
    localStorage.setItem("rotas_tenant_id", identityScope.tenantId);
    localStorage.setItem("rotas_driver_id", identityScope.driverId);
    localStorage.setItem("rotas_session_id", identityScope.sessionId);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  async function seedFailure(errorCode: string, lastError: string) {
    await db.syncQueue.add({
      ...identityScope,
      localId: `local_${errorCode}`,
      idempotencyKey: crypto.randomUUID(),
      operation: "create",
      entityType: "fuel_log",
      payload: {},
      retryCount: 1,
      status: "failed",
      lastError,
      lastErrorCode: errorCode,
      createdAt: new Date().toISOString(),
    });
  }

  it("não mostra a mensagem técnica do servidor como explicação principal", async () => {
    // Exactamente o que o backend devolve para um payload incompleto.
    await seedFailure("payload_validation_failed", "request_reference: Field required");
    render(<SyncIssuesPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/Este registo está incompleto e o servidor não o aceita/i),
      ).toBeTruthy();
    });
  });

  it("desactiva o reenvio quando reenviar daria o mesmo resultado", async () => {
    await seedFailure("payload_validation_failed", "request_reference: Field required");
    render(<SyncIssuesPanel />);

    const button = await screen.findByRole("button", { name: /Reenfileirar/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.getAttribute("title")).toMatch(/mesmo resultado/i);
  });

  it("mantém o reenvio disponível quando a falha é transitória", async () => {
    await seedFailure("sync_operation_failed", "The server could not process this operation.");
    render(<SyncIssuesPanel />);

    const button = await screen.findByRole("button", { name: /Reenfileirar/i });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("explica um código desconhecido em vez de mostrar nada", async () => {
    await seedFailure("codigo_que_esta_app_nao_conhece", "something new from the server");
    render(<SyncIssuesPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Este registo não foi aceite/i)).toBeTruthy();
    });
  });
});
