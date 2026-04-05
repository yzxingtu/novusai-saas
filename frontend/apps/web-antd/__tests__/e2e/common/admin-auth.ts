import type { Page } from '@playwright/test';

import { createAdminSession } from './session';

const ADMIN_USERNAME =
  process.env.ADMIN_USERNAME || process.env.PLATFORM_ADMIN_USERNAME;
const ADMIN_PASSWORD =
  process.env.ADMIN_PASSWORD || process.env.PLATFORM_ADMIN_PASSWORD;
const ADMIN_BASE_URL =
  (process.env.ADMIN_BASE_URL || 'http://localhost:5666').replace(/\/+$/, '');

export function hasAdminCredentials() {
  return Boolean(ADMIN_USERNAME && ADMIN_PASSWORD);
}

function requireAdminCredentials() {
  if (!hasAdminCredentials()) {
    throw new Error(
      'Set ADMIN_USERNAME and ADMIN_PASSWORD to run admin e2e tests.',
    );
  }
  return {
    password: ADMIN_PASSWORD as string,
    username: ADMIN_USERNAME as string,
  };
}

export async function loginAsAdmin(page: Page) {
  const credentials = requireAdminCredentials();
  await page.goto(`${ADMIN_BASE_URL}/admin/login`);
  await createAdminSession(page, {
    password: credentials.password,
    username: credentials.username,
  });
}
