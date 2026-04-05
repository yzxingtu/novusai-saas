import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant AI Call Logs smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders hero card and detail drawer', async ({ page }) => {
    await page.goto('/tenant/ai/call-logs');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('调用日志').first()).toBeVisible();
    await expect(page.getByText('调用人').first()).toBeVisible();
    await expect(page.getByText('模型 / 供应商 / 状态').first()).toBeVisible();
    await expect(page.locator('.monitoring-grid')).toBeVisible();

    const detailButton = page.locator('.monitoring-grid .vxe-body--row button').first();
    if ((await detailButton.count()) > 0) {
      await detailButton.click();
      await expect(page.locator('.ant-drawer')).toBeVisible();
    }
  });
});
