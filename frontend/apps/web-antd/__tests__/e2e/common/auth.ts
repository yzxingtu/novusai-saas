import type { Page } from '@playwright/test';

import { createTenantSession } from './session';

const TENANT_ADMIN_USERNAME = process.env.TENANT_ADMIN_USERNAME;
const TENANT_ADMIN_PASSWORD = process.env.TENANT_ADMIN_PASSWORD;
const TENANT_ADMIN_TENANT_CODE = process.env.TENANT_ADMIN_TENANT_CODE;

export function hasTenantCredentials() {
  return Boolean(
    TENANT_ADMIN_USERNAME && TENANT_ADMIN_PASSWORD && TENANT_ADMIN_TENANT_CODE,
  );
}

function requireTenantCredentials() {
  if (!hasTenantCredentials()) {
    throw new Error(
      'Set TENANT_ADMIN_USERNAME, TENANT_ADMIN_PASSWORD, and TENANT_ADMIN_TENANT_CODE to run tenant e2e tests.',
    );
  }
  return {
    username: TENANT_ADMIN_USERNAME as string,
    password: TENANT_ADMIN_PASSWORD as string,
    tenantCode: TENANT_ADMIN_TENANT_CODE,
  };
}

export async function loginAsTenant(page: Page) {
  const credentials = requireTenantCredentials();
  await createTenantSession(page, {
    password: credentials.password,
    tenantCode: credentials.tenantCode as string,
    username: credentials.username,
  });
}
