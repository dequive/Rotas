import { expect, test } from "@playwright/test";

const vehicle = {
  plate: `E25-${Date.now().toString().slice(-6)}`,
  chassis: `ROTAS-ISSUE25-${Date.now()}`,
  brand: "Mercedes-Benz",
  model: "Actros",
  year: "2025",
  currentKm: "1250",
};

async function fillVehicleForm(page: import("@playwright/test").Page) {
  await page.getByLabel("Matrícula").fill(vehicle.plate);
  await page.getByLabel("Chassis").fill(vehicle.chassis);
  await page.getByLabel("Marca").fill(vehicle.brand);
  await page.getByLabel("Modelo").fill(vehicle.model);
  await page.getByLabel("Ano").fill(vehicle.year);
  await page.getByLabel("Km actual").fill(vehicle.currentKm);
}

test("authenticated vehicle creation exposes pending state on a slow real mutation", async ({ page }) => {
  await page.route("**/api/vehicles", async (route) => {
    if (route.request().method() === "POST") {
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    await route.continue();
  });

  await page.goto("/viaturas");
  await page.getByRole("button", { name: "Nova viatura" }).click();
  await fillVehicleForm(page);

  const save = page.getByRole("button", { name: "Guardar" });
  await save.click();

  await expect(page.getByRole("button", { name: "A guardar..." })).toBeDisabled();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText(vehicle.plate)).toBeVisible({ timeout: 15_000 });
});

test("failed authenticated mutation announces the error and preserves form context", async ({ page }) => {
  await page.route("**/api/vehicles", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { message: "Serviço temporariamente indisponível." } }),
      });
      return;
    }
    await route.continue();
  });

  await page.goto("/viaturas");
  await page.getByRole("button", { name: "Nova viatura" }).click();
  await fillVehicleForm(page);
  await page.getByRole("button", { name: "Guardar" }).click();

  await expect(page.getByRole("dialog").getByRole("alert")).toHaveText(
    "Serviço temporariamente indisponível.",
  );
  await expect(page.getByLabel("Matrícula")).toHaveValue(vehicle.plate);
  await expect(page.getByRole("button", { name: "Guardar" })).toBeEnabled();
});
