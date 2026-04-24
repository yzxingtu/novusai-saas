import type { ItemType } from 'ant-design-vue/es/menu';

import type { ComputedRef, Ref } from 'vue';

import type { AgentItem, ChatMessage, InputVariable } from '#/types/ai-chat';

/**
 * Test type: behavioral
 * Verifies: slide-panel header diagnostics stay hidden by default on end-user prefixes and only open when the explicit feature flag is enabled.
 * Mock strategy: API/config edges are mocked, while usePanelHeader menu composition runs real.
 */
import { computed, ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePanelHeader } from '../use-panel-header';

const publicConfigState = {
  platformConfig: { brand: { siteName: 'Test' } } as {
    brand: { siteName: string };
    features?: Record<string, boolean>;
  },
  tenantConfig: null as null | { features?: Record<string, boolean> },
};

vi.mock('#/api/shared/ai-chat', () => ({
  compactChatConversationApi: vi.fn(async () => undefined),
  getChatConversationTimelineApi: vi.fn(async () => []),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: vi.fn(),
  },
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/types/ai-chat', () => ({
  getAgentInputVariables: () => [],
}));

vi.mock('#/utils/error-helpers', () => ({
  getErrorMessage: () => 'failed',
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => publicConfigState,
}));

vi.mock('#/utils/request/app-env', () => ({
  isDevErrorMode: () => false,
}));

function buildOptions(
  overrides: {
    activeConversationId?: null | number;
    apiPrefix?: Ref<string> | string;
  } = {},
) {
  return {
    activeConversationId: ref(overrides.activeConversationId ?? 100),
    agentsWithVarsInConversation: ref([]) as Ref<AgentItem[]>,
    allAgentsVariables: ref({}) as Ref<Record<number, Record<string, string>>>,
    apiPrefix: overrides.apiPrefix ?? '/tenant/ai/chat',
    chatMessages: ref([]) as Ref<ChatMessage[]>,
    clearConversationMemory: vi.fn(async () => true),
    currentConversationAgentName: computed(
      () => 'Agent',
    ) as ComputedRef<string>,
    exportMenuItems: computed(() => [] as ItemType[]),
    fetchConversationMemory: vi.fn(async () => undefined),
    forceRerouteNextTurn: ref(false),
    isPinned: computed(() => false),
    lastMemoryUpdated: ref(null) as Ref<boolean | null | number | string>,
    loadConversationMessages: vi.fn(async () => undefined),
    onOpenMultiVarsEditor: vi.fn(),
    onOpenVarsModal: vi.fn(
      (_vars: InputVariable[], _agentId: number, _agentName: string) =>
        undefined,
    ),
    routing: ref(false),
    selectedAgent: ref(null) as Ref<AgentItem | null>,
    showMemoryPanel: ref(false),
    totalTokensUsed: ref(0),
    unpinAgent: vi.fn(),
  };
}

function itemKeys(items: ItemType[]): string[] {
  return items
    .map((item) => {
      if (!item || typeof item !== 'object' || !('key' in item)) {
        return '';
      }
      return String(item.key ?? '');
    })
    .filter(Boolean);
}

describe('usePanelHeader diagnostics gating', () => {
  beforeEach(() => {
    publicConfigState.platformConfig = { brand: { siteName: 'Test' } };
    publicConfigState.tenantConfig = null;
  });

  it('hides context diagnostics from the default admin menu', () => {
    const header = usePanelHeader(
      buildOptions({ apiPrefix: '/admin/ai/chat' }),
    );

    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'context-diagnostics',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'run-timeline',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'rebuild-context',
    );
  });

  it('hides context diagnostics from the default tenant menu', () => {
    const header = usePanelHeader(buildOptions());

    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'context-diagnostics',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'run-timeline',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'rebuild-context',
    );
  });

  it('hides context diagnostics from the default user menu', () => {
    const header = usePanelHeader(buildOptions({ apiPrefix: '/api/user' }));

    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'context-diagnostics',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'run-timeline',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain(
      'rebuild-context',
    );
  });

  it('shows context diagnostics only when tenant diagnostics are enabled', () => {
    publicConfigState.tenantConfig = {
      features: {
        show_diagnostics: true,
      },
    };

    const header = usePanelHeader(buildOptions());

    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'context-diagnostics',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'run-timeline',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'rebuild-context',
    );
  });

  it('shows context diagnostics only when admin diagnostics are enabled explicitly', () => {
    publicConfigState.platformConfig = {
      brand: { siteName: 'Test' },
      features: {
        show_diagnostics: true,
      },
    };

    const header = usePanelHeader(
      buildOptions({ apiPrefix: '/admin/ai/chat' }),
    );

    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'context-diagnostics',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'run-timeline',
    );
    expect(itemKeys(header.headerMoreMenuItems.value)).toContain(
      'rebuild-context',
    );
  });

  it('keeps the panel header free of per-conversation agent names while surfacing anonymous conversation context', () => {
    const options = buildOptions();
    options.chatMessages.value = [
      { content: 'one', role: 'assistant' },
      { content: 'two', role: 'user' },
    ] as ChatMessage[];
    options.totalTokensUsed.value = 128;
    options.lastMemoryUpdated.value = true;
    options.agentsWithVarsInConversation.value = [
      {
        id: 7,
        name: 'Agent',
      } as AgentItem,
    ];
    options.allAgentsVariables.value = {
      7: { project: 'novus' },
    };

    const header = usePanelHeader(options);

    expect(header.headerConversationSummary.value).toContain(
      '2 common.globalAiChat.messages',
    );
    expect(header.headerConversationSummary.value).toContain(
      '128 common.globalAiChat.tokens',
    );
    expect(header.headerConversationSummary.value).toContain(
      'user.aiChat.varsModal.editVars',
    );
    expect(header.headerConversationSummary.value).not.toContain('Agent');
  });

  it('exposes memory as a direct header action instead of a more-menu item', async () => {
    const options = buildOptions();
    const header = usePanelHeader(options);

    expect(header.showHeaderMemoryButton.value).toBe(true);
    expect(itemKeys(header.headerMoreMenuItems.value)).not.toContain('memory');

    await header.onToggleMemory();

    expect(options.fetchConversationMemory).toHaveBeenCalledTimes(1);
    expect(options.showMemoryPanel.value).toBe(true);

    await header.onToggleMemory();

    expect(options.fetchConversationMemory).toHaveBeenCalledTimes(1);
    expect(options.showMemoryPanel.value).toBe(false);
  });

  it('raises memory attention only while updates exist and the panel is closed', () => {
    const options = buildOptions();
    const header = usePanelHeader(options);

    expect(header.headerMemoryHasAttention.value).toBe(false);

    options.lastMemoryUpdated.value = true;
    expect(header.headerMemoryHasAttention.value).toBe(true);

    options.showMemoryPanel.value = true;
    expect(header.headerMemoryHasAttention.value).toBe(false);
  });
});
