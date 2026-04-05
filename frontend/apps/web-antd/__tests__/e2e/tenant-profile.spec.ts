import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant Profile smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders identity card and profile fields', async ({ page }) => {
    await page.goto('/tenant/profile');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.identity-display').first()).toBeVisible();
    await expect(page.getByText('基本信息').first()).toBeVisible();
    await expect(page.getByText('昵称').first()).toBeVisible();
    await expect(page.getByText('邮箱').first()).toBeVisible();
  });
});
