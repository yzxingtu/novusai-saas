// Test type: smoke
// Scope: tenant-user Playwright authentication and provisioning helper.
import type { APIRequestContext, Page } from '@playwright/test';

import process from 'node:process';

import { expect, request } from '@playwright/test';

import {
  getBackendEnvValue,
  getDevBootstrapSecret,
  seedAuthSession,
} from './session';

interface UserLoginResponse {
  code: number;
  data?: {
    access_token?: string;
    refresh_token?: string;
  };
  message?: string;
}

interface UserCredentials {
  email: string;
  password: string;
  tenantCode: string;
  username: string;
}

interface TenantUserListResponse {
  code: number;
  data?: {
    items?: Array<{
      id: number;
      username?: null | string;
    }>;
  };
}

interface TenantAgentListResponse {
  code: number;
  data?: {
    items?: Array<{
      execution_mode?: null | string;
      id: number;
      name?: null | string;
      status?: null | string;
    }>;
  };
}

interface TenantAgentPublicationResponse {
  code: number;
  data?: {
    access_type?: null | string;
    enabled_for_users?: boolean;
  };
}

const API_BASE_URL = (
  process.env.E2E_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

const USER_E2E_TENANT_CODE =
  process.env.USER_E2E_TENANT_CODE ||
  getBackendEnvValue('USER_E2E_TENANT_CODE') ||
  getBackendEnvValue('DEV_TENANT_BOOTSTRAP_TENANT_CODE');

function buildEphemeralUserCredentials(): UserCredentials | null {
  if (!USER_E2E_TENANT_CODE) {
    return null;
  }

  const seed = Date.now().toString(36);
  return {
    email: `e2e-user-${seed}@example.com`,
    password: 'NovusaiE2E!123',
    tenantCode: USER_E2E_TENANT_CODE,
    username: `e2e_user_${seed}`,
  };
}

function resolveUserCredentials(): UserCredentials | null {
  return buildEphemeralUserCredentials();
}

export function hasUserCredentials() {
  return Boolean(
    resolveUserCredentials() &&
      USER_E2E_TENANT_CODE &&
      getDevBootstrapSecret('tenant') &&
      getDevBootstrapSecret('user'),
  );
}

async function fetchTenantAdminAccessToken() {
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  });

  try {
    const bootstrapSecret = getDevBootstrapSecret('tenant');
    if (bootstrapSecret) {
      const bootstrapResponse = await api.post('/tenant/auth/dev/bootstrap', {
        data: {
          bootstrap_secret: bootstrapSecret,
        },
      });
      expect(
        bootstrapResponse.ok(),
        'Expected tenant admin bootstrap API to succeed for user e2e provisioning.',
      ).toBe(true);
      const bootstrapBody =
        (await bootstrapResponse.json()) as UserLoginResponse;
      expect(
        bootstrapBody.code,
        'Expected tenant admin bootstrap code to be 0.',
      ).toBe(0);
      expect(
        bootstrapBody.data?.access_token,
        'Expected tenant admin access token in bootstrap response.',
      ).toEqual(expect.any(String));
      return bootstrapBody.data?.access_token as string;
    }

    throw new Error(
      'Set DEV_TENANT_BOOTSTRAP_SECRET to provision user e2e sessions. Legacy tenant login fallback is retired.',
    );
  } finally {
    await api.dispose();
  }
}

async function ensureTenantUserProvisioned(
  credentials: UserCredentials,
  password: string,
) {
  const tenantAdminAccessToken = await fetchTenantAdminAccessToken();
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      Authorization: `Bearer ${tenantAdminAccessToken}`,
      'Content-Type': 'application/json',
    },
  });

  try {
    const createResponse = await api.post('/tenant/users', {
      data: {
        email: credentials.email,
        is_active: true,
        nickname: credentials.username,
        password,
        username: credentials.username,
      },
    });

    if (createResponse.ok()) {
      await ensureTenantUserAccessibleAgent(api);
      return;
    }

    const listResponse = await api.get('/tenant/users', {
      params: {
        page: 1,
        search: credentials.username,
        size: 20,
      },
    });
    expect(
      listResponse.ok(),
      'Expected tenant user list API to succeed after duplicate create failure.',
    ).toBe(true);
    const listBody = (await listResponse.json()) as TenantUserListResponse;
    const existingUser = listBody.data?.items?.find(
      (item) => item.username === credentials.username,
    );
    expect(
      existingUser?.id,
      'Expected to resolve an existing tenant user after duplicate create failure.',
    ).toEqual(expect.any(Number));

    const resetResponse = await api.put(
      `/tenant/users/${existingUser!.id}/reset-password`,
      {
        data: {
          new_password: password,
        },
      },
    );
    expect(
      resetResponse.ok(),
      'Expected tenant user password reset API to succeed for user e2e provisioning.',
    ).toBe(true);
    await ensureTenantUserAccessibleAgent(api);
    return;
  } finally {
    await api.dispose();
  }
}

async function ensureTenantUserAccessibleAgent(api: APIRequestContext) {
  const agentListResponse = await api.get('/tenant/ai/agents', {
    params: {
      'filter[status][eq]': 'published',
      'page[size]': 100,
      sort: '-updated_at',
    },
  });
  expect(
    agentListResponse.ok(),
    'Expected tenant agent list API to succeed for user e2e provisioning.',
  ).toBe(true);
  const agentListBody =
    (await agentListResponse.json()) as TenantAgentListResponse;
  const items = agentListBody.data?.items ?? [];
  const candidate =
    items.find(
      (item) =>
        item.id > 0 &&
        item.status === 'published' &&
        item.execution_mode !== 'router',
    ) ??
    items.find((item) => item.id > 0 && item.status === 'published');

  expect(
    candidate?.id,
    'Expected at least one published tenant agent for user e2e provisioning.',
  ).toEqual(expect.any(Number));

  const publicationResponse = await api.get(
    `/tenant/ai/agents/${candidate!.id}/publication`,
  );
  expect(
    publicationResponse.ok(),
    'Expected tenant publication API to succeed for user e2e provisioning.',
  ).toBe(true);
  const publicationBody =
    (await publicationResponse.json()) as TenantAgentPublicationResponse;
  if (
    publicationBody.data?.enabled_for_users &&
    publicationBody.data?.access_type === 'all_users'
  ) {
    return;
  }

  const updateResponse = await api.put(
    `/tenant/ai/agents/${candidate!.id}/publication`,
    {
      data: {
        access_type: 'all_users',
        enabled_for_users: true,
        org_node_ids: null,
        tenant_user_ids: null,
        tenant_user_role_ids: null,
      },
    },
  );
  expect(
    updateResponse.ok(),
    'Expected tenant agent publication update to enable user e2e access.',
  ).toBe(true);
}

async function loginUser(
  credentials: UserCredentials,
) {
  const api = await request.newContext({
    baseURL: API_BASE_URL,
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  });

  try {
    await ensureTenantUserProvisioned(credentials, credentials.password);

    const bootstrapSecret = getDevBootstrapSecret('user');
    if (bootstrapSecret) {
      const bootstrapResponse = await api.post('/api/user/auth/dev/bootstrap', {
        data: {
          bootstrap_secret: bootstrapSecret,
          tenant_code: credentials.tenantCode,
          username: credentials.username,
        },
      });
      expect(
        bootstrapResponse.ok(),
        'Expected tenant user bootstrap API to succeed after provisioning.',
      ).toBe(true);
      const bootstrapBody =
        (await bootstrapResponse.json()) as UserLoginResponse;
      expect(
        bootstrapBody.code,
        'Expected tenant user bootstrap code to be 0.',
      ).toBe(0);
      expect(
        bootstrapBody.data?.access_token,
        'Expected tenant user access token in bootstrap response.',
      ).toEqual(expect.any(String));
      return {
        accessToken: bootstrapBody.data.access_token as string,
        refreshToken: bootstrapBody.data.refresh_token,
      };
    }

    throw new Error(
      'Set DEV_TENANT_USER_BOOTSTRAP_SECRET to run user e2e smoke. Legacy user login fallback is retired.',
    );
  } finally {
    await api.dispose();
  }
}

export async function loginAsUser(page: Page) {
  const credentials = resolveUserCredentials();
  if (!credentials) {
    throw new Error(
      'Set USER_E2E_TENANT_CODE or backend DEV_TENANT_BOOTSTRAP_TENANT_CODE to run user e2e smoke.',
    );
  }

  await page.addInitScript(() => {
    window.sessionStorage.setItem('__novusai_e2e_domain_type', 'tenant');
  });

  const tokens = await loginUser(credentials);
  await seedAuthSession(page, 'user', tokens);
}
