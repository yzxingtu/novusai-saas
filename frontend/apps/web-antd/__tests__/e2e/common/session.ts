// Test type: smoke
// Scope: authenticated Playwright session bootstrap helpers.
import type { APIRequestContext, Page } from '@playwright/test';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { expect, request } from '@playwright/test';

type AuthEndpoint = 'admin' | 'tenant' | 'user';

interface LoginResponse {
  code: number;
  data?: {
    access_token?: string;
    refresh_token?: string;
  };
  message?: string;
}

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));
const API_BASE_URL = (
  process.env.E2E_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

function loadAppNamespace() {
  const packageJson = JSON.parse(
    readFileSync(resolve(CURRENT_DIR, '../../../package.json'), 'utf8'),
  ) as { version?: string };
  const envFile = readFileSync(resolve(CURRENT_DIR, '../../../.env'), 'utf8');
  const namespaceMatch = envFile.match(/^VITE_APP_NAMESPACE=(.+)$/m);
  const baseNamespace = namespaceMatch?.[1]?.trim() || 'novusai-web-saas';
  const appVersion = packageJson.version || '0.0.0';
  const env = process.env.NODE_ENV === 'production' ? 'prod' : 'dev';
  return `${baseNamespace}-${appVersion}-${env}`;
}

const APP_NAMESPACE = loadAppNamespace();

const SECRET_VARIABLES: Partial<Record<AuthEndpoint, string>> = {
  admin: 'DEV_ADMIN_BOOTSTRAP_SECRET',
  tenant: 'DEV_TENANT_BOOTSTRAP_SECRET',
  user: 'DEV_TENANT_USER_BOOTSTRAP_SECRET',
};

const REPO_ROOT = resolve(CURRENT_DIR, '../../../../../..');
const BACKEND_ENV_PATH = resolve(REPO_ROOT, 'backend', '.env');

let backendEnvVars: null | Record<string, string> = null;

function loadBackendEnv() {
  if (backendEnvVars) return backendEnvVars;
  try {
    const contents = readFileSync(BACKEND_ENV_PATH, 'utf8');
    const envValues: Record<string, string> = {};
    for (const line of contents.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) {
        continue;
      }
      const [key, ...valueParts] = trimmed.split('=');
      if (!key) {
        continue;
      }
      envValues[key.trim()] = valueParts.join('=').trim();
    }
    backendEnvVars = envValues;
  } catch {
    backendEnvVars = {};
  }
  return backendEnvVars;
}

export function getBackendEnvValue(name: string) {
  return loadBackendEnv()[name];
}

export function getDevBootstrapSecret(endpoint: AuthEndpoint) {
  const key = SECRET_VARIABLES[endpoint];
  if (!key) {
    return undefined;
  }
  return process.env[key] || getBackendEnvValue(key);
}

async function fetchDevBootstrapTokens(
  endpoint: AuthEndpoint,
  api: APIRequestContext,
) {
  const secret = getDevBootstrapSecret(endpoint);
  if (!secret) {
    throw new Error(
      `Set ${SECRET_VARIABLES[endpoint]} in the environment or backend/.env to run authenticated e2e smoke.`,
    );
  }
  const response = await api.post(`/${endpoint}/auth/dev/bootstrap`, {
    data: {
      bootstrap_secret: secret,
    },
  });
  expect(
    response.ok(),
    `Expected ${endpoint} dev bootstrap API to succeed`,
  ).toBe(true);
  const body = (await response.json()) as LoginResponse;
  expect(body.code, `Expected ${endpoint} dev bootstrap code to be 0`).toBe(0);
  expect(
    body.data?.access_token,
    `Expected ${endpoint} access token in dev bootstrap response`,
  ).toEqual(expect.any(String));
  return {
    accessToken: body.data.access_token as string,
    refreshToken: body.data.refresh_token,
  };
}

async function fetchTokens(endpoint: AuthEndpoint) {
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  });

  try {
    return await fetchDevBootstrapTokens(endpoint, api);
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
      let tokenKey = `${namespace}_admin_token`;
      let refreshKey = `${namespace}_admin_refresh_token`;
      if (endpoint === 'tenant') {
        tokenKey = `${namespace}_tenant_admin_token`;
        refreshKey = `${namespace}_tenant_admin_refresh_token`;
      } else if (endpoint === 'user') {
        tokenKey = `${namespace}_tenant_user_token`;
        refreshKey = `${namespace}_tenant_user_refresh_token`;
      }
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

export async function createAdminSession(page: Page) {
  const tokens = await fetchTokens('admin');
  await seedAuthSession(page, 'admin', tokens);
}

export async function createTenantSession(page: Page) {
  const tokens = await fetchTokens('tenant');
  await seedAuthSession(page, 'tenant', tokens);
}
