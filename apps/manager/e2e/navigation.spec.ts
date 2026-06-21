import { test, expect } from '@playwright/test';

test('dashboard loads and sidebar shows Viaturas link', async ({ page }) => {
  await page.goto('/');
  // Sidebar should contain the Viaturas nav link
  await expect(page.getByRole('link', { name: 'Viaturas' })).toBeVisible();
});

test('clicking Motoristas link navigates to /motoristas', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Motoristas' }).click();
  await page.waitForURL(/\/motoristas/, { timeout: 10_000 });
  expect(page.url()).toContain('/motoristas');
});
