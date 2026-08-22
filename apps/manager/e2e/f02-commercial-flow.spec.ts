import { expect, test } from "@playwright/test";

test("executes client to contract to trip through the Manager", async ({ page }) => {
  test.setTimeout(90_000);
  const consoleErrors: string[] = [];
  const failedApiResponses: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && response.url().includes("/api/")) {
      failedApiResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  const suffix = String(Date.now()).slice(-9);
  const clientName = `Cliente runtime ${suffix}`;
  const contractReference = `CTR-RUNTIME-${suffix}`;
  const orderReference = `PO-RUNTIME-${suffix}`;
  const origin = `Maputo ${suffix}`;
  const destination = `Beira ${suffix}`;

  await page.goto("/clientes");
  await page.getByRole("button", { name: "Novo Cliente" }).click();
  await page.getByPlaceholder("Nome comercial do cliente").fill(clientName);
  await page.getByPlaceholder("000000000").fill(suffix);
  await page.getByRole("button", { name: "Guardar Cliente" }).click();

  await expect(page.getByText(clientName, { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Contratos", exact: true }).click();
  await page.getByRole("button", { name: "Novo contrato" }).click();
  await page.getByPlaceholder("CTR-2026-001").fill(contractReference);
  await page.getByRole("textbox", { name: "Título" }).fill("Contrato runtime F-02");
  await page.getByRole("checkbox", { name: "Requer Load Permit" }).uncheck();

  await page.getByText("Pesquisar cliente…", { exact: true }).click();
  await page.getByRole("option", { name: new RegExp(clientName) }).click();
  await expect(page.getByRole("combobox").filter({ hasText: clientName })).toBeVisible();

  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText(contractReference, { exact: true })).toBeVisible();

  await page.goto("/");
  await page.getByRole("button", { name: "Nova ordem" }).click();
  await page.getByLabel("Contrato").selectOption({
    label: `${contractReference} — ${clientName}`,
  });
  await page.getByLabel("Referência do cliente").fill(orderReference);
  await page.getByLabel("Origem", { exact: true }).fill(origin);
  await page.getByLabel("Destino", { exact: true }).fill(destination);
  await page.getByLabel("Data de recolha").fill("2026-08-21");
  await page.getByLabel("Peso estimado (kg)").fill("1200");
  await page.getByRole("button", { name: "Criar rascunho" }).click();

  const orderCard = page
    .getByText(orderReference, { exact: true })
    .locator("xpath=../../..");
  await expect(orderCard).toBeVisible();
  await orderCard.getByRole("button", { name: "Confirmar ordem" }).click();
  await expect(orderCard.getByRole("button", { name: "Atribuir motorista" })).toBeVisible();

  await orderCard.getByRole("button", { name: "Atribuir motorista" }).click();
  await page.getByLabel("Selecionar viatura").selectOption({ index: 1 });
  await page.getByLabel("Selecionar motorista").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Confirmar despacho" }).click();
  await expect(page.getByText(orderReference, { exact: true })).toHaveCount(0);

  await page.goto("/viagens");
  const tripsTable = page.getByRole("region", { name: "Tabela de viagens" });
  let tripRow = tripsTable.getByRole("row", {
    name: new RegExp(`${origin}.*${destination}`),
  });
  await expect(tripRow).toBeVisible();
  await tripRow.getByRole("button", { name: "Solicitar saída" }).click();
  await expect(tripRow.getByText("Aguarda autorização")).toBeVisible();

  await page.goto("/");
  const pendingQueue = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Autorização pendente", exact: true }),
  });
  let clearanceItem = pendingQueue
    .getByText(`${origin} -> ${destination}`, { exact: true })
    .locator("xpath=..");
  await clearanceItem.getByRole("button", { name: "Aprovar saída" }).click();
  for (const label of [
    "Viatura verificada",
    "Motorista verificado",
    "Documentos verificados",
    "Load permit verificado",
    "Carga verificada",
    "Adiantamento de combustível verificado",
    "Risco da rota verificado",
  ]) {
    await page.getByRole("checkbox", { name: label }).check();
  }
  await page.getByRole("button", { name: "Confirmar aprovação" }).click();

  clearanceItem = pendingQueue
    .getByText(`${origin} -> ${destination}`, { exact: true })
    .locator("xpath=..");
  await clearanceItem.getByRole("button", { name: "Iniciar saída" }).click();
  await expect(
    pendingQueue.getByText(`${origin} -> ${destination}`, { exact: true }),
  ).toHaveCount(0);

  await page.goto("/viagens");
  tripRow = page.getByRole("region", { name: "Tabela de viagens" }).getByRole("row", {
    name: new RegExp(`${origin}.*${destination}`),
  });
  await tripRow.getByRole("button", { name: "Iniciar" }).click();
  await tripRow.getByRole("spinbutton", { name: "Km inicial" }).fill("1300");
  await tripRow.getByRole("button", { name: "Confirmar início" }).click();
  await expect(tripRow.getByRole("button", { name: "Concluir", exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);
  expect(failedApiResponses).toEqual([]);
});

test("renews an expired page session before dashboard data loads", async ({
  context,
  page,
}) => {
  const failedApiResponses: string[] = [];
  page.on("response", (response) => {
    if (response.status() >= 400 && response.url().includes("/api/")) {
      failedApiResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  await context.addCookies([
    {
      name: "rotas_access_token",
      value: "expired.access-token",
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);

  await page.goto("/");

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: "Nova ordem" })).toBeVisible();
  expect(failedApiResponses).toEqual([]);
});
