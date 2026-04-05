import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';
import { hasTenantCredentials, loginAsTenant } from './common/auth';

const adminTestsEnabled = hasAdminCredentials();
const tenantTestsEnabled = hasTenantCredentials();

test.describe('Admin Organization smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('keeps organization member actions semantically focused', async ({
    page,
  }) => {
    await page.goto('/admin/system/organization');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.member-panel')).toBeVisible();
    await expect(page.getByRole('button', { name: '创建账号' })).toBeVisible();
    await expect(
      page.getByText('已有账号的组织归属请通过“编辑账号”调整'),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: '添加已有账号' }),
    ).toHaveCount(0);
  });
});

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
    await expect(page.getByRole('button', { name: '创建账号' })).toBeVisible();
    await expect(
      page.getByText('已有账号的组织归属请通过“编辑账号”调整'),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: '添加已有账号' }),
    ).toHaveCount(0);
  });
});
