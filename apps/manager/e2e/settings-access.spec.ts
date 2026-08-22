import { expect, test } from "@playwright/test";

test("creates a user with the backend-required temporary password", async ({ page }) => {
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
  await page.goto("/settings");
  await page.getByRole("button", { name: "Gestão de Acessos" }).click();
  await page.getByPlaceholder("Nome completo").fill(`Gestor runtime ${suffix}`);
  await page.getByPlaceholder("Email").fill(`gestor.${suffix}@rotas.local`);
  await page.getByLabel("Palavra-passe temporária").fill(`Temp-${suffix}!`);
  await page.getByRole("button", { name: "Criar utilizador" }).click();

  await expect(page.getByText("Utilizador criado com sucesso!", { exact: true })).toBeVisible();
  await expect(page.getByText(`gestor.${suffix}@rotas.local`, { exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);
  expect(failedApiResponses).toEqual([]);
});
