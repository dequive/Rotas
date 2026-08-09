import { expect, test } from "@playwright/test";

test("logout limpa a identidade anterior antes de permitir novo pareamento", async ({
  context,
  page,
}) => {
  await context.addInitScript(() => {
    localStorage.setItem("rotas_access_token", "access-old");
    localStorage.setItem("rotas_refresh_token", "refresh-old");
    localStorage.setItem("rotas_tenant_id", "tenant-old");
    localStorage.setItem("rotas_driver_id", "driver-old");
    localStorage.setItem("rotas_device_id", "device-old");
    localStorage.setItem("rotas_driver_name", "Motorista Antigo");
    localStorage.setItem("rotas_session_id", "session-old");
  });

  await page.route("**/api/v1/driver/bootstrap", async (route) => {
    const tenant = route.request().headers()["x-tenant-id"];
    const isNew = tenant === "tenant-new";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profile: {
          tenant_id: isNew ? "tenant-new" : "tenant-old",
          driver_id: isNew ? "driver-new" : "driver-old",
          device_id: isNew ? "device-new" : "device-old",
        },
        checklistTemplates: [],
        activeTrip: null,
        vehicles: [],
      }),
    });
  });
  await page.route("**/api/v1/driver-auth/pair", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "access-new",
        refresh_token: "refresh-new",
        driver: {
          id: "driver-new",
          tenant_id: "tenant-new",
          full_name: "Motorista Novo",
        },
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Motorista Antigo" })).toBeVisible();
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener("controllerchange", () => resolve(), {
          once: true,
        });
        void registration.update();
      });
    }
    const cache = await caches.open("api-cache");
    await cache.put(
      "/api/v1/vehicles",
      Response.json({ tenant: "tenant-old", secret: true }),
    );
  });

  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByPlaceholder("ABC123")).toBeVisible();

  const purgeState = await page.evaluate(async () => {
    const databaseState = await new Promise<Record<string, number>>((resolve, reject) => {
      const request = indexedDB.open("RotasMotoristaDB");
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const database = request.result;
        const names = Array.from(database.objectStoreNames);
        const transaction = database.transaction(names, "readonly");
        const counts: Record<string, number> = {};
        let remaining = names.length;
        for (const name of names) {
          const countRequest = transaction.objectStore(name).count();
          countRequest.onerror = () => reject(countRequest.error);
          countRequest.onsuccess = () => {
            counts[name] = countRequest.result;
            remaining -= 1;
            if (remaining === 0) {
              database.close();
              resolve(counts);
            }
          };
        }
      };
    });
    return {
      accessToken: localStorage.getItem("rotas_access_token"),
      refreshToken: localStorage.getItem("rotas_refresh_token"),
      tenantId: localStorage.getItem("rotas_tenant_id"),
      sessionId: localStorage.getItem("rotas_session_id"),
      hasApiCache: await caches.has("api-cache"),
      counts: databaseState,
    };
  });

  expect(purgeState.accessToken).toBeNull();
  expect(purgeState.refreshToken).toBeNull();
  expect(purgeState.tenantId).toBeNull();
  expect(purgeState.sessionId).toBeNull();
  expect(purgeState.hasApiCache).toBe(false);
  expect(Object.values(purgeState.counts).every((count) => count === 0)).toBe(true);

  await page.getByPlaceholder("ABC123").fill("NEW123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Motorista Novo" })).toBeVisible();

  const newIdentity = await page.evaluate(() => ({
    tenantId: localStorage.getItem("rotas_tenant_id"),
    driverId: localStorage.getItem("rotas_driver_id"),
    sessionId: localStorage.getItem("rotas_session_id"),
  }));
  expect(newIdentity.tenantId).toBe("tenant-new");
  expect(newIdentity.driverId).toBe("driver-new");
  expect(newIdentity.sessionId).toBeTruthy();
  expect(newIdentity.sessionId).not.toBe("session-old");
});
