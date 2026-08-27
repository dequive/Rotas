import { test, expect } from '@playwright/test';

test('drivers list page loads', async ({ page }) => {
  await page.goto('/motoristas');
  // Table, empty state, or heading must appear
  await expect(
    page.locator('table, [data-testid="empty-state"], h1, h2').first()
  ).toBeVisible({ timeout: 10_000 });
});

test('driver Hub 360 opens with the selected driver', async ({ page }) => {
  await page.goto('/motoristas');

  await page.getByRole('button', { name: 'Motorista E2E Sintético' }).click();
  const dialog = page.getByRole('dialog', { name: 'Hub 360 do Motorista' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Motorista E2E Sintético')).toBeVisible();
});
