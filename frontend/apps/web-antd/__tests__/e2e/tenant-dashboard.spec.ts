import { expect, test } from '@playwright/test';

import { hasTenantCredentials, loginAsTenant } from './common/auth';

const tenantTestsEnabled = hasTenantCredentials();

test.describe('Tenant Dashboard smoke', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!tenantTestsEnabled, 'Tenant credentials are not configured');
    await loginAsTenant(page);
  });

  test('renders recent activity identities', async ({ page }) => {
    await page.goto('/tenant/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('近期活动').first()).toBeVisible();
    await expect(page.locator('.identity-display').first()).toBeVisible();
  });
});
