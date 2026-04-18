import type { Page } from '@playwright/test';

import process from 'node:process';

import { createTenantSession, getDevBootstrapSecret } from './session';

const TENANT_ADMIN_USERNAME = process.env.TENANT_ADMIN_USERNAME;
const TENANT_ADMIN_PASSWORD = process.env.TENANT_ADMIN_PASSWORD;
const TENANT_ADMIN_TENANT_CODE = process.env.TENANT_ADMIN_TENANT_CODE;

export function hasTenantCredentials() {
  return Boolean(
    getDevBootstrapSecret('tenant') ||
    (TENANT_ADMIN_USERNAME &&
      TENANT_ADMIN_PASSWORD &&
      TENANT_ADMIN_TENANT_CODE),
  );
}

function getTenantCredentials() {
  if (!hasTenantCredentials()) {
    return null;
  }
  return {
    username: TENANT_ADMIN_USERNAME as string,
    password: TENANT_ADMIN_PASSWORD as string,
    tenantCode: TENANT_ADMIN_TENANT_CODE,
  };
}

function requireTenantCredentials() {
  const credentials = getTenantCredentials();
  if (!credentials) {
    throw new Error(
      'Set DEV_TENANT_BOOTSTRAP_SECRET or TENANT_ADMIN_USERNAME, TENANT_ADMIN_PASSWORD, and TENANT_ADMIN_TENANT_CODE to run tenant e2e tests.',
    );
  }
  return credentials;
}

export async function loginAsTenant(page: Page) {
  const bootstrapSecret = getDevBootstrapSecret('tenant');
  if (bootstrapSecret) {
    await createTenantSession(page, getTenantCredentials() ?? undefined);
    return;
  }
  const credentials = requireTenantCredentials();
  await createTenantSession(page, credentials);
}
