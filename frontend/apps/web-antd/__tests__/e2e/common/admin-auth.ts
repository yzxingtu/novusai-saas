// Test type: smoke
// Scope: admin Playwright authentication bootstrap helper.
import type { Page } from '@playwright/test';

import { createAdminSession, getDevBootstrapSecret } from './session';

export function hasAdminCredentials() {
  return Boolean(getDevBootstrapSecret('admin'));
}

function requireAdminBootstrapSecret() {
  if (!getDevBootstrapSecret('admin')) {
    throw new Error(
      'Set DEV_ADMIN_BOOTSTRAP_SECRET to run admin e2e smoke. Legacy admin login credentials are not used by checked-in smoke helpers.',
    );
  }
}

export async function loginAsAdmin(page: Page) {
  requireAdminBootstrapSecret();
  await createAdminSession(page);
}
