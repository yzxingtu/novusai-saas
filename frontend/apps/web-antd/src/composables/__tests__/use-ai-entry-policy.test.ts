// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: route meta AI policy only controls chat-entry visibility.
// Mock strategy: permission and route refs are mocked; policy computation runs real.
import { effectScope, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createPinia, setActivePinia } from 'pinia';

const mockRefs = vi.hoisted(() => ({
  canChat: { value: true },
  canRoute: { value: true },
  canViewHistory: { value: true },
  resource: { value: 'admin_agent_chat' },
  routeMeta: { value: {} as Record<string, unknown> },
  routePath: { value: '/admin/dashboard' },
  userStore: { userInfo: null as null | Record<string, unknown> },
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

vi.mock('@vben/stores', () => ({
  useUserStore: () => mockRefs.userStore,
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
    setActivePinia(createPinia());
    mockRefs.canChat.value = true;
    mockRefs.canRoute.value = true;
    mockRefs.canViewHistory.value = true;
    mockRefs.resource.value = 'admin_agent_chat';
    mockRefs.routePath.value = '/admin/dashboard';
    mockRefs.routeMeta.value = {};
    mockRefs.userStore.userInfo = null;
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
    expect(policy.commandBarEnabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('disabled');
    expect(policy.aiUnavailableReason.value).toBe('route_disabled');

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
    expect(policy.commandBarEnabled.value).toBe(true);
    expect(policy.effectiveMode.value).toBe('disabled');
    expect(policy.aiUnavailableReason.value).toBe('permission_missing');

    scope.stop();
  });

  it('keeps command bar available when account AI is disabled', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-entry-policy');
    mockRefs.userStore.userInfo = {
      accountAIEnabled: false,
      aiChatEnabled: false,
      aiUnavailableReason: 'account_ai_disabled',
    };

    let policy!: ReturnType<typeof module.useAIEntryPolicy>;
    scope.run(() => {
      policy = module.useAIEntryPolicy();
    });
    await nextTick();

    expect(policy.commandBarEnabled.value).toBe(true);
    expect(policy.aiChatEnabled.value).toBe(false);
    expect(policy.aiUnavailableReason.value).toBe('account_disabled');

    scope.stop();
  });

  it('maps tenant effective AI fields from user info', async () => {
    const scope = effectScope();
    const module = await import('../use-ai-entry-policy');
    mockRefs.routePath.value = '/tenant/dashboard';
    mockRefs.userStore.userInfo = {
      accountAIEnabled: true,
      aiChatEnabled: false,
      aiUnavailableReason: 'tenant_plan_ai_disabled',
      tenantPlanAIEnabled: false,
    };

    let policy!: ReturnType<typeof module.useAIEntryPolicy>;
    scope.run(() => {
      policy = module.useAIEntryPolicy();
    });
    await nextTick();

    expect(policy.commandBarEnabled.value).toBe(true);
    expect(policy.accountAIEnabled.value).toBe(true);
    expect(policy.tenantPlanAIEnabled.value).toBe(false);
    expect(policy.aiChatEnabled.value).toBe(false);
    expect(policy.aiUnavailableReason.value).toBe('tenant_plan_disabled');

    scope.stop();
  });
});
