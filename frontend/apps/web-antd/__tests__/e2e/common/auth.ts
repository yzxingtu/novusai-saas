// Test type: smoke
// Scope: tenant Playwright authentication bootstrap helper.
import type { Page } from '@playwright/test';

import { createTenantSession, getDevBootstrapSecret } from './session';

export function hasTenantCredentials() {
  return Boolean(getDevBootstrapSecret('tenant'));
}

function requireTenantBootstrapSecret() {
  if (!getDevBootstrapSecret('tenant')) {
    throw new Error(
      'Set DEV_TENANT_BOOTSTRAP_SECRET to run tenant e2e smoke. Legacy tenant login credentials are not used by checked-in smoke helpers.',
    );
  }
}

export async function loginAsTenant(page: Page) {
  requireTenantBootstrapSecret();
  await createTenantSession(page);
}
