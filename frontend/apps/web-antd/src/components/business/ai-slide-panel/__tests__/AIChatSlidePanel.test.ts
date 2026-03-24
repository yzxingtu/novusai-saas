// @vitest-environment happy-dom
/**
 * AIChatSlidePanel component render tests: confirmCountdown in real component.
 * AIChatSlidePanel 组件挂载测试：倒计时文案在真实组件中渲染。
 *
 * 与 countdown-display.test.ts（纯逻辑单测）互补，覆盖“组件渲染层”。
 */
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, reactive, ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';

// Store mock for countdown assertions / 用于倒计时断言的 store mock
const visible = ref(true);
const docked = ref(true);
const minimized = ref(false);
const mode = ref<'full' | 'panel'>('panel');
const panelWidth = ref(460);
const selectedAgentIdValue = ref<null | number>(1);
const supportsVisionValue = ref(false);
const activeConversationIdValue = ref<null | number>(null);
const inputMessageValue = ref('');
const pendingAttachmentsValue = ref<Array<{ type: string }>>([]);
const pageContextValue = ref<null | {
  page_data?: Record<string, unknown>;
  page_key: string;
  page_title: string;
}>(null);
const pageOperationsValue = ref<
  Array<{
    description?: string;
    label: string;
    name: string;
    params?: Record<string, unknown>;
    readonly: boolean;
  }>
>([]);
const routeMessageMock = vi.fn();
const sendMessageMock = vi.fn();
const startNewConversationMock = vi.fn();
const deleteConversationMock = vi.fn();
const loadConversationMessagesMock = vi.fn();
const loadConversationsMock = vi.fn();
const loadAgentsMock = vi.fn();
const updateConversationTitleMock = vi.fn();
const fetchConversationMemoryMock = vi.fn();
const clearConversationMemoryMock = vi.fn();
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
const antMessageMocks = vi.hoisted(() => ({
  error: vi.fn(),
  warning: vi.fn(),
}));

let aiPanelStore: ReturnType<typeof createAIPanelStore>;

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => {
  const TextArea = defineComponent({
    name: 'TextAreaStub',
    props: {
      disabled: {
        default: false,
        type: Boolean,
      },
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['keydown', 'paste', 'update:value'],
    template: `
      <textarea
        data-testid="ai-chat-input"
        :disabled="disabled"
        :value="value"
        @input="$emit('update:value', $event.target.value)"
        @keydown="$emit('keydown', $event)"
        @paste="$emit('paste', $event)"
      />
    `,
  });

  const Input = Object.assign(
    defineComponent({
      name: 'InputStub',
      props: {
        disabled: {
          default: false,
          type: Boolean,
        },
        value: {
          default: '',
          type: String,
        },
      },
      emits: ['update:value'],
      template: `
        <input
          :disabled="disabled"
          :value="value"
          @input="$emit('update:value', $event.target.value)"
        />
      `,
    }),
    { TextArea },
  );

  const Dropdown = defineComponent({
    name: 'DropdownStub',
    template:
      '<div class="dropdown-stub"><slot /><slot name="overlay" /></div>',
  });

  const Menu = defineComponent({
    name: 'MenuStub',
    props: {
      items: {
        default: () => [],
        type: Array,
      },
    },
    template: '<div class="menu-stub"></div>',
  });

  const Modal = defineComponent({
    name: 'ModalStub',
    props: {
      open: {
        default: false,
        type: Boolean,
      },
    },
    emits: ['update:open'],
    template: '<div v-if="open" class="modal-stub"><slot /></div>',
  });

  const Popover = defineComponent({
    name: 'PopoverStub',
    template: '<div class="popover-stub"><slot /><slot name="content" /></div>',
  });

  const Spin = defineComponent({
    name: 'SpinStub',
    template: '<div class="spin-stub"><slot /></div>',
  });

  const Tooltip = defineComponent({
    name: 'TooltipStub',
    template: '<div class="tooltip-stub"><slot /></div>',
  });

  return {
    Dropdown,
    Input,
    Menu,
    Modal,
    Popover,
    Spin,
    Tooltip,
    message: antMessageMocks,
  };
});

function createAIPanelStore() {
  const store = reactive({
    clearResolvedPageOps: vi.fn(),
    close: vi.fn(() => {
      store.visible = false;
    }),
    consumePendingAgentId: vi.fn(() => null),
    dispatchToolCall: vi.fn(),
    docked: true,
    hasUnread: false,
    markUnread: vi.fn(),
    minimize: vi.fn(() => {
      store.minimized = true;
      store.visible = false;
    }),
    minimized: false,
    mode: 'panel' as 'full' | 'panel',
    open: vi.fn(() => {
      store.visible = true;
    }),
    panelWidth: 460,
    pendingPageOps: [] as typeof pendingPageOpsValue.value,
    pinnedAgentId: null as null | number,
    pinnedAgentName: null as null | string,
    resetConversation: vi.fn(),
    resolvePageOp,
    restore: vi.fn(() => {
      store.minimized = false;
      store.visible = true;
    }),
    setConversation: vi.fn(),
    toggleDock: vi.fn(),
    toggleMode: vi.fn(),
    togglePin: vi.fn(),
    unpinAgent: vi.fn(() => {
      store.pinnedAgentId = null;
      store.pinnedAgentName = null;
    }),
    visible: true,
  });
  return store;
}

vi.mock('#/store', () => ({
  useAIPanelStore: () => aiPanelStore,
}));

vi.mock('#/store/shared/public-config', () => ({
  usePublicConfigStore: () => ({
    platformConfig: { brand: { siteName: 'Test' } },
    tenantConfig: null,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string, params?: { seconds?: number }) =>
    key === 'shared.pageOperation.confirmCountdown' &&
    params?.seconds !== undefined
      ? `${params.seconds}s remaining`
      : key,
}));

vi.mock('#/components/business/ai-chat-panel/use-ai-chat', async () => {
  const vue = await import('vue');
  const agents = vue.ref([
    {
      id: 1,
      name: 'Agent One',
      avatar: null,
      description: null,
      status: 'published',
      tenant_id: 1,
      model_capabilities: {
        supports_vision: true,
        max_image_count: 5,
        max_image_size_mb: 10,
      },
      input_variables: [],
    },
    {
      id: 2,
      name: 'Agent Two',
      avatar: null,
      description: null,
      status: 'published',
      tenant_id: 1,
      model_capabilities: {
        supports_vision: false,
        max_image_count: 5,
        max_image_size_mb: 10,
      },
      input_variables: [],
    },
  ]);
  const conversations = vue.ref([
    {
      id: 10,
      agent_id: 2,
      agent_name: 'Agent Two',
      title: 'Conversation',
      status: 'active',
      created_at: '2024-01-01T00:00:00Z',
    },
  ]);
  return {
    useAIChat: () => ({
      agents,
      agentsLoading: vue.ref(false),
      selectedAgentId: selectedAgentIdValue,
      selectedAgent: vue.computed(
        () =>
          agents.value.find(
            (agent) => agent.id === selectedAgentIdValue.value,
          ) ?? null,
      ),
      loadAgents: loadAgentsMock,
      conversations,
      conversationsLoading: vue.ref(false),
      activeConversationId: activeConversationIdValue,
      loadConversations: loadConversationsMock,
      startNewConversation: startNewConversationMock,
      deleteConversation: deleteConversationMock,
      updateConversationTitle: updateConversationTitleMock,
      loadConversationMessages: loadConversationMessagesMock,
      chatMessages: vue.ref([]),
      inputMessage: inputMessageValue,
      mentionedAgentId: vue.ref(null),
      mentionedAgent: vue.computed(() => null),
      mentionOpen: vue.ref(false),
      mentionQuery: vue.ref(''),
      mentionCandidates: vue.ref([]),
      mentionActiveIndex: vue.ref(0),
      sending: vue.ref(false),
      streaming: vue.ref(false),
      messagesContainer: vue.ref(null),
      sendMessage: sendMessageMock,
      stopGeneration: vi.fn(),
      handleMessagesScroll: vi.fn(),
      showScrollToBottom: vue.ref(false),
      showScrollToTop: vue.ref(false),
      scrollToBottom: vi.fn(),
      scrollToTop: vi.fn(),
      copyMessage: vi.fn(),
      handleInputKeyDown: vi.fn(() => false),
      selectMentionAgent: vi.fn(),
      selectMentionKnowledgeBase: vi.fn(),
      removeSelectedKnowledgeBase: vi.fn(),
      selectedKBIds: vue.ref([]),
      clearMentionedAgent: vi.fn(),
      cleanup: vi.fn(),
      pendingAttachments: pendingAttachmentsValue,
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
      clearConversationMemory: clearConversationMemoryMock,
      clearingMemory: vue.ref(false),
      fetchConversationMemory: fetchConversationMemoryMock,
      memoryState: vue.ref(null),
      memoryLoading: vue.ref(false),
      lastMemoryUpdated: vue.ref(false),
      exportAsMarkdown: vi.fn(),
      exportAsPlainText: vi.fn(),
      totalTokensUsed: vue.ref(0),
      supportsVision: supportsVisionValue,
      agentKBBindings: vue.ref([]),
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
    routeMessage: routeMessageMock,
  }),
}));

vi.mock('#/composables/use-modal-detector', () => ({
  useModalDetector: () => ({ modalState: {} }),
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => null,
}));

vi.mock('#/composables/use-page-screenshot', () => ({
  DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS: [
    '[data-ai-panel]',
    '.ant-message',
  ],
  usePageScreenshot: () => ({
    captureAndUpload: vi.fn(),
    capturing: ref(false),
  }),
}));

vi.mock('#/composables/use-form-state-tracker', () => ({
  formStateTracker: {
    getFieldDescriptors: vi.fn(() => null),
    isOpenWithFallback: vi.fn(() => false),
    track: vi.fn(),
    untrack: vi.fn(),
  },
}));

vi.mock('../page-context-registry', () => ({
  resolvePageContext: () => pageContextValue.value,
  pageContextVersion: ref(0),
}));

vi.mock('../page-operation-registry', () => ({
  listPageOperations: () => pageOperationsValue.value,
  pageOperationVersion: ref(0),
}));

describe('AIChatSlidePanel (component mount)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000_000_000);
    visible.value = true;
    docked.value = true;
    minimized.value = false;
    mode.value = 'panel';
    panelWidth.value = 460;
    selectedAgentIdValue.value = 1;
    supportsVisionValue.value = false;
    activeConversationIdValue.value = null;
    inputMessageValue.value = '';
    pendingAttachmentsValue.value = [];
    pageContextValue.value = null;
    pendingPageOpsValue.value = [];
    pageOperationsValue.value = [];
    aiPanelStore = createAIPanelStore();
    aiPanelStore.visible = visible.value;
    aiPanelStore.docked = docked.value;
    aiPanelStore.minimized = minimized.value;
    aiPanelStore.mode = mode.value;
    aiPanelStore.panelWidth = panelWidth.value;
    aiPanelStore.pendingPageOps = pendingPageOpsValue.value;
    resolvePageOp.mockClear();
    routeMessageMock.mockReset();
    routeMessageMock.mockResolvedValue({
      agentId: 1,
      agentName: 'Agent One',
      confidence: 1,
      routedBy: 'router',
    });
    sendMessageMock.mockClear();
    startNewConversationMock.mockClear();
    startNewConversationMock.mockResolvedValue(undefined);
    deleteConversationMock.mockClear();
    loadConversationMessagesMock.mockClear();
    loadConversationsMock.mockClear();
    loadConversationsMock.mockResolvedValue(undefined);
    loadAgentsMock.mockClear();
    loadAgentsMock.mockResolvedValue(undefined);
    updateConversationTitleMock.mockClear();
    fetchConversationMemoryMock.mockClear();
    clearConversationMemoryMock.mockClear();
    antMessageMocks.error.mockClear();
    antMessageMocks.warning.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('renders confirmCountdown when pending op exists', async () => {
    const startedAt = 1_000_000_000_000; // Same as fake now / 与 fake time 当前值一致
    pendingPageOpsValue.value = [
      {
        invokeId: 'op-1',
        operationLabel: 'Replace Content',
        operationDescription: 'Replace content in editor',
        resolved: false,
        startedAt,
      },
    ];
    aiPanelStore.pendingPageOps = pendingPageOpsValue.value;

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    // Panel is teleported to body; confirmCountdown should be visible / 面板通过 teleport 挂到 body，需能看到倒计时
    const panel = document.querySelector('[data-ai-panel]');
    expect(panel).toBeTruthy();
    expect(panel?.textContent).toMatch(/60s remaining|60/);

    wrapper.unmount();
  });

  it('reopens without resetting the current conversation when no external context is queued', async () => {
    activeConversationIdValue.value = 10;

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    startNewConversationMock.mockClear();

    aiPanelStore.visible = false;
    await flushPromises();
    aiPanelStore.visible = true;
    await flushPromises();

    expect(startNewConversationMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('restores queued conversation before sending queued message', async () => {
    selectedAgentIdValue.value = 2;
    loadConversationMessagesMock.mockImplementation(async (convId: number) => {
      activeConversationIdValue.value = convId;
    });

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pendingConversationId: 10,
        pendingMessage: 'continue this thread',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    expect(loadConversationMessagesMock).toHaveBeenCalledWith(10);
    expect(sendMessageMock).toHaveBeenCalledWith({ pageContext: null });
    expect(
      loadConversationMessagesMock.mock.invocationCallOrder[0],
    ).toBeLessThan(sendMessageMock.mock.invocationCallOrder[0]);

    wrapper.unmount();
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
    aiPanelStore.pendingPageOps = pendingPageOpsValue.value;

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.page',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    let panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/60/);

    // Advance 5s; countdown ticks every 1s / 前进 5 秒；倒计时按 1 秒步进
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(1000);
      await flushPromises();
    }
    panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/55/);

    // Advance to 60s+; countdown should clamp at 0 / 前进到 60 秒以上；倒计时应钳制为 0
    vi.advanceTimersByTime(60_000);
    await flushPromises();
    panel = document.querySelector('[data-ai-panel]');
    expect(panel?.textContent).toMatch(/0s remaining|0/);

    wrapper.unmount();
  });

  it('sends directly within an active conversation without routing again', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'follow-up';

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.page',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    expect(sendButton).toBeTruthy();
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).not.toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith({ pageContext: null });

    wrapper.unmount();
  });

  it('renders the compact header rail and more-actions trigger', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.page',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-header-status"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector('[data-testid="ai-panel-header-actions"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector(
        'button[aria-label="common.aiPanel.moreActions"]',
      ),
    ).toBeTruthy();

    wrapper.unmount();
  });

  it('renders route notice as a standalone header banner after routing', async () => {
    selectedAgentIdValue.value = 1;
    inputMessageValue.value = 'hello';
    routeMessageMock.mockResolvedValueOnce({
      agentId: 1,
      agentName: 'Agent One',
      confidence: 1,
      routedBy: 'router',
    });

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    expect(sendButton).toBeTruthy();
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routeBanner = document.body.querySelector(
      '[data-testid="ai-panel-route-banner"]',
    );
    expect(routeBanner).toBeTruthy();
    expect(routeBanner?.textContent).toContain('common.aiPanel.routedTo');

    wrapper.unmount();
  });

  it('renders a compact page AI rail that expands on demand', async () => {
    pageOperationsValue.value = [
      { name: 'op-1', label: 'Refresh', readonly: true },
      { name: 'op-2', label: 'Open Drawer', readonly: false },
      { name: 'op-3', label: 'Save Draft', readonly: false },
      { name: 'op-4', label: 'Search Records', readonly: true },
      { name: 'op-5', label: 'Assign Owner', readonly: false },
      { name: 'op-6', label: 'Export View', readonly: true },
    ];

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.page',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-card"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(0);

    const capabilityRail = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-card"]',
    ) as HTMLDivElement | null;
    expect(capabilityRail).toBeTruthy();
    capabilityRail?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeTruthy();
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(4);

    capabilityRail?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    const toggleButton = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-toggle"]',
    ) as HTMLButtonElement | null;
    expect(toggleButton).toBeTruthy();
    toggleButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeTruthy();
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiOperationCount',
    );
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiWritableCount',
    );
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiReadonlyCount',
    );
    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(4);

    const moreButton = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-more"]',
    ) as HTMLButtonElement | null;
    expect(moreButton).toBeTruthy();
    moreButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelectorAll(
        '[data-testid="ai-panel-page-ai-preview-item"]',
      ),
    ).toHaveLength(6);

    toggleButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-details"]'),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('mounts safely when page context exists before runtime size guards initialize', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.page',
      page_title: 'admin.system.codegen.name',
      page_data: {
        list_summary: {
          columns: ['name'],
          row_count: 1,
          sample_rows: [{ name: 'Codegen' }],
        },
      },
    };
    pageOperationsValue.value = [
      { name: 'op-1', label: 'Inspect', readonly: true },
    ];

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.page',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-card"]'),
    ).toBeTruthy();
    expect(antMessageMocks.error).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('does not expose fallback-only context as formal page AI support', async () => {
    pageContextValue.value = {
      page_key: 'tenant.demo.fallback',
      page_title: 'Fallback Only',
      page_data: {
        source: 'dom_snapshot',
        tables: [{ columns: ['name'], row_count: 1 }],
      },
    };

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.fallback',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();

    expect(
      document.body.querySelector('[data-testid="ai-panel-page-ai-card"]'),
    ).toBeFalsy();

    wrapper.unmount();
  });

  it('keeps form_fields in routed page context while trimming oversized payloads', async () => {
    inputMessageValue.value = 'inspect this page';
    pageContextValue.value = {
      page_key: 'tenant.demo.large',
      page_title: 'Large Demo Page',
      page_data: {
        document_body_text: 'x'.repeat(6400),
        form_fields: Object.fromEntries(
          Array.from({ length: 24 }, (_, index) => [
            `field_${index}`,
            {
              component: 'input',
              description: `Field ${index} `.repeat(18),
              options: Array.from({ length: 6 }, (__, optionIndex) => ({
                label: `Option ${index}-${optionIndex}`,
                value: `${index}-${optionIndex}`,
              })),
              required: index % 2 === 0,
              type: 'string',
            },
          ]),
        ),
        list_summary: {
          sample_rows: Array.from({ length: 5 }, (_, index) => ({
            description: `Row ${index} `.repeat(32),
            name: `Record ${index}`,
          })),
          total_rows: 50,
        },
      },
    };
    pageOperationsValue.value = Array.from({ length: 16 }, (_, index) => ({
      description: `Operation ${index} `.repeat(14),
      label: `Op ${index}`,
      name: `op_${index}`,
      params: {
        field_name: {
          description: `Field name ${index}`.repeat(12),
          required: true,
          type: 'string',
        },
        mode: {
          enum: ['draft', 'published', 'archived'],
          type: 'string',
        },
      },
      readonly: index % 2 === 0,
    }));

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.large',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    expect(sendButton).toBeTruthy();
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routedContext = routeMessageMock.mock.calls[0]?.[2] as null | {
      page_data?: Record<string, unknown>;
    };
    expect(routedContext?.page_data).toBeTruthy();
    expect(routedContext?.page_data?.form_fields).toBeTruthy();
    expect(
      Object.keys(
        routedContext?.page_data?.form_fields as Record<string, unknown>,
      ).length,
    ).toBeGreaterThan(0);
    expect(
      (
        routedContext?.page_data?.list_summary as
          | { sample_rows?: unknown[] }
          | undefined
      )?.sample_rows?.length ?? 0,
    ).toBeLessThanOrEqual(2);
    expect(
      (routedContext?.page_data?.available_operations as unknown[] | undefined)
        ?.length ?? 0,
    ).toBeLessThanOrEqual(16);
    expect(
      String(routedContext?.page_data?.document_body_text ?? '').length,
    ).toBeLessThan(6400);

    wrapper.unmount();
  });

  it('keeps screenshot page operations in routed page context for backend runtime gating', async () => {
    inputMessageValue.value = 'inspect this page';
    supportsVisionValue.value = false;
    pageContextValue.value = {
      page_key: 'tenant.demo.visual',
      page_title: 'Visual Demo',
      page_data: {},
    };
    pageOperationsValue.value = [
      {
        label: 'Capture Screenshot',
        name: 'capture_screenshot',
        readonly: true,
      },
      { label: 'Read View', name: 'read_current_view', readonly: true },
    ];

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        pageContextKey: 'tenant.demo.visual',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    expect(sendButton).toBeTruthy();
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    const routedContext = routeMessageMock.mock.calls[0]?.[2] as null | {
      page_data?: {
        available_operations?: Array<{ name: string }>;
      };
    };
    const opNames =
      routedContext?.page_data?.available_operations?.map(
        (item) => item.name,
      ) ?? [];
    expect(opNames).toContain('read_current_view');
    expect(opNames).toContain('capture_screenshot');

    wrapper.unmount();
  });

  it('does not fall back to current agent when image reroute fails', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'look at this';
    pendingAttachmentsValue.value = [{ type: 'image' }];
    routeMessageMock.mockRejectedValueOnce(new Error('no vision agent'));

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const rerouteButton = document.body.querySelector(
      'button[aria-label="common.globalAiChat.rerouteThisTurn"]',
    );
    const sendButton = document.body.querySelector('button.send-btn');
    expect(rerouteButton).toBeTruthy();
    expect(sendButton).toBeTruthy();
    rerouteButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[4]).toBe(true);
    expect(sendMessageMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('routes attachment-only audio messages with placeholder text and attachment flags', async () => {
    activeConversationIdValue.value = null;
    selectedAgentIdValue.value = 1;
    inputMessageValue.value = '';
    pendingAttachmentsValue.value = [{ type: 'audio' }];

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const sendButton = document.body.querySelector('button.send-btn');
    expect(sendButton).toBeTruthy();
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[0]).toBe(' ');
    expect(routeMessageMock.mock.calls[0]?.[3]).toEqual({
      hasAudioAttachments: true,
      hasFileAttachments: false,
      hasImageAttachments: false,
      hasVideoAttachments: false,
    });
    expect(sendMessageMock).toHaveBeenCalledWith({
      agentId: 1,
      pageContext: null,
    });

    wrapper.unmount();
  });

  it('does not fall back to current agent when audio reroute fails', async () => {
    activeConversationIdValue.value = 10;
    selectedAgentIdValue.value = 2;
    inputMessageValue.value = 'listen to this';
    pendingAttachmentsValue.value = [{ type: 'audio' }];
    routeMessageMock.mockRejectedValueOnce(new Error('no audio model'));

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: true,
        },
      },
    });

    await flushPromises();
    const rerouteButton = document.body.querySelector(
      'button[aria-label="common.globalAiChat.rerouteThisTurn"]',
    );
    const sendButton = document.body.querySelector('button.send-btn');
    expect(rerouteButton).toBeTruthy();
    expect(sendButton).toBeTruthy();
    rerouteButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    sendButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[4]).toBe(true);
    expect(sendMessageMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });
});
