import { test, expect } from '@playwright/test';

test('vehicles list page loads', async ({ page }) => {
  await page.goto('/viaturas');
  // Either a table row or an empty-state message must appear — not a hard crash
  await expect(
    page.locator('table, [data-testid="empty-state"], text=Sem viaturas').first()
  ).toBeVisible({ timeout: 10_000 });
});

test('vehicle detail page shows Apólices de Seguro section', async ({ page }) => {
  await page.goto('/viaturas');

  // If no vehicles exist, skip gracefully
  const firstLink = page.locator('table tbody tr a').first();
  const count = await firstLink.count();
  if (count === 0) {
    test.skip();
    return;
  }

  await firstLink.click();
  await page.waitForURL(/\/viaturas\/.+/, { timeout: 10_000 });

  // InsuranceTab renders "Apólices de Seguro" heading
  await expect(page.getByText('Apólices de Seguro')).toBeVisible({ timeout: 10_000 });
});
