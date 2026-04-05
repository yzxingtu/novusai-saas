import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';

const adminTestsEnabled = hasAdminCredentials();

test.describe('Admin Profile smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('renders identity card and profile fields', async ({ page }) => {
    await page.goto('http://localhost:5666/admin/profile');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.identity-display').first()).toBeVisible();
    await expect(page.getByText('基本信息').first()).toBeVisible();
    await expect(page.getByText('昵称').first()).toBeVisible();
    await expect(page.getByText('邮箱').first()).toBeVisible();
  });
});
