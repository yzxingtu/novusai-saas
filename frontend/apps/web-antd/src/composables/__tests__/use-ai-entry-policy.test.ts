// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: route meta AI policy only controls chat-entry visibility.
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

describe('useAIEntryPolicy', () => {
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

  it('keeps AI enabled by default', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-entry-policy');

    let policy!: ReturnType<typeof module.useAIEntryPolicy>;
    scope.run(() => {
      policy = module.useAIEntryPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('enabled');

    scope.stop();
  });

  it('disables AI when route meta explicitly disables the entry', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-entry-policy');
    mockRefs.routeMeta.value = {
      ai: {
        mode: 'disabled',
      },
    };

    let policy!: ReturnType<typeof module.useAIEntryPolicy>;
    scope.run(() => {
      policy = module.useAIEntryPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(false);
    expect(policy.entryDisabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('disabled');

    scope.stop();
  });

  it('disables AI when chat permission is missing', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-entry-policy');
    mockRefs.canChat.value = false;

    let policy!: ReturnType<typeof module.useAIEntryPolicy>;
    scope.run(() => {
      policy = module.useAIEntryPolicy();
    });
    await nextTick();

    expect(policy.aiEnabled.value).toBe(false);
    expect(policy.effectiveMode.value).toBe('disabled');

    scope.stop();
  });
});
