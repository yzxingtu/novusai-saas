import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';

const adminTestsEnabled = hasAdminCredentials();

test.describe('Admin Dashboard smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('renders recent activity identities', async ({ page }) => {
    await page.goto('http://localhost:5666/admin/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('近期活动').first()).toBeVisible();
    await expect(page.locator('.identity-display').first()).toBeVisible();
  });
});
