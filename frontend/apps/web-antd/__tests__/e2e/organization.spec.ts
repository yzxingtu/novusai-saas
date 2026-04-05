import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant Organization smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('opens tree and member panel placeholders', async ({ page }) => {
    await page.goto('/tenant/system/organization');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('负责人信息').first()).toBeVisible();
    await expect(page.locator('.member-panel')).toBeVisible();
    await expect(
      page.getByRole('button', { name: '添加已有账号' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: '创建账号' })).toBeVisible();
  });
});
