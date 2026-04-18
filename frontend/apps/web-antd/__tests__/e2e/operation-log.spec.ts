import type { Page } from '@playwright/test';

import { expect, test } from '@playwright/test';

import { hasAdminCredentials, loginAsAdmin } from './common/admin-auth';
import { hasTenantCredentials, loginAsTenant } from './common/auth';

const adminTestsEnabled = hasAdminCredentials();
const tenantTestsEnabled = hasTenantCredentials();

async function assertIdentityInteractions(page: Page) {
  const identityTrigger = page.locator('.identity-profile-trigger').first();
  if ((await identityTrigger.count()) === 0) {
    return;
  }

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

test.describe('Admin Operation Logs smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!adminTestsEnabled, 'Admin credentials are not configured');
    await loginAsAdmin(page);
  });

  test('renders filters, identity triggers, and detail drawer sections', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/admin/system/operation-logs');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('操作用户').first()).toBeVisible();
    await expect(page.getByText('模块').first()).toBeVisible();
    await expect(page.locator('.vxe-table')).toBeVisible();

    await assertIdentityInteractions(page);

    expect(consoleErrors).toEqual([]);
  });
});

test.describe('Tenant Operation Logs smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders filters, identity triggers, and detail drawer sections', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/tenant/system/operation-logs');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('操作用户').first()).toBeVisible();
    await expect(page.getByText('模块').first()).toBeVisible();
    await expect(page.locator('.ant-select').first()).toBeVisible();
    await expect(page.locator('.vxe-table')).toBeVisible();

    await assertIdentityInteractions(page);

    expect(consoleErrors).toEqual([]);
  });
});
