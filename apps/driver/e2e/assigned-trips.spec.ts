import { expect, test } from "@playwright/test";

test.use({ serviceWorkers: "block" });

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
  recipient_name: "Cliente Sul",
  cargo_status: null,
  created_at: "2026-08-23T07:00:00Z",
  updated_at: "2026-08-23T07:00:00Z",
};

const tripDocuments = {
  trip_id: trip.id,
  complete: false,
  can_request: true,
  missing_required: ["transport_document:guia_de_transporte"],
  requirements: [
    { document_type: "load_permit", present: true },
    { document_type: "cargo_manifest", present: true },
    { document_type: "transport_document:guia_de_transporte", present: false },
  ],
  documents: [
    {
      id: "doc-1", document_type: "load_permit", document_number: "LP-001",
      status: "valid", file_id: null, issued_at: "2026-08-23T07:30:00Z",
    },
    {
      id: "doc-2", document_type: "cargo_manifest", document_number: "MAN-001",
      status: "issued", file_id: null, issued_at: "2026-08-23T07:35:00Z",
    },
  ],
  requests: [],
};

test("motorista navega da lista atribuída ao requisito documental real", async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.text() === "Service Worker registration blocked by Playwright") return;
    if (message.type() === "error" || message.type() === "warning") {
      consoleErrors.push(message.text());
    }
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    localStorage.setItem("rotas_access_token", "test-token");
    localStorage.setItem("rotas_tenant_id", "tenant-1");
    localStorage.setItem("rotas_driver_id", "driver-1");
    localStorage.setItem("rotas_device_id", "device-1");
    localStorage.setItem("rotas_driver_name", "Motorista QA");
    localStorage.setItem("rotas_session_id", "session-1");
  });
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: object = {};
    if (path === "/api/v1/driver/bootstrap") {
      body = {
        profile: { tenant_id: "tenant-1", driver_id: "driver-1", device_id: "device-1" },
        checklistTemplates: [],
        activeTrip: trip,
        vehicles: [],
      };
    } else if (path === "/api/v1/driver/trips") {
      body = { items: [trip], total: 1, limit: 20, offset: 0 };
    } else if (path === "/api/v1/driver/trips/trip-1/documents") {
      body = tripDocuments;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Viagens" }).click();
  await page.getByRole("button", { name: "Maputo para Matola" }).click();

  await expect(page.getByRole("heading", { name: "Maputo → Matola" })).toBeVisible();
  await expect(page.getByText("Documentação incompleta")).toBeVisible();
  await expect(page.getByText("Load Permit").first()).toBeVisible();
  await expect(page.getByText("Manifesto de carga").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Solicitar Guia de transporte" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Nova viagem/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Emitir/i })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("assigned-trip-detail.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("recupera viagens e documentos offline sem permitir pedidos", async ({ page }) => {
  let offline = false;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    localStorage.setItem("rotas_access_token", "test-token");
    localStorage.setItem("rotas_tenant_id", "tenant-1");
    localStorage.setItem("rotas_driver_id", "driver-1");
    localStorage.setItem("rotas_device_id", "device-1");
    localStorage.setItem("rotas_driver_name", "Motorista QA");
    localStorage.setItem("rotas_session_id", "session-1");
  });
  await page.route("**/api/v1/**", async (route) => {
    if (offline) {
      await route.abort("internetdisconnected");
      return;
    }
    const path = new URL(route.request().url()).pathname;
    const body = path === "/api/v1/driver/bootstrap"
      ? {
        profile: { tenant_id: "tenant-1", driver_id: "driver-1", device_id: "device-1" },
        checklistTemplates: [], activeTrip: trip, vehicles: [],
      }
      : path === "/api/v1/driver/trips"
        ? { items: [trip], total: 1, limit: 20, offset: 0 }
        : tripDocuments;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Viagens" }).click();
  await page.getByRole("button", { name: "Maputo para Matola" }).click();
  await expect(page.getByText("Documentação incompleta")).toBeVisible();
  await expect.poll(() => page.evaluate(async () => {
    const request = indexedDB.open("RotasMotoristaDB");
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const count = await new Promise<number>((resolve, reject) => {
      const countRequest = database
        .transaction("driverReadCache", "readonly")
        .objectStore("driverReadCache")
        .count();
      countRequest.onsuccess = () => resolve(countRequest.result);
      countRequest.onerror = () => reject(countRequest.error);
    });
    database.close();
    return count;
  })).toBe(2);
  await page.getByRole("button", { name: "Minhas viagens" }).click();
  await page.locator(".trip-back").click();

  offline = true;
  await page.getByRole("button", { name: "Viagens" }).click();
  await expect(page.getByText(/Modo offline — viagens guardadas/)).toBeVisible();
  await page.getByRole("button", { name: "Maputo para Matola" }).click();
  await expect(page.getByText(/Documentos guardados — somente leitura offline/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Solicitar Guia de transporte" })).toHaveCount(0);
});
