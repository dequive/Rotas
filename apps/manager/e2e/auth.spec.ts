import { test, expect } from '@playwright/test';

// These tests verify auth flows and must NOT use saved storageState
test.use({ storageState: { cookies: [], origins: [] } });

test('login with valid credentials redirects to dashboard', async ({ page }) => {
  const email = process.env.E2E_EMAIL ?? 'e2e@rotas.local';
  const password = process.env.E2E_PASSWORD ?? 'E2eP@ss2024!';

  await page.goto('/login');
  await expect(page.locator('input[type="email"]')).toBeVisible();

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await page.waitForURL('/', { timeout: 15_000 });
  expect(page.url()).not.toContain('/login');
});

test('login with wrong password shows error', async ({ page }) => {
  await page.goto('/login');
  await expect(page.locator('input[type="email"]')).toBeVisible();

  await page.locator('input[type="email"]').fill('e2e@rotas.local');
  await page.locator('input[type="password"]').fill('wrong-password-xyz');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.locator('p.login-error')).toBeVisible({ timeout: 8_000 });
});

test('unauthenticated access to /viaturas redirects to /login', async ({ page }) => {
  await page.goto('/viaturas');
  await page.waitForURL(/\/login/, { timeout: 10_000 });
  expect(page.url()).toContain('/login');
});
