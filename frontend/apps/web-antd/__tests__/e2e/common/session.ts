import type { APIRequestContext, Page } from '@playwright/test';

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { expect, request } from '@playwright/test';

type AuthEndpoint = 'admin' | 'tenant' | 'user';

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

async function tryDevBootstrap(endpoint: AuthEndpoint, api: APIRequestContext) {
  const secret = getDevBootstrapSecret(endpoint);
  if (!secret) return null;
  const response = await api.post(`/${endpoint}/auth/dev/bootstrap`, {
    data: {
      bootstrap_secret: secret,
    },
  });
  if (!response.ok()) return null;
  const body = (await response.json()) as LoginResponse;
  if (body.code !== 0 || !body.data?.access_token) return null;
  return {
    accessToken: body.data.access_token as string,
    refreshToken: body.data.refresh_token,
  };
}

async function fetchTokens(
  endpoint: AuthEndpoint,
  payload: LoginPayload | null,
) {
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  });

  try {
    const bootstrapTokens = await tryDevBootstrap(endpoint, api);
    if (bootstrapTokens) {
      return bootstrapTokens;
    }

    if (!payload) {
      throw new Error(
        `No credentials provided for ${endpoint} login and bootstrap is unavailable.`,
      );
    }

    const response = await api.post(`/${endpoint}/auth/login`, {
      data: payload,
    });
    expect(response.ok(), `Expected ${endpoint} login API to succeed`).toBe(
      true,
    );
    const body = (await response.json()) as LoginResponse;
    expect(body.code, `Expected ${endpoint} login code to be 0`).toBe(0);
    expect(
      body.data?.access_token,
      'Expected access token in login response',
    ).toBeTruthy();
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
          : endpoint === 'user'
            ? `${namespace}_tenant_user_token`
            : `${namespace}_admin_token`;
      const refreshKey =
        endpoint === 'tenant'
          ? `${namespace}_tenant_admin_refresh_token`
          : endpoint === 'user'
            ? `${namespace}_tenant_user_refresh_token`
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
  credentials?: {
    password: string;
    username: string;
  },
) {
  const payload = credentials
    ? {
        password: credentials.password,
        username: credentials.username,
      }
    : null;
  const tokens = await fetchTokens('admin', payload);
  await seedAuthSession(page, 'admin', tokens);
}

export async function createTenantSession(
  page: Page,
  credentials?: {
    password: string;
    tenantCode: string;
    username: string;
  },
) {
  const payload = credentials
    ? {
        password: credentials.password,
        tenant_code: credentials.tenantCode,
        username: credentials.username,
      }
    : null;
  const tokens = await fetchTokens('tenant', payload);
  await seedAuthSession(page, 'tenant', tokens);
}
