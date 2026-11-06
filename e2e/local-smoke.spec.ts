import { test, expect } from '@playwright/test';

test('local API health is explicit about prototype status', async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8000/api/health');
  expect(response.ok()).toBeTruthy();
  const health = await response.json();
  expect(health.production_ready).toBe(false);
});

test('local dashboard renders controls without secrets', async ({ page }) => {
  await page.goto('http://127.0.0.1:3000/apps/workspace/index.html');
  await expect(page.locator('body')).toContainText(/CV|Pipeline|Sign in/i);
  await expect(page.locator('body')).not.toContainText(/sb_secret_|service_role/i);
});
