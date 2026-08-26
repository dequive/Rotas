import { expect, test } from "@playwright/test";

test.use({ serviceWorkers: "block" });

const emptyPage = { items: [], total: 0, limit: 20, offset: 0 };

test("consulta o diário imutável e recupera-o offline para a mesma identidade", async ({ page }, testInfo) => {
  let offline = false;
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.text() === "Service Worker registration blocked by Playwright") return;
    if (offline && message.text().includes("ERR_INTERNET_DISCONNECTED")) return;
    if (message.type() === "error" || message.type() === "warning") consoleErrors.push(message.text());
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
    if (offline) {
      await route.abort("internetdisconnected");
      return;
    }
    const path = new URL(route.request().url()).pathname;
    let body: object = emptyPage;
    if (path === "/api/v1/driver/bootstrap") {
      body = {
        profile: { tenant_id: "tenant-1", driver_id: "driver-1", device_id: "device-1" },
        checklistTemplates: [], activeTrip: null, vehicles: [],
      };
    } else if (path.endsWith("/records/checklists")) {
      body = { ...emptyPage, total: 1, items: [{
        id: "check-1", trip_id: "trip-1", vehicle_id: "vehicle-1",
        checklist_type: "pre_trip", status: "completed",
        started_at: "2026-08-24T06:50:00Z", completed_at: "2026-08-24T07:00:00Z",
        created_at: "2026-08-24T06:50:00Z",
      }] };
    } else if (path.endsWith("/records/fuel")) {
      body = { ...emptyPage, total: 1, items: [{
        id: "fuel-1", trip_id: "trip-1", vehicle_id: "vehicle-1",
        fuel_date: "2026-08-24T08:00:00Z", station_name: "Posto Maputo",
        fuel_type: "diesel", liters: "80.00", total_cost: "7200.00",
        km_at_refuel: 45210, has_receipt: true, is_verified: true,
        is_flagged: false, created_at: "2026-08-24T08:00:00Z",
      }] };
    } else if (path.endsWith("/records/expenses")) {
      body = { ...emptyPage, total: 1, items: [{
        id: "expense-1", trip_id: "trip-1", expense_type: "toll",
        description: "Portagem", amount: "-250.00", currency: "MZN",
        payment_method: "cash", has_receipt: true, entry_type: "adjustment",
        corrects_id: "expense-original", correction_reason: "Valor corrigido",
        recorded_by_type: "manager", incurred_at: "2026-08-24T09:00:00Z",
        created_at: "2026-08-24T09:00:00Z",
      }] };
    } else if (path.endsWith("/records/advances")) {
      body = { ...emptyPage, total: 1, items: [{
        id: "advance-1", trip_id: "trip-1", total_amount: "3000.00",
        allowance_amount: "3000.00", expense_amount: "0.00", currency: "MZN",
        status: "issued", issued_at: "2026-08-24T06:00:00Z",
      }] };
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Registos" }).click();
  await expect(page.getByRole("heading", { name: "Registos" })).toBeVisible();
  await expect(page.getByText("Checklist antes da viagem")).toBeVisible();
  await expect(page.getByText("Ajuste de despesa")).toBeVisible();
  await expect(page.getByText("Despacho de viagem")).toBeVisible();
  await expect(page.getByText("pre_trip")).toHaveCount(0);

  const navigation = page.getByRole("navigation", { name: "Navegação principal" });
  await expect(navigation).toHaveCSS("position", "fixed");
  const navigationBeforeScroll = await navigation.boundingBox();
  expect(navigationBeforeScroll).not.toBeNull();
  expect(Math.round((navigationBeforeScroll?.y ?? 0) + (navigationBeforeScroll?.height ?? 0))).toBe(844);
  await page.evaluate(() => window.scrollTo(0, 240));
  const navigationAfterScroll = await navigation.boundingBox();
  expect(navigationAfterScroll?.y).toBe(navigationBeforeScroll?.y);

  await page.setViewportSize({ width: 412, height: 915 });
  const shellAtWidePhone = await page.locator(".phone-shell").boundingBox();
  const navigationAtWidePhone = await navigation.boundingBox();
  expect(Math.round(shellAtWidePhone?.width ?? 0)).toBe(412);
  expect(Math.round(navigationAtWidePhone?.width ?? 0)).toBe(412);
  expect(Math.round((navigationAtWidePhone?.y ?? 0) + (navigationAtWidePhone?.height ?? 0))).toBe(915);

  await page.getByRole("button", { name: "Hoje" }).click();
  offline = true;
  await page.getByRole("button", { name: "Registos" }).click();
  await expect(page.getByText(/dados guardados.*somente leitura/i)).toBeVisible();
  await expect(page.getByText("Ajuste de despesa")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("records-offline.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});
