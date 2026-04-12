// @vitest-environment happy-dom
import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  canChat: { value: true },
  canRoute: { value: true },
  canViewHistory: { value: true },
  resource: { value: 'admin_agent_chat' },
  routeMeta: { value: {} as Record<string, unknown> },
  routePath: { value: '/admin/ai/agents' },
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get meta() {
      return mockRefs.routeMeta.value;
    },
    get path() {
      return mockRefs.routePath.value;
    },
  }),
}));

vi.mock('../use-ai-permission', () => ({
  useAIPermission: () => ({
    canChat: mockRefs.canChat,
    canRoute: mockRefs.canRoute,
    canViewHistory: mockRefs.canViewHistory,
    resource: mockRefs.resource,
  }),
}));

vi.mock('#/components/business/ai-runtime/page-key-utils', () => ({
  normalizePageKey: (value?: string) =>
    String(value ?? '')
      .replace(/^\//, '')
      .replaceAll('/', '.'),
}));

vi.mock('#/utils/ai-page-capabilities', () => ({
  normalizeCapabilityKeys: (value?: string | string[]) => {
    if (Array.isArray(value)) return value;
    return value ? [value] : [];
  },
  normalizeOperationNames: (value?: string | string[]) => {
    if (Array.isArray(value)) return value;
    return value ? [value] : [];
  },
  normalizePageAIMode: (mode?: string, fallback = 'operate') =>
    mode === 'disabled' || mode === 'context_only' || mode === 'operate'
      ? mode
      : fallback,
}));

describe('useCurrentPageAIPolicy', () => {
  beforeEach(() => {
    mockRefs.canChat.value = true;
    mockRefs.canRoute.value = true;
    mockRefs.canViewHistory.value = true;
    mockRefs.resource.value = 'admin_agent_chat';
    mockRefs.routePath.value = '/admin/ai/agents';
    mockRefs.routeMeta.value = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('applies route meta policy and updates global execution policy', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-page-policy');
    mockRefs.routeMeta.value = {
      ai: {
        disabledCapabilities: ['search'],
        disabledOperations: 'delete_record',
        mode: 'context_only',
        pageContextKey: '/custom/page',
      },
    };

    let policy!: ReturnType<typeof module.useCurrentPageAIPolicy>;
    scope.run(() => {
      policy = module.useCurrentPageAIPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(true);
    expect(policy.pageDisabled.value).toBe(false);
    expect(policy.pageMode.value).toBe('context_only');
    expect(policy.effectiveMode.value).toBe('context_only');
    expect(policy.pageContextKey.value).toBe('custom.page');
    expect(module.currentPageAIExecutionPolicy.value).toEqual({
      disabledCapabilities: ['search'],
      disabledOperations: ['delete_record'],
      mode: 'context_only',
      pageContextKey: 'custom.page',
    });

    scope.stop();
  });

  it('disables AI when chat permission is missing and falls back to route path key', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-page-policy');
    mockRefs.canChat.value = false;
    mockRefs.routePath.value = '/tenant/ai/chat';
    mockRefs.routeMeta.value = {
      ai: {
        mode: 'operate',
      },
    };

    let policy!: ReturnType<typeof module.useCurrentPageAIPolicy>;
    scope.run(() => {
      policy = module.useCurrentPageAIPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(false);
    expect(policy.effectiveMode.value).toBe('disabled');
    expect(policy.pageContextKey.value).toBe('tenant.ai.chat');

    scope.stop();
  });
});
