import type { Page } from '@playwright/test';

import process from 'node:process';

import { createAdminSession, getDevBootstrapSecret } from './session';

const ADMIN_USERNAME =
  process.env.ADMIN_USERNAME || process.env.PLATFORM_ADMIN_USERNAME;
const ADMIN_PASSWORD =
  process.env.ADMIN_PASSWORD || process.env.PLATFORM_ADMIN_PASSWORD;

export function hasAdminCredentials() {
  return Boolean(
    getDevBootstrapSecret('admin') || (ADMIN_USERNAME && ADMIN_PASSWORD),
  );
}

function getAdminCredentials() {
  if (!(ADMIN_USERNAME && ADMIN_PASSWORD)) {
    return null;
  }
  return {
    password: ADMIN_PASSWORD as string,
    username: ADMIN_USERNAME as string,
  };
}

function requireAdminCredentials() {
  const credentials = getAdminCredentials();
  if (!credentials) {
    throw new Error(
      'Set DEV_ADMIN_BOOTSTRAP_SECRET or ADMIN_USERNAME and ADMIN_PASSWORD to run admin e2e tests.',
    );
  }
  return credentials;
}

export async function loginAsAdmin(page: Page) {
  const bootstrapSecret = getDevBootstrapSecret('admin');
  if (bootstrapSecret) {
    await createAdminSession(page, getAdminCredentials() ?? undefined);
    return;
  }
  const credentials = requireAdminCredentials();
  await createAdminSession(page, credentials);
}
