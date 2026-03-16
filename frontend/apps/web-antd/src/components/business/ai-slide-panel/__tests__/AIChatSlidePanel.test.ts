/**
 * AIChatSlidePanel component render tests: confirmCountdown in real component.
 * AIChatSlidePanel 组件挂载测试：倒计时文案在真实组件中渲染。
 *
 * 与 countdown-display.test.ts（纯逻辑单测）互补，覆盖“组件渲染层”。
 */
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';

// --- Store mock: controlled pendingPageOps for countdown assertion ---
const visible = ref(true);
const pendingPageOpsValue = ref<
  Array<{
    invokeId: string;
    operationLabel: string;
    operationDescription: string;
    resolved: boolean;
    startedAt: number;
  }>
>([]);
const resolvePageOp = vi.fn();

vi.mock('#/store', () => ({
  useAIPanelStore: () => ({
    get visible() {
      return visible.value;
    },
    get pendingPageOps() {
      return pendingPageOpsValue.value;
    },
    resolvePageOp,
    pinnedAgentId: ref(null),
    pinnedAgentName: ref(null),
  }),
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => ({
    platformConfig: { brand: { siteName: 'Test' } },
    tenantConfig: null,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string, params?: { seconds?: number }) =>
    key === 'shared.pageOperation.confirmCountdown' && params?.seconds !== undefined
      ? `${params.seconds}s remaining`
      : key,
}));

vi.mock('#/components/business/ai-chat-panel/use-ai-chat', async () => {
  const vue = await import('vue');
  return {
  useAIChat: () => ({
      agents: vue.ref([]),
      selectedAgentId: vue.ref(null),
      selectedAgent: vue.computed(() => null),
      loadAgents: vi.fn(),
      conversations: vue.ref([]),
      conversationsLoading: vue.ref(false),
      activeConversationId: vue.ref(null),
      loadConversations: vi.fn(),
      startNewConversation: vi.fn(),
      deleteConversation: vi.fn(),
      loadConversationMessages: vi.fn(),
      chatMessages: vue.ref([]),
      inputMessage: vue.ref(''),
      sending: vue.ref(false),
      streaming: vue.ref(false),
      messagesContainer: vue.ref(null),
      sendMessage: vi.fn(),
      stopGeneration: vi.fn(),
      handleMessagesScroll: vi.fn(),
      showScrollToBottom: vue.ref(false),
      showScrollToTop: vue.ref(false),
      scrollToBottom: vi.fn(),
      scrollToTop: vi.fn(),
      copyMessage: vi.fn(),
      handleInputKeyDown: vi.fn(),
      cleanup: vi.fn(),
      pendingAttachments: vue.ref([]),
      uploading: vue.ref(false),
      fileInput: vue.ref(null),
      chatAcceptAttribute: vue.ref(''),
      handleFileSelect: vi.fn(),
      handlePaste: vi.fn(),
      handleDrop: vi.fn(),
      handleDragOver: vi.fn(),
      removePendingAttachment: vi.fn(),
      confirmAction: vi.fn(),
      rejectAction: vi.fn(),
      confirmConsent: vi.fn(),
      rejectConsent: vi.fn(),
      trustSession: vue.ref(false),
      clickActionButton: vi.fn(),
      regenerateMessage: vi.fn(),
      editAndResend: vi.fn(),
      retryLastMessage: vi.fn(),
      clearConversationMemory: vi.fn(),
      clearingMemory: vue.ref(false),
      fetchConversationMemory: vi.fn(),
      memoryState: vue.ref(null),
      memoryLoading: vue.ref(false),
      lastMemoryUpdated: vue.ref(false),
      exportAsMarkdown: vi.fn(),
      exportAsPlainText: vi.fn(),
      totalTokensUsed: vue.ref(0),
      supportsVision: vue.ref(false),
      agentKBBindings: vue.ref({}),
      loadAgentKBBindings: vi.fn(),
      allAgentsVariables: vue.ref({}),
      agentsWithVarsInConversation: vue.ref([]),
      ensureAgentVarsLoaded: vi.fn(),
      applyVariables: vi.fn(),
    }),
  };
});

vi.mock('../use-agent-router', () => ({
  useAgentRouter: () => ({
    routing: ref(false),
    routeMessage: vi.fn(),
  }),
}));

vi.mock('#/composables/use-modal-detector', () => ({
  useModalDetector: () => ({ modalState: {} }),
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => null,
}));

vi.mock('#/composables/use-page-screenshot', () => ({
  usePageScreenshot: () => ({ capture: vi.fn(), capturing: ref(false) }),
}));

vi.mock('#/composables/use-form-state-tracker', () => ({
  formStateTracker: { track: vi.fn(), untrack: vi.fn() },
}));

vi.mock('../page-context-registry', () => ({
  resolvePageContext: () => null,
  pageContextVersion: ref(0),
}));

vi.mock('../page-operation-registry', () => ({
  listPageOperations: () => [],
  pageOperationVersion: ref(0),
}));

describe('AIChatSlidePanel (component mount)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000_000_000);
    visible.value = true;
    pendingPageOpsValue.value = [];
    resolvePageOp.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders confirmCountdown when pending op exists', async () => {
    const startedAt = 1_000_000_000_000; // same as fake now
    pendingPageOpsValue.value = [
      {
        invokeId: 'op-1',
        operationLabel: 'Replace Content',
        operationDescription: 'Replace content in editor',
        resolved: false,
        startedAt,
      },
    ];

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          IconifyIcon: true,
          ChatMessageItem: true,
          Modal: true,
          Spin: true,
          Dropdown: true,
          Menu: true,
          Popover: true,
          Tooltip: true,
          Input: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    // Panel is teleported to body; confirmCountdown should be visible
    const panel = document.querySelector('[data-ai-panel]');
    expect(panel).toBeTruthy();
    expect(panel?.textContent).toMatch(/60s remaining|60/);
  });

  it('countdown decrements over time and stays >= 0', async () => {
    const base = 1_000_000_000_000;
    pendingPageOpsValue.value = [
      {
        invokeId: 'op-1',
        operationLabel: 'Replace',
        operationDescription: '',
        resolved: false,
        startedAt: base,
      },
    ];

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          IconifyIcon: true,
          ChatMessageItem: true,
          Modal: true,
          Spin: true,
          Dropdown: true,
          Menu: true,
          Popover: true,
          Tooltip: true,
          Input: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    let panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/60/);

    // Advance 5s (countdown interval ticks every 1s, we need 5 ticks)
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(1000);
      await wrapper.vm.$nextTick();
    }
    panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/55/);

    // Advance to 60s+: countdown should show 0, not negative
    vi.advanceTimersByTime(60_000);
    await wrapper.vm.$nextTick();
    panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/0s remaining|0/);

    wrapper.unmount();
  });
});
