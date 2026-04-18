import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant AI Call Logs smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders hero card and detail drawer', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/tenant/ai/call-logs');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('调用日志').first()).toBeVisible();
    await expect(page.getByText('调用人').first()).toBeVisible();
    await expect(page.getByText('模型 / 供应商 / 状态').first()).toBeVisible();
    await expect(page.locator('.monitoring-grid')).toBeVisible();

    const identityTrigger = page.locator('.identity-profile-trigger').first();
    if ((await identityTrigger.count()) > 0) {
      await identityTrigger.hover();
      await expect(
        page.locator('.identity-summary-card[data-mode="quick"]').first(),
      ).toBeVisible();
      await identityTrigger.click();
      await expect(
        page.locator('.ant-drawer [data-section="overview"]'),
      ).toBeVisible();
      await expect(
        page.locator('.ant-drawer [data-section="account"]'),
      ).toBeVisible();
      await expect(
        page.locator('.ant-drawer [data-section="activity"]'),
      ).toBeVisible();
    }

    expect(consoleErrors).toEqual([]);
  });
});
