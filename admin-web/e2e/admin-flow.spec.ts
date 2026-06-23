import { expect, test } from '@playwright/test';

// Happy-path smoke. Requires a running backend (seeded admin gbrewards/12345678)
// and the admin-web dev server. Credentials overridable via env.
const USER = process.env.E2E_ADMIN_USER ?? 'gbrewards';
const PASS = process.env.E2E_ADMIN_PASS ?? '12345678';

test('admin can log in and reach the dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill(USER);
  await page.getByLabel('Password').fill(PASS);
  await page.getByRole('button', { name: /log in/i }).click();

  await expect(page.getByText('Dashboard')).toBeVisible();
  await expect(page.getByText('Total users')).toBeVisible();
});

test('admin can create a product', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill(USER);
  await page.getByLabel('Password').fill(PASS);
  await page.getByRole('button', { name: /log in/i }).click();

  await page.getByRole('menuitem', { name: /products/i }).click();
  await page.getByRole('button', { name: /new product/i }).click();
  await page.getByLabel('Name').fill(`E2E ${Date.now()}`);
  await page.getByLabel('Points value').fill('50');
  await page.getByRole('button', { name: /save/i }).click();

  await expect(page.getByText(/E2E /)).toBeVisible();
});
