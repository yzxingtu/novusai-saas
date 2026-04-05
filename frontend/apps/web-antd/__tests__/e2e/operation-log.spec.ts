import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant Operation Logs smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders filters and column headers', async ({ page }) => {
    await page.goto('/tenant/system/operation-logs');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('操作用户').first()).toBeVisible();
    await expect(page.getByText('模块').first()).toBeVisible();
    await expect(page.locator('.ant-select').first()).toBeVisible();
    await expect(page.locator('.vxe-table')).toBeVisible();
  });
});
