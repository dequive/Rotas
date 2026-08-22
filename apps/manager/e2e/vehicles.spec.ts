import { test, expect } from '@playwright/test';

test('vehicles list page loads', async ({ page }) => {
  await page.goto('/viaturas');
  // Either a table row or an empty-state message must appear — not a hard crash
  await expect(
    page.locator('table').first()
  ).toBeVisible({ timeout: 10_000 });
});

test('vehicle detail page shows Apólices de Seguro section', async ({ page }) => {
  await page.goto('/viaturas');

  // If no vehicles exist, skip gracefully
  const firstLink = page.getByRole('link', { name: 'Ver Detalhe' }).first();
  const count = await firstLink.count();
  if (count === 0) {
    test.skip();
    return;
  }

  await firstLink.click();
  await page.waitForURL(/\/viaturas\/.+/, { timeout: 10_000 });

  await page.getByRole('tab', { name: 'Administração' }).click();
  await expect(page.getByText('Apólices de Seguro')).toBeVisible({ timeout: 10_000 });
});
