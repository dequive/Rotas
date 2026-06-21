import { test as setup, expect } from '@playwright/test';
import * as path from 'path';

const authFile = path.join(__dirname, '../playwright/.auth/user.json');

setup('authenticate as E2E user', async ({ page }) => {
  const email = process.env.E2E_EMAIL ?? 'e2e@rotas.local';
  const password = process.env.E2E_PASSWORD ?? 'E2eP@ss2024!';

  await page.goto('/login');

  // Wait for the login form to be visible
  await expect(page.locator('input[type="email"]')).toBeVisible();

  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  // After successful login, middleware redirects to /
  // waitForURL confirms the redirect completed before saving state
  await page.waitForURL('/', { timeout: 15_000 });

  // Confirm we are actually on the dashboard (not still on /login)
  expect(page.url()).toContain('/');
  expect(page.url()).not.toContain('/login');

  // Save cookies (including httpOnly) to file for all subsequent tests
  await page.context().storageState({ path: authFile });
});
