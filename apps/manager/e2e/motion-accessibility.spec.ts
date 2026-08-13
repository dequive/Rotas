import { expect, test } from "@playwright/test";

test.use({ storageState: { cookies: [], origins: [] } });

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test("reduced motion collapses non-essential animation and preserves keyboard order", async ({ page }) => {
  await page.goto("/login");

  const reducedMotion = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.style.animation = "spin 10s linear infinite";
    probe.style.transition = "transform 10s linear";
    document.body.append(probe);
    const style = getComputedStyle(probe);
    const result = {
      animationDuration: style.animationDuration,
      animationIterations: style.animationIterationCount,
      transitionDuration: style.transitionDuration,
    };
    probe.remove();
    return result;
  });

  expect(parseFloat(reducedMotion.animationDuration)).toBeLessThanOrEqual(0.00001);
  expect(reducedMotion.animationIterations).toBe("1");
  expect(parseFloat(reducedMotion.transitionDuration)).toBeLessThanOrEqual(0.00001);

  await page.keyboard.press("Tab");
  await expect(page.locator('input[type="email"]')).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator('input[type="password"]')).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Esqueceu a palavra-passe?" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Entrar" })).toBeFocused();
});

test("slow login remains stable and a network failure is announced", async ({ page }) => {
  await page.route("**/api/auth/login", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.abort("failed");
  });

  await page.goto("/login");
  await page.locator('input[type="email"]').fill("operador@rotas.local");
  await page.locator('input[type="password"]').fill("segredo-invalido");

  const card = page.locator(".login-card");
  const before = await card.boundingBox();
  const submit = page.getByRole("button", { name: "Entrar" });
  await submit.click();
  await expect(submit).toBeDisabled();
  await expect(submit).toHaveAttribute("aria-busy", "true");

  const alert = page.locator(".login-error[role=alert]");
  await expect(alert).toContainText("Não foi possível contactar o servidor");
  const after = await card.boundingBox();

  expect(before).not.toBeNull();
  expect(after).not.toBeNull();
  expect(Math.abs((after?.x ?? 0) - (before?.x ?? 0))).toBeLessThan(1);
  expect(Math.abs((after?.height ?? 0) - (before?.height ?? 0))).toBeLessThan(1);
  await expect(submit).toBeEnabled();
});
