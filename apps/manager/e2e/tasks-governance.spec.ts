import { expect, test } from "@playwright/test";

test("Governance and Workshop task flows use their real backends", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  const suffix = Date.now();
  const governanceTitle = `Incidente Governance E2E ${suffix}`;
  const workshopTitle = `Pedido Oficina E2E ${suffix}`;

  await page.goto("/tarefas/nova");
  await page.getByRole("button", { name: /Governance \/ Incidentes/i }).click();
  await expect(page.getByLabel("Tipo de caso")).toBeVisible();
  await page.getByLabel("Tipo de caso").selectOption("rotas.incident");
  await page.getByLabel(/Título resumido/i).fill(governanceTitle);
  await page.getByLabel(/Descrição detalhada/i).fill("Falha operacional verificada pelo fluxo E2E.");

  const createGovernance = page.waitForResponse(
    (response) =>
      response.url().includes("/api/governance/cases") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Criar Tarefa" }).click();
  expect((await createGovernance).status()).toBe(201);
  await page.waitForURL(/\/tarefas$/);
  await expect(page.getByText(governanceTitle)).toBeVisible();

  const governanceRow = page.getByRole("row").filter({ hasText: governanceTitle });
  await governanceRow.getByRole("link", { name: /Ver detalhes/i }).click();
  await expect(page.getByText("Falha operacional verificada pelo fluxo E2E.")).toBeVisible();

  const transition = page.waitForResponse(
    (response) =>
      response.url().includes("/api/governance/cases/") &&
      response.url().endsWith("/transitions") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Resolver caso" }).click();
  expect((await transition).status()).toBe(201);
  await expect(page.getByRole("button", { name: "Fechar caso" })).toBeVisible();
  await page.screenshot({ path: "test-results/tasks-governance-detail.png", fullPage: true });

  const vehicleResponse = await page.request.post("/api/vehicles", {
    data: {
      plate: `E2E-${String(suffix).slice(-6)}`,
      brand: "ROTAS",
      model: "E2E",
      year: 2026,
      category: "pesado",
      fuel_type: "gasoleo",
      ownership_type: "fleet",
    },
  });
  expect(vehicleResponse.ok()).toBeTruthy();
  const vehicle = (await vehicleResponse.json()) as { id: string };
  expect(vehicle.id).toBeTruthy();

  await page.goto("/tarefas/nova");
  const vehicleSelect = page.getByLabel("Matrícula da Viatura");
  await expect(vehicleSelect).toBeVisible();
  await vehicleSelect.selectOption(vehicle.id);
  await page.getByLabel(/Título resumido/i).fill(workshopTitle);
  await page.getByLabel(/Descrição detalhada/i).fill("Revisão mecânica criada pelo fluxo E2E.");

  const createWorkshop = page.waitForResponse(
    (response) =>
      response.url().includes("/api/proxy") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Criar Tarefa" }).click();
  expect((await createWorkshop).status()).toBe(200);
  await page.waitForURL(/\/tarefas$/);
  await expect(page.getByText(new RegExp(workshopTitle))).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
