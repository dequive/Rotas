import { devices, expect, test } from "@playwright/test";

test.use({
  ...devices["Pixel 5"],
  reducedMotion: "reduce",
});

test("reduced motion keeps the mobile sync surface stable under a slow bootstrap", async ({ context, page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await context.addInitScript(() => {
    localStorage.setItem("rotas_access_token", "access-motion-e2e");
    localStorage.setItem("rotas_refresh_token", "refresh-motion-e2e");
    localStorage.setItem("rotas_tenant_id", "tenant-motion-e2e");
    localStorage.setItem("rotas_driver_id", "driver-motion-e2e");
    localStorage.setItem("rotas_device_id", "device-motion-e2e");
    localStorage.setItem("rotas_driver_name", "Motorista Motion E2E");
    localStorage.setItem("rotas_session_id", "session-motion-e2e");
  });
  await page.route("**/api/v1/driver/bootstrap", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profile: { tenant_id: "tenant-motion-e2e", driver_id: "driver-motion-e2e", device_id: "device-motion-e2e" },
        checklistTemplates: [],
        activeTrip: null,
        vehicles: [],
      }),
    });
  });

  await page.goto("/");
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-motion: reduce)").matches)).toBe(true);
  const banner = page.locator('.sync-banner[aria-label="Estado de sincronização"]');
  await expect(banner).toBeAttached();
  const idleHeight = await banner.evaluate((element) => element.getBoundingClientRect().height);
  expect(idleHeight).toBeGreaterThanOrEqual(48);

  const motion = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.className = "spin";
    document.body.append(probe);
    const style = getComputedStyle(probe);
    const result = [style.animationDuration, style.animationIterationCount];
    probe.remove();
    return result;
  });
  expect(parseFloat(motion[0] ?? "1")).toBeLessThanOrEqual(0.00001);
  expect(motion[1]).toBe("1");

  await expect(page.getByText("Sem viagem activa", { exact: true })).toBeVisible();
  await context.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await expect(banner).toContainText("Sem ligação — a gravar localmente");
  const offlineHeight = await banner.evaluate((element) => element.getBoundingClientRect().height);
  expect(Math.abs(offlineHeight - idleHeight)).toBeLessThan(1);
});
