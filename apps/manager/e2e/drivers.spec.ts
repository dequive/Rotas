import { test, expect } from '@playwright/test';

test('drivers list page loads', async ({ page }) => {
  await page.goto('/motoristas');
  // Table, empty state, or heading must appear
  await expect(
    page.locator('table, [data-testid="empty-state"], h1, h2').first()
  ).toBeVisible({ timeout: 10_000 });
});

test('driver detail page loads', async ({ page }) => {
  await page.goto('/motoristas');

  // If no drivers exist, skip gracefully
  const firstLink = page.locator('table tbody tr a').first();
  const count = await firstLink.count();
  if (count === 0) {
    test.skip();
    return;
  }

  await firstLink.click();
  await page.waitForURL(/\/motoristas\/.+/, { timeout: 10_000 });

  // Detail page must render some heading
  await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 10_000 });
});
