// Test type: behavioral
// Verifies: auth mappers preserve account and tenant-plan AI availability fields, and logout uses endpoint-scoped TokenStorage tokens.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TokenStorage } from '#/store/shared/token-storage';

const requestMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('#/utils/request', () => ({
  baseRequestClient: {
    post: requestMocks.post,
  },
  requestClient: {
    get: requestMocks.get,
    post: requestMocks.post,
  },
}));

vi.mock('@vben/stores', () => ({
  useAccessStore: () => ({ accessToken: 'token' }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('auth AI availability mapping', () => {
  beforeEach(() => {
    localStorage.clear();
    requestMocks.get.mockReset();
    requestMocks.post.mockReset();
    TokenStorage.init('auth_test');
  });

  it('keeps platform admin account AI disabled from /admin/auth/me', async () => {
    requestMocks.get.mockResolvedValueOnce({
      ai_enabled: false,
      avatar: null,
      email: 'admin@example.com',
      id: 1,
      is_super: true,
      permissions: ['*'],
      username: 'admin',
    });

    const { getAdminInfoApi } = await import('../admin/auth');
    const user = await getAdminInfoApi();

    expect(user.accountAIEnabled).toBe(false);
    expect(user.tenantPlanAIEnabled).toBe(true);
    expect(user.aiChatEnabled).toBe(false);
  });

  it('keeps tenant plan AI disabled reason from /tenant/auth/me', async () => {
    requestMocks.get.mockResolvedValueOnce({
      ai_enabled: true,
      ai_unavailable_reason: 'tenant_plan_ai_disabled',
      avatar: null,
      effective_ai_enabled: false,
      email: 'owner@example.com',
      id: 7,
      permissions: ['agent_chat:chat'],
      tenant_ai_enabled: false,
      tenant_id: 5,
      tenant_name: 'Tenant',
      username: 'owner',
    });

    const { getTenantAdminInfoApi } = await import('../tenant/auth');
    const user = await getTenantAdminInfoApi();

    expect(user.accountAIEnabled).toBe(true);
    expect(user.tenantPlanAIEnabled).toBe(false);
    expect(user.aiChatEnabled).toBe(false);
    expect(user.aiUnavailableReason).toBe('tenant_plan_ai_disabled');
  });

  it('preserves tenant permissions from /tenant/auth/me', async () => {
    requestMocks.get.mockResolvedValueOnce({
      avatar: null,
      email: 'owner@example.com',
      id: 7,
      permissions: ['menu:tenant.ai.chat', 'agent_chat:chat'],
      tenant_id: 5,
      tenant_name: 'Tenant',
      username: 'owner',
    });

    const { getTenantAdminInfoApi } = await import('../tenant/auth');
    const user = await getTenantAdminInfoApi();

    expect(user.permissions).toEqual([
      'menu:tenant.ai.chat',
      'agent_chat:chat',
    ]);
  });

  it('does not synthesize empty tenant permissions when /tenant/auth/me omits them', async () => {
    requestMocks.get.mockResolvedValueOnce({
      avatar: null,
      email: 'owner@example.com',
      id: 7,
      tenant_id: 5,
      tenant_name: 'Tenant',
      username: 'owner',
    });

    const { getTenantAdminInfoApi } = await import('../tenant/auth');
    const user = await getTenantAdminInfoApi();

    expect(Object.hasOwn(user, 'permissions')).toBe(false);
  });

  it('uses endpoint-scoped TokenStorage tokens for logout authorization headers', async () => {
    TokenStorage.setToken('admin', 'admin-token');
    TokenStorage.setToken('tenant', 'tenant-token');
    TokenStorage.setToken('user', 'user-token');
    requestMocks.post.mockResolvedValue({});

    const { adminLogoutApi } = await import('../admin/auth');
    const { tenantLogoutApi } = await import('../tenant/auth');
    const { userLogoutApi } = await import('../user/auth');

    await adminLogoutApi();
    await tenantLogoutApi();
    await userLogoutApi();

    expect(requestMocks.post.mock.calls).toEqual([
      [
        '/admin/auth/logout',
        undefined,
        { headers: { Authorization: 'Bearer admin-token' } },
      ],
      [
        '/tenant/auth/logout',
        undefined,
        { headers: { Authorization: 'Bearer tenant-token' } },
      ],
      [
        '/api/user/auth/logout',
        undefined,
        { headers: { Authorization: 'Bearer user-token' } },
      ],
    ]);
  });
});
