import { test, expect } from '@playwright/test';

test('billing page loads with correct title', async ({ page }) => {
  await page.goto('/cobranca');
  await expect(page.getByText('Cobrança de Transporte')).toBeVisible({ timeout: 10_000 });
});
