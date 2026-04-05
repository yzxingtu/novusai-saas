import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { Page } from '@playwright/test';

import { expect, request } from '@playwright/test';

type AuthEndpoint = 'admin' | 'tenant';

interface LoginPayload {
  password: string;
  tenant_code?: string;
  username: string;
}

interface LoginResponse {
  code: number;
  data?: {
    access_token?: string;
    refresh_token?: string;
  };
  message?: string;
}

const API_BASE_URL = (
  process.env.E2E_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

function loadAppNamespace() {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const packageJson = JSON.parse(
    readFileSync(resolve(currentDir, '../../../package.json'), 'utf8'),
  ) as { version?: string };
  const envFile = readFileSync(resolve(currentDir, '../../../.env'), 'utf8');
  const namespaceMatch = envFile.match(/^VITE_APP_NAMESPACE=(.+)$/m);
  const baseNamespace = namespaceMatch?.[1]?.trim() || 'novusai-web-saas';
  const appVersion = packageJson.version || '0.0.0';
  const env = process.env.NODE_ENV === 'production' ? 'prod' : 'dev';
  return `${baseNamespace}-${appVersion}-${env}`;
}

const APP_NAMESPACE = loadAppNamespace();

async function fetchTokens(endpoint: AuthEndpoint, payload: LoginPayload) {
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  });

  try {
    const response = await api.post(`/${endpoint}/auth/login`, {
      data: payload,
    });
    expect(response.ok(), `Expected ${endpoint} login API to succeed`).toBe(true);
    const body = (await response.json()) as LoginResponse;
    expect(body.code, `Expected ${endpoint} login code to be 0`).toBe(0);
    expect(body.data?.access_token, 'Expected access token in login response').toBeTruthy();
    return {
      accessToken: body.data?.access_token as string,
      refreshToken: body.data?.refresh_token,
    };
  } finally {
    await api.dispose();
  }
}

export async function seedAuthSession(
  page: Page,
  endpoint: AuthEndpoint,
  tokens: {
    accessToken: string;
    refreshToken?: string;
  },
) {
  await page.addInitScript(
    ({ accessToken, endpoint, namespace, refreshToken }) => {
      const tokenKey =
        endpoint === 'tenant'
          ? `${namespace}_tenant_admin_token`
          : `${namespace}_admin_token`;
      const refreshKey =
        endpoint === 'tenant'
          ? `${namespace}_tenant_admin_refresh_token`
          : `${namespace}_admin_refresh_token`;
      localStorage.setItem(tokenKey, accessToken);
      if (refreshToken) {
        localStorage.setItem(refreshKey, refreshToken);
      }
    },
    {
      accessToken: tokens.accessToken,
      endpoint,
      namespace: APP_NAMESPACE,
      refreshToken: tokens.refreshToken,
    },
  );
}

export async function createAdminSession(
  page: Page,
  credentials: {
    password: string;
    username: string;
  },
) {
  const tokens = await fetchTokens('admin', {
    password: credentials.password,
    username: credentials.username,
  });
  await seedAuthSession(page, 'admin', tokens);
}

export async function createTenantSession(
  page: Page,
  credentials: {
    password: string;
    tenantCode: string;
    username: string;
  },
) {
  const tokens = await fetchTokens('tenant', {
    password: credentials.password,
    tenant_code: credentials.tenantCode,
    username: credentials.username,
  });
  await seedAuthSession(page, 'tenant', tokens);
}
