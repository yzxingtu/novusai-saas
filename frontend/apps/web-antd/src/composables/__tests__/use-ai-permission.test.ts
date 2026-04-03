import { describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  hasAccessByCodes: vi.fn(),
  routePath: { value: '/admin/ai/agents' },
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get path() {
      return mockRefs.routePath.value;
    },
  }),
}));

vi.mock('#/utils/access', () => ({
  useAccess: () => ({
    hasAccessByCodes: mockRefs.hasAccessByCodes,
  }),
}));

describe('useAIPermission', () => {
  it('uses admin permission resource for admin routes', async () => {
    const { useAIPermission } = await import('../use-ai-permission');

    mockRefs.routePath.value = '/admin/ai/agents';
    mockRefs.hasAccessByCodes.mockImplementation(
      (codes: string[]) => codes[0]?.startsWith('admin_agent_chat:') ?? false,
    );

    const permissions = useAIPermission();

    expect(permissions.resource.value).toBe('admin_agent_chat');
    expect(permissions.canChat.value).toBe(true);
    expect(permissions.canViewHistory.value).toBe(true);
    expect(permissions.canRoute.value).toBe(true);
  });

  it('uses tenant/user permission resource for non-admin routes', async () => {
    const { useAIPermission } = await import('../use-ai-permission');

    mockRefs.routePath.value = '/tenant/ai/chat';
    mockRefs.hasAccessByCodes.mockImplementation(
      (codes: string[]) => codes[0] === 'agent_chat:conversations',
    );

    const permissions = useAIPermission();

    expect(permissions.resource.value).toBe('agent_chat');
    expect(permissions.canChat.value).toBe(false);
    expect(permissions.canViewHistory.value).toBe(true);
    expect(permissions.canRoute.value).toBe(false);
  });
});
