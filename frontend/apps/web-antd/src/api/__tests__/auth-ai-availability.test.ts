// Test type: structural
// Verifies: auth mappers preserve account and tenant-plan AI availability fields.
import { describe, expect, it, vi } from 'vitest';

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
    expect(user.aiEnabled).toBe(false);
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
});
