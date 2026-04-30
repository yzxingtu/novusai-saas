// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: route meta AI policy only controls chat-entry visibility after page awareness retirement.
// Mock strategy: permission and route refs are mocked; policy computation runs real.
import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockRefs = vi.hoisted(() => ({
  canChat: { value: true },
  canRoute: { value: true },
  canViewHistory: { value: true },
  resource: { value: 'admin_agent_chat' },
  routeMeta: { value: {} as Record<string, unknown> },
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get meta() {
      return mockRefs.routeMeta.value;
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

describe('useCurrentPageAIPolicy', () => {
  beforeEach(() => {
    mockRefs.canChat.value = true;
    mockRefs.canRoute.value = true;
    mockRefs.canViewHistory.value = true;
    mockRefs.resource.value = 'admin_agent_chat';
    mockRefs.routeMeta.value = {};
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('keeps AI enabled by default and records an enabled global policy', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-page-policy');

    let policy!: ReturnType<typeof module.useCurrentPageAIPolicy>;
    scope.run(() => {
      policy = module.useCurrentPageAIPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('enabled');
    expect(module.currentPageAIExecutionPolicy.value).toEqual({
      mode: 'enabled',
    });
    expect(module.currentRouteAISecurityPolicy.value).toEqual({
      enabled: true,
      confirmActionKinds: [],
      disabledActionKinds: [],
    });

    scope.stop();
  });

  it('disables AI when route meta explicitly disables the entry', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-page-policy');
    mockRefs.routeMeta.value = {
      ai: {
        mode: 'disabled',
      },
    };

    let policy!: ReturnType<typeof module.useCurrentPageAIPolicy>;
    scope.run(() => {
      policy = module.useCurrentPageAIPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(false);
    expect(policy.pageDisabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('disabled');
    expect(module.currentPageAIExecutionPolicy.value).toEqual({
      mode: 'disabled',
    });

    scope.stop();
  });

  it('disables AI when chat permission is missing', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-page-policy');
    mockRefs.canChat.value = false;

    let policy!: ReturnType<typeof module.useCurrentPageAIPolicy>;
    scope.run(() => {
      policy = module.useCurrentPageAIPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(false);
    expect(policy.effectiveMode.value).toBe('disabled');
    expect(module.currentRouteAISecurityPolicy.value.enabled).toBe(false);

    scope.stop();
  });
});
