import { expect, test } from "@playwright/test";

test("reabre o PWA offline com bootstrap da mesma identidade", async ({
  context,
  page,
}) => {
  await context.addInitScript(() => {
    localStorage.setItem("rotas_access_token", "access-e2e");
    localStorage.setItem("rotas_refresh_token", "refresh-e2e");
    localStorage.setItem("rotas_tenant_id", "tenant-e2e");
    localStorage.setItem("rotas_driver_id", "driver-e2e");
    localStorage.setItem("rotas_device_id", "device-e2e");
    localStorage.setItem("rotas_driver_name", "Motorista E2E");
    localStorage.setItem("rotas_session_id", "session-e2e");
  });

  await page.route("**/api/v1/driver/bootstrap", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        profile: {
          tenant_id: "tenant-e2e",
          driver_id: "driver-e2e",
          device_id: "device-e2e",
        },
        checklistTemplates: [
          {
            id: "template-e2e",
            name: "Checklist E2E",
            type: "pre_trip",
            items: [],
          },
        ],
        activeTrip: {
          id: "trip-e2e",
          origin: "Maputo",
          destination: "Beira",
          status: "in_progress",
          billing_status: "pending_delivery_proof",
          load_state: "loaded",
          vehicle_id: "vehicle-e2e",
          vehicle_plate: "ABC-12-34",
        },
        vehicles: [],
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("Maputo → Beira")).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(
        () =>
          new Promise<boolean>((resolve, reject) => {
            const request = indexedDB.open("RotasMotoristaDB");
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
              const database = request.result;
              const transaction = database.transaction(
                "bootstrapCache",
                "readonly",
              );
              const getRequest = transaction
                .objectStore("bootstrapCache")
                .get("tenant-e2e:driver-e2e:session-e2e");
              getRequest.onerror = () => reject(getRequest.error);
              getRequest.onsuccess = () => {
                resolve(Boolean(getRequest.result));
                database.close();
              };
            };
          }),
      ),
    )
    .toBe(true);
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller) {
      await new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener(
          "controllerchange",
          () => resolve(),
          { once: true },
        );
        void registration.update();
      });
    }
  });

  await page.unroute("**/api/v1/driver/bootstrap");
  await page.close();
  await context.setOffline(true);

  const offlinePage = await context.newPage();
  await offlinePage.goto("/");
  await expect(offlinePage.getByText("Maputo → Beira")).toBeVisible();
  await expect(
    offlinePage.getByText(/Sem ligação — a gravar localmente/),
  ).toBeVisible();
  await expect
    .poll(() =>
      offlinePage.evaluate(async () => {
        const apiCache = await caches.open("api-cache");
        const cached = await apiCache.match("/api/v1/driver/bootstrap");
        return Boolean(cached);
      }),
    )
    .toBe(false);

  await offlinePage.evaluate(() => {
    const originalFetch = window.fetch.bind(window);
    const captured: Array<{
      headerKey: string | null;
      bodyKey: string;
      localId: string;
    }> = [];
    (window as typeof window & { __syncRequests?: typeof captured }).__syncRequests =
      captured;
    window.fetch = async (input, init) => {
      const url = new URL(
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url,
        window.location.origin,
      );
      if (url.pathname === "/api/v1/sync/batch") {
        const body = JSON.parse(String(init?.body)) as {
          operations: Array<{
            local_id: string;
            idempotency_key: string;
          }>;
        };
        const operation = body.operations[0]!;
        captured.push({
          headerKey: new Headers(init?.headers).get("Idempotency-Key"),
          bodyKey: operation.idempotency_key,
          localId: operation.local_id,
        });
        return Response.json({
          results: [
            {
              local_id: operation.local_id,
              status: "processed",
              entity_type: "trip_stop",
            },
          ],
        });
      }
      return originalFetch(input, init);
    };
  });
  await offlinePage.evaluate(
    () =>
      new Promise<void>((resolve, reject) => {
        const request = indexedDB.open("RotasMotoristaDB");
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
          const database = request.result;
          const transaction = database.transaction("syncQueue", "readwrite");
          transaction.onerror = () => reject(transaction.error);
          transaction.oncomplete = () => {
            database.close();
            resolve();
          };
          transaction.objectStore("syncQueue").add({
            tenantId: "tenant-e2e",
            driverId: "driver-e2e",
            sessionId: "session-e2e",
            localId: "stop-offline-e2e",
            idempotencyKey: "idem-offline-e2e",
            operation: "create",
            entityType: "trip_stop",
            payload: {
              tripLocalId: "trip-e2e",
              type: "rest",
              clientCapturedAt: "2026-07-26T20:00:00.000Z",
            },
            retryCount: 0,
            status: "local_only",
            createdAt: "2026-07-26T20:00:00.000Z",
          });
        };
      }),
  );

  await context.setOffline(false);
  await expect.poll(() => offlinePage.evaluate(() => navigator.onLine)).toBe(true);
  await offlinePage.evaluate(() => {
    window.dispatchEvent(new Event("online"));
  });
  await expect
    .poll(() =>
      offlinePage.evaluate(
        () =>
          (
            window as typeof window & {
              __syncRequests?: Array<unknown>;
            }
          ).__syncRequests?.length ?? 0,
      ),
    )
    .toBe(1);
  const syncRequest = await offlinePage.evaluate(
    () =>
      (
        window as typeof window & {
          __syncRequests?: Array<{
            headerKey: string | null;
            bodyKey: string;
            localId: string;
          }>;
        }
      ).__syncRequests?.[0],
  );
  expect(syncRequest).toEqual({
    headerKey: "idem-offline-e2e",
    bodyKey: "idem-offline-e2e",
    localId: "stop-offline-e2e",
  });
  await expect
    .poll(() =>
      offlinePage.evaluate(
        () =>
          new Promise<number>((resolve, reject) => {
            const request = indexedDB.open("RotasMotoristaDB");
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
              const database = request.result;
              const transaction = database.transaction(
                "syncQueue",
                "readonly",
              );
              const countRequest = transaction.objectStore("syncQueue").count();
              countRequest.onerror = () => reject(countRequest.error);
              countRequest.onsuccess = () => {
                resolve(countRequest.result);
                database.close();
              };
            };
          }),
      ),
    )
    .toBe(0);
  await offlinePage.evaluate(() => {
    window.dispatchEvent(new Event("online"));
  });
  await offlinePage.waitForTimeout(500);
  expect(
    await offlinePage.evaluate(
      () =>
        (
          window as typeof window & {
            __syncRequests?: Array<unknown>;
          }
        ).__syncRequests?.length ?? 0,
    ),
  ).toBe(1);
});
