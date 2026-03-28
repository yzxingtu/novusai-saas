// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import type {
  AgentItem,
  ChatMessage,
  RichTextAITask,
} from '#/components/business/ai-chat-panel/types';
import type { SourceEditorRegistration } from '#/components/business/rich-text-editor/types';

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
import { useRichTextTaskOrchestration } from '../use-rich-text-task-orchestration';

const useAIChatState = vi.hoisted(() => ({
  chatMessages: undefined as unknown as { value: ChatMessage[] },
  sending: undefined as unknown as { value: boolean },
  streaming: undefined as unknown as { value: boolean },
}));

const sourceEditorMockState = vi.hoisted(() => ({
  editors: new Map<string, SourceEditorRegistration>(),
  prepareRichTextContent: vi.fn(
    (content: string, options?: { mode?: 'formatted' | 'plain' }) =>
      `prepared::${options?.mode ?? 'plain'}::${content}`,
  ),
  version: undefined as unknown as { value: number },
}));

const composerInteractionState = vi.hoisted(() => ({
  agentKBBindings: undefined as unknown as {
    value: Array<{ kb_name?: string; knowledge_base_id: number }>;
  },
  removeSelectedKnowledgeBase: vi.fn(),
  selectedKBIds: undefined as unknown as { value: number[] },
}));

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
    operationDescription: string;
    operationLabel: string;
    resolved: boolean;
    startedAt: number;
  }>
>([]);
const resolvePageOp = vi.fn();
const antMessageMocks = vi.hoisted(() => ({
  error: vi.fn(),
  info: vi.fn(),
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

interface MockAIPanelStore {
  bindRichTextConversation: ReturnType<typeof vi.fn>;
  clearResolvedPageOps: ReturnType<typeof vi.fn>;
  clearPendingRichTextTask: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  consumePendingAgentId: ReturnType<typeof vi.fn>;
  dispatchToolCall: ReturnType<typeof vi.fn>;
  docked: boolean;
  getRichTextConversationBinding: ReturnType<typeof vi.fn>;
  hasUnread: boolean;
  markRichTextTaskApplied: ReturnType<typeof vi.fn>;
  markRichTextTaskUndone: ReturnType<typeof vi.fn>;
  markUnread: ReturnType<typeof vi.fn>;
  minimize: ReturnType<typeof vi.fn>;
  minimized: boolean;
  mode: 'full' | 'panel';
  open: ReturnType<typeof vi.fn>;
  panelWidth: number;
  pendingConversationId: null | number;
  pendingMessage: null | string;
  pendingPageOps: typeof pendingPageOpsValue.value;
  pendingRichTextTask: null | RichTextAITask;
  pinnedAgentId: null | number;
  pinnedAgentName: null | string;
  promoteQueuedRichTextTask: ReturnType<typeof vi.fn>;
  queuedRichTextTask: null | RichTextAITask;
  queueRichTextTask: ReturnType<typeof vi.fn>;
  resetConversation: ReturnType<typeof vi.fn>;
  resolvePageOp: typeof resolvePageOp;
  restore: ReturnType<typeof vi.fn>;
  setConversation: ReturnType<typeof vi.fn>;
  toggleDock: ReturnType<typeof vi.fn>;
  toggleMode: ReturnType<typeof vi.fn>;
  togglePin: ReturnType<typeof vi.fn>;
  unpinAgent: ReturnType<typeof vi.fn>;
  visible: boolean;
}

function requireElement<T>(value: null | T | undefined, message: string): T {
  expect(value).toBeTruthy();
  if (value === null || value === undefined) {
    throw new Error(message);
  }
  return value;
}

function createAIPanelStore() {
  const store = reactive<MockAIPanelStore>({
    bindRichTextConversation: vi.fn(),
    clearResolvedPageOps: vi.fn(),
    clearPendingRichTextTask: vi.fn((taskId?: string) => {
      if (!taskId || store.pendingRichTextTask?.taskId === taskId) {
        store.pendingRichTextTask = null;
      }
    }),
    close: vi.fn(() => {
      store.visible = false;
    }),
    consumePendingAgentId: vi.fn(() => null),
    dispatchToolCall: vi.fn(),
    docked: true,
    getRichTextConversationBinding: vi.fn(() => null),
    hasUnread: false,
    markRichTextTaskApplied: vi.fn(),
    markRichTextTaskUndone: vi.fn(),
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
    pendingConversationId: null as null | number,
    pendingMessage: null as null | string,
    pendingPageOps: [] as typeof pendingPageOpsValue.value,
    pendingRichTextTask: null,
    pinnedAgentId: null as null | number,
    pinnedAgentName: null as null | string,
    promoteQueuedRichTextTask: vi.fn(() => {
      if (!store.queuedRichTextTask) {
        return null;
      }
      const nextTask: RichTextAITask = {
        ...store.queuedRichTextTask,
        state: 'ready',
      };
      store.queuedRichTextTask = null;
      store.pendingRichTextTask = nextTask;
      return nextTask;
    }),
    queuedRichTextTask: null,
    queueRichTextTask: vi.fn((task: RichTextAITask) => {
      store.queuedRichTextTask = {
        ...task,
        state: 'queued',
      };
    }),
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

function createRichTextTask(
  overrides: Partial<RichTextAITask> = {},
): RichTextAITask {
  const pageKey = overrides.pageKey ?? 'tenant.docs.detail';
  const editorInstanceId = overrides.editorInstanceId ?? 'editor-1';
  return {
    agentId: 1,
    availableModes: ['plain', 'formatted'],
    conversationId: null,
    contextTitle: '富文本页面',
    createdAt: 1000,
    draft: {
      html: '<p>Draft</p>',
      markdown: 'Draft',
      plainText: 'Draft',
    },
    editorInstanceId,
    feature: 'rewrite',
    message: '[Rich Text Task] Rewrite',
    pageKey,
    preferredApplyMode: 'formatted',
    selectionLabel: '待改写段落',
    selectionSnapshot: {
      afterTextExcerpt: 'after',
      beforeTextExcerpt: 'before',
      editorInstanceId,
      editorRevision: 2,
      from: 4,
      pageKey,
      selectedText: '待改写段落',
      to: 12,
    },
    state: 'ready',
    summary: '已生成一版草稿',
    taskId: 'rich-text-task-1',
    title: 'AI Rewrite',
    updatedAt: 1000,
    ...overrides,
  };
}

function createRichTextMessage(
  task: RichTextAITask,
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  const clientKey = overrides.clientKey ?? `assistant-${task.taskId}`;
  return {
    clientKey,
    role: 'assistant',
    content: task.draft.markdown ?? task.message,
    source: 'rich_text_ai',
    richTextAI: {
      ...task,
      messageClientKey: task.messageClientKey ?? clientKey,
    },
    ...overrides,
  };
}

function createSourceEditorMock(
  task: RichTextAITask,
  options: {
    mounted?: boolean;
    revision?: number;
  } = {},
) {
  const state = {
    mounted: options.mounted ?? true,
    revision: options.revision ?? task.selectionSnapshot.editorRevision,
  };
  const editor: SourceEditorRegistration = {
    appendToEnd: vi.fn(() => {
      state.revision += 1;
      editor.revision = state.revision;
      return true;
    }),
    editorInstanceId: task.editorInstanceId,
    focus: vi.fn(),
    getHTML: vi.fn(() => '<p>Existing</p>'),
    getRevision: vi.fn(() => state.revision),
    getText: vi.fn(() => 'Existing'),
    insertAfterRange: vi.fn(() => {
      state.revision += 1;
      editor.revision = state.revision;
      return true;
    }),
    isMounted: vi.fn(() => state.mounted),
    pageKey: task.pageKey,
    replaceRange: vi.fn(() => {
      state.revision += 1;
      editor.revision = state.revision;
      return true;
    }),
    revision: state.revision,
    undo: vi.fn(() => {
      if (state.revision <= 0) {
        return false;
      }
      state.revision -= 1;
      editor.revision = state.revision;
      return true;
    }),
  };
  sourceEditorMockState.editors.set(
    `${task.pageKey}::${task.editorInstanceId}`,
    editor,
  );
  sourceEditorMockState.version.value += 1;
  return editor;
}

async function flushPanel() {
  await flushPromises();
  await flushPromises();
}

type RichTextTaskPanelStore = Parameters<
  typeof useRichTextTaskOrchestration
>[0]['store'];

function createRichTextTaskStoreStub(
  overrides: Partial<RichTextTaskPanelStore> = {},
): RichTextTaskPanelStore {
  return {
    bindRichTextConversation: vi.fn(),
    clearPendingRichTextTask: vi.fn(),
    getRichTextConversationBinding: vi.fn(() => null),
    markRichTextTaskApplied: vi.fn(),
    markRichTextTaskUndone: vi.fn(),
    open: vi.fn(),
    pendingRichTextTask: null,
    promoteQueuedRichTextTask: vi.fn(() => null),
    queueRichTextTask: vi.fn(),
    visible: true,
    ...overrides,
  };
}

function mountRichTextOrchestrationHarness(options: {
  activeConversationId?: null | number;
  chatMessages: ChatMessage[];
  store?: RichTextTaskPanelStore;
}) {
  const activeConversationId = ref<null | number>(
    options.activeConversationId ?? null,
  );
  const agents = ref<AgentItem[]>([
    {
      avatar: null,
      description: null,
      id: 1,
      input_variables: null,
      name: 'AI Writer',
      status: 'active',
      tenant_id: 1,
    },
  ]);
  const allAgentsVariables = ref<Record<number, Record<string, string>>>({});
  const chatMessages = ref(options.chatMessages);
  const inputMessage = ref('');
  const manualNewConversationAgentId = ref<null | number>(null);
  const selectedAgentId = ref<null | number>(1);
  const showHistory = ref(false);
  const showMemoryPanel = ref(false);
  const sending = ref(false);
  const streaming = ref(false);
  const store = options.store ?? createRichTextTaskStoreStub();

  const wrapper = mount(
    defineComponent({
      setup(_, { expose }) {
        const orchestration = useRichTextTaskOrchestration({
          activeConversationId,
          agents,
          allAgentsVariables,
          chatMessages,
          ensureAgentVarsLoaded: vi.fn(),
          inputMessage,
          loadConversationMessages: vi.fn(),
          manualNewConversationAgentId,
          onMissingVariables: vi.fn(),
          onTaskQueued: vi.fn(),
          selectedAgentId,
          sendMessage: vi.fn(async () => true),
          sending,
          showHistory,
          showMemoryPanel,
          startNewConversation: vi.fn(),
          store,
          streaming,
        });

        expose({
          activeConversationId,
          getRichTextDraftState: (index: number) => {
            const message = chatMessages.value[index];
            return message
              ? orchestration.getRichTextDraftState(message)
              : null;
          },
          onRichTextApply: orchestration.onRichTextApply,
        });
        return () => null;
      },
    }),
  );

  return {
    activeConversationId,
    store,
    wrapper,
  };
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
  useAIChatState.chatMessages = vue.ref([]);
  useAIChatState.sending = vue.ref(false);
  useAIChatState.streaming = vue.ref(false);
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
  composerInteractionState.agentKBBindings ??= vue.ref([]);
  composerInteractionState.selectedKBIds ??= vue.ref([]);
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
      chatMessages: useAIChatState.chatMessages,
      inputMessage: inputMessageValue,
      mentionedAgentId: vue.ref(null),
      mentionedAgent: vue.computed(() => null),
      mentionOpen: vue.ref(false),
      mentionQuery: vue.ref(''),
      mentionCandidates: vue.ref([]),
      mentionActiveIndex: vue.ref(0),
      sending: useAIChatState.sending,
      streaming: useAIChatState.streaming,
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
      removeSelectedKnowledgeBase:
        composerInteractionState.removeSelectedKnowledgeBase,
      selectedKBIds: composerInteractionState.selectedKBIds,
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
      agentKBBindings: composerInteractionState.agentKBBindings,
      allAgentsVariables: vue.ref({}),
      agentsWithVarsInConversation: vue.ref([]),
      ensureAgentVarsLoaded: vi.fn(),
      applyVariables: vi.fn(),
    }),
  };
});

vi.mock(
  '#/components/business/rich-text-editor/sourceEditorRegistry',
  async () => {
    const vue = await import('vue');
    sourceEditorMockState.version = vue.ref(0);
    return {
      prepareRichTextContent: sourceEditorMockState.prepareRichTextContent,
      resolveSourceEditor: (pageKey: string, editorInstanceId: string) =>
        sourceEditorMockState.editors.get(`${pageKey}::${editorInstanceId}`) ??
        null,
      sourceEditorRegistryVersion: sourceEditorMockState.version,
    };
  },
);

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

describe('aIChatSlidePanel (component mount)', () => {
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
    useAIChatState.chatMessages.value = [];
    useAIChatState.sending.value = false;
    useAIChatState.streaming.value = false;
    sourceEditorMockState.editors.clear();
    sourceEditorMockState.prepareRichTextContent.mockClear();
    sourceEditorMockState.version.value = 0;
    composerInteractionState.agentKBBindings.value = [];
    composerInteractionState.removeSelectedKnowledgeBase.mockClear();
    composerInteractionState.selectedKBIds.value = [];
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
    sendMessageMock.mockReset();
    sendMessageMock.mockResolvedValue(true);
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
    antMessageMocks.info.mockClear();
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

    expect(startNewConversationMock).not.toHaveBeenCalled();
    expect(loadConversationMessagesMock).toHaveBeenCalledWith(10);
    expect(sendMessageMock).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: null,
      }),
    );
    const loadInvocationOrder =
      loadConversationMessagesMock.mock.invocationCallOrder[0];
    const sendInvocationOrder = sendMessageMock.mock.invocationCallOrder[0];

    const resolvedLoadInvocationOrder = requireElement(
      loadInvocationOrder,
      'Expected loadConversationMessages invocation order',
    );
    const resolvedSendInvocationOrder = requireElement(
      sendInvocationOrder,
      'Expected sendMessage invocation order',
    );
    expect(resolvedLoadInvocationOrder).toBeLessThan(
      resolvedSendInvocationOrder,
    );

    wrapper.unmount();
  });

  it('falls back to store pendingMessage when prop timing lags behind visibility change', async () => {
    selectedAgentIdValue.value = 2;
    aiPanelStore.pendingMessage = 'store queued message';
    aiPanelStore.visible = false;

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

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: null,
      }),
    );
    expect(wrapper.emitted('messageSent')).toBeTruthy();

    wrapper.unmount();
  });

  it('keeps queued pendingMessage when external send did not start', async () => {
    selectedAgentIdValue.value = null;
    aiPanelStore.pendingMessage = 'store queued message';
    aiPanelStore.visible = false;
    routeMessageMock.mockRejectedValue(new Error('route failed'));

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

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(wrapper.emitted('messageSent')).toBeFalsy();
    expect(aiPanelStore.pendingMessage).toBe('store queued message');

    wrapper.unmount();
  });

  it('uses the queued pendingAgentId as the send target when external context starts a new conversation', async () => {
    selectedAgentIdValue.value = 2;
    aiPanelStore.pendingMessage = 'send to explicit agent';
    aiPanelStore.consumePendingAgentId = vi.fn(() => 1);
    aiPanelStore.visible = false;

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

    aiPanelStore.visible = true;
    await flushPromises();

    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
      }),
    );
    expect(wrapper.emitted('messageSent')).toBeTruthy();

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
    requireElement(
      sendButton,
      'Expected send button in active conversation test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).not.toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        pageContext: null,
      }),
    );

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
    requireElement(
      sendButton,
      'Expected send button in large context routing test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
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

  it('shows fallback-only page AI support with a downgraded awareness badge', async () => {
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
    ).toBeTruthy();
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiFallbackBadge',
    );

    const fallbackRail = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-card"]',
    ) as HTMLDivElement | null;
    fallbackRail?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeTruthy();
    expect(document.body.textContent).toContain(
      'common.aiPanel.pageAiDiagSource',
    );

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
    requireElement(
      sendButton,
      'Expected send button in screenshot operation test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
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
          | undefined
          | { sample_rows?: unknown[] }
      )?.sample_rows?.length ?? 0,
    ).toBeLessThanOrEqual(2);
    expect(
      (routedContext?.page_data?.available_operations as undefined | unknown[])
        ?.length ?? 0,
    ).toBeGreaterThan(0);
    expect(
      (
        routedContext?.page_data?.available_operations as Array<{
          name: string;
        }>
      ).every((operation) => typeof operation.name === 'string'),
    ).toBe(true);
    expect(
      String(routedContext?.page_data?.document_body_text ?? '').length,
    ).toBeLessThan(6400);

    const diagnosticsRail = document.body.querySelector(
      '[data-testid="ai-panel-page-ai-card"]',
    ) as HTMLDivElement | null;
    diagnosticsRail?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();
    expect(
      document.body.querySelector(
        '[data-testid="ai-panel-page-ai-diagnostics"]',
      ),
    ).toBeTruthy();

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
    requireElement(
      sendButton,
      'Expected send button in screenshot capability test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
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
    requireElement(
      rerouteButton,
      'Expected reroute button in image reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    requireElement(
      sendButton,
      'Expected send button in image reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
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
    requireElement(
      sendButton,
      'Expected send button in audio attachment routing test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
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

  it('toggles the send button disabled state with composer input changes', async () => {
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

    await flushPanel();

    const composerInput = requireElement(
      document.body.querySelector('[data-testid="ai-chat-input"]'),
      'Expected composer input for send button state test',
    ) as HTMLTextAreaElement;

    let sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button for composer input state test',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(true);

    composerInput.value = 'hello composer';
    composerInput.dispatchEvent(new Event('input', { bubbles: true }));
    await flushPanel();

    sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button after composer input update',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(false);

    composerInput.value = '';
    composerInput.dispatchEvent(new Event('input', { bubbles: true }));
    await flushPanel();

    sendButton = requireElement(
      document.body.querySelector('button.send-btn'),
      'Expected send button after clearing composer input',
    ) as HTMLButtonElement;
    expect(sendButton.hasAttribute('disabled')).toBe(true);

    wrapper.unmount();
  });

  it('removes selected KB chips from the current turn via the composer controls', async () => {
    composerInteractionState.agentKBBindings.value = [
      {
        kb_name: 'Knowledge Base A',
        knowledge_base_id: 101,
      },
    ];
    composerInteractionState.selectedKBIds.value = [101];

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

    await flushPanel();

    expect(document.body.textContent).toContain('Knowledge Base A');
    const removeKbButton = requireElement(
      document.body.querySelector(
        'button[aria-label="common.globalAiChat.removeKbFromTurn"]',
      ),
      'Expected remove KB button for current turn chip',
    ) as HTMLButtonElement;

    removeKbButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(
      composerInteractionState.removeSelectedKnowledgeBase,
    ).toHaveBeenCalledWith(101);

    wrapper.unmount();
  });

  it('dispatches a pending rich text task after reopening from the closed panel state', async () => {
    visible.value = false;
    const task = createRichTextTask({
      message: '[Rich Text Task] Rewrite from closed panel',
      taskId: 'rich-text-closed-task',
    });
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-closed',
          content: 'Draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });
    aiPanelStore = createAIPanelStore();
    aiPanelStore.visible = false;
    aiPanelStore.pendingRichTextTask = task;

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

    await flushPanel();

    expect(aiPanelStore.open).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(aiPanelStore.clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-closed-task',
    );
    expect(useAIChatState.chatMessages.value[0]?.richTextAI?.taskId).toBe(
      'rich-text-closed-task',
    );

    wrapper.unmount();
  });

  it('queues the latest pending rich text task while streaming', async () => {
    useAIChatState.streaming.value = true;

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

    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] First queued draft',
      taskId: 'rich-text-queue-1',
    });
    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      draft: {
        html: '<p>Second</p>',
        markdown: 'Second',
        plainText: 'Second',
      },
      message: '[Rich Text Task] Latest queued draft',
      taskId: 'rich-text-queue-2',
    });
    await flushPanel();

    expect(aiPanelStore.queueRichTextTask).toHaveBeenCalledTimes(2);
    expect(aiPanelStore.queueRichTextTask).toHaveBeenLastCalledWith(
      expect.objectContaining({
        taskId: 'rich-text-queue-2',
      }),
    );
    expect(aiPanelStore.queuedRichTextTask?.taskId).toBe('rich-text-queue-2');
    expect(aiPanelStore.pendingRichTextTask).toBeNull();
    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(antMessageMocks.info).toHaveBeenCalledWith(
      'common.richTextTaskQueued',
    );

    wrapper.unmount();
  });

  it('flushes the queued rich text task once the panel returns to idle', async () => {
    useAIChatState.streaming.value = true;
    sendMessageMock.mockImplementation(async ({ agentId, routeSource }) => {
      useAIChatState.chatMessages.value = [
        ...useAIChatState.chatMessages.value,
        {
          clientKey: 'assistant-rich-text-queued',
          content: 'Queued draft ready',
          role: 'assistant',
          agent_id: agentId ?? null,
          routeSource: routeSource ?? null,
        },
      ];
      return true;
    });

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

    await flushPanel();

    aiPanelStore.pendingRichTextTask = createRichTextTask({
      message: '[Rich Text Task] Flush queued draft',
      taskId: 'rich-text-flush-1',
    });
    await flushPanel();

    expect(aiPanelStore.queuedRichTextTask?.taskId).toBe('rich-text-flush-1');

    aiPanelStore.clearPendingRichTextTask.mockClear();
    aiPanelStore.promoteQueuedRichTextTask.mockClear();
    sendMessageMock.mockClear();
    useAIChatState.streaming.value = false;

    await flushPanel();

    expect(aiPanelStore.promoteQueuedRichTextTask).toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        agentId: 1,
        pageContext: null,
        routeSource: 'rich_text_ai',
      }),
    );
    expect(aiPanelStore.clearPendingRichTextTask).toHaveBeenCalledWith(
      'rich-text-flush-1',
    );
    expect(useAIChatState.chatMessages.value[0]?.richTextAI?.taskId).toBe(
      'rich-text-flush-1',
    );

    wrapper.unmount();
  });

  it('wires rich text apply, discard, and undo events through the slide panel', async () => {
    activeConversationIdValue.value = 42;
    const task = createRichTextTask({
      taskId: 'rich-text-actions',
    });
    const sourceEditor = createSourceEditorMock(task);
    useAIChatState.chatMessages.value = [createRichTextMessage(task)];

    const wrapper = mount(AIChatSlidePanel, {
      props: {
        apiPrefix: '/tenant',
        uploadUrl: '/upload',
      },
      attachTo: document.body,
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            props: {
              index: {
                required: true,
                type: Number,
              },
              msg: {
                required: true,
                type: Object,
              },
              richTextState: {
                default: null,
                type: Object,
              },
            },
            emits: ['rich-text-apply', 'rich-text-discard', 'rich-text-undo'],
            template: `
              <div data-testid="rich-text-message-item">
                <div data-testid="rich-text-state">
                  {{
                    JSON.stringify({
                      canUndo: richTextState?.canUndo ?? false,
                      discarded: richTextState?.discarded ?? false,
                    })
                  }}
                </div>
                <button
                  data-testid="rich-text-discard-btn"
                  @click="$emit('rich-text-discard', index)"
                />
                <button
                  data-testid="rich-text-apply-btn"
                  @click="$emit('rich-text-apply', index, 'replace_selection', 'formatted')"
                />
                <button
                  data-testid="rich-text-undo-btn"
                  @click="$emit('rich-text-undo', index)"
                />
              </div>
            `,
          }),
        },
      },
    });

    await flushPanel();

    const getRichTextStateText = () =>
      requireElement(
        document.body.querySelector('[data-testid="rich-text-state"]'),
        'Expected rich text state output',
      ).textContent ?? '';
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":false');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-discard-btn"]'),
      'Expected discard trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(getRichTextStateText()).toContain('"discarded":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-apply-btn"]'),
      'Expected apply trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditorMockState.prepareRichTextContent).toHaveBeenCalledWith(
      'Draft',
      { mode: 'formatted' },
    );
    expect(sourceEditor.replaceRange).toHaveBeenCalledWith(
      4,
      12,
      'prepared::formatted::Draft',
    );
    expect(aiPanelStore.markRichTextTaskApplied).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"discarded":false');
    expect(getRichTextStateText()).toContain('"canUndo":true');

    requireElement(
      document.body.querySelector('[data-testid="rich-text-undo-btn"]'),
      'Expected undo trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(sourceEditor.undo).toHaveBeenCalled();
    expect(aiPanelStore.markRichTextTaskUndone).toHaveBeenCalledWith(
      'rich-text-actions',
      {
        conversationId: 42,
        lastAppliedMode: 'formatted',
      },
    );
    expect(getRichTextStateText()).toContain('"canUndo":false');

    wrapper.unmount();
  });

  it('invalidates rich text undo once the active conversation changes', async () => {
    const task = createRichTextTask({
      taskId: 'rich-text-conversation-switch',
    });
    createSourceEditorMock(task);
    const { activeConversationId, wrapper } = mountRichTextOrchestrationHarness(
      {
        activeConversationId: 42,
        chatMessages: [createRichTextMessage(task)],
      },
    );

    await flushPanel();

    const harness = wrapper.vm as {
      getRichTextDraftState: (index: number) => null | { canUndo: boolean };
      onRichTextApply: (
        index: number,
        target: 'replace_selection',
        mode: 'formatted',
      ) => void;
    };

    harness.onRichTextApply(0, 'replace_selection', 'formatted');
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(true);

    activeConversationId.value = 99;
    await flushPanel();

    expect(harness.getRichTextDraftState(0)?.canUndo).toBe(false);

    wrapper.unmount();
  });

  it('keeps reopened rich text history messages read-only', async () => {
    const historyTask = createRichTextTask({
      messageClientKey: undefined,
      taskId: 'rich-text-history-readonly',
    });
    createSourceEditorMock(historyTask);
    const { wrapper } = mountRichTextOrchestrationHarness({
      chatMessages: [
        createRichTextMessage(historyTask, {
          richTextAI: {
            ...historyTask,
            messageClientKey: undefined,
          },
        }),
      ],
    });

    await flushPanel();

    const harness = wrapper.vm as {
      getRichTextDraftState: (index: number) => unknown;
    };
    expect(harness.getRichTextDraftState(0)).toBeNull();

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
    requireElement(
      rerouteButton,
      'Expected reroute button in audio reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    requireElement(
      sendButton,
      'Expected send button in audio reroute failure test',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(routeMessageMock).toHaveBeenCalledOnce();
    expect(routeMessageMock.mock.calls[0]?.[4]).toBe(true);
    expect(sendMessageMock).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('opens search result urls in a new tab instead of routing them to image preview', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null as unknown as Window);

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            emits: ['openUrl'],
            template:
              '<button data-testid="search-open-url" @click="$emit(\'openUrl\', \'https://example.com/article\')">open</button>',
          }),
        },
      },
    });

    await flushPanel();

    requireElement(
      document.body.querySelector('[data-testid="search-open-url"]'),
      'Expected open-url trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(openSpy).toHaveBeenCalledWith(
      'https://example.com/article',
      '_blank',
      'noopener,noreferrer',
    );
    expect(
      document.body.querySelector('.modal-stub img'),
    ).toBeFalsy();

    openSpy.mockRestore();
    wrapper.unmount();
  });

  it('keeps image urls on the preview lightbox path', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null as unknown as Window);

    const wrapper = mount(AIChatSlidePanel, {
      props: { apiPrefix: '/tenant', uploadUrl: '/upload' },
      attachTo: document.body,
      global: {
        stubs: {
          AIChatMessageViewport: defineComponent({
            emits: ['openUrl'],
            template:
              '<button data-testid="image-open-url" @click="$emit(\'openUrl\', \'https://example.com/image.png\')">preview</button>',
          }),
        },
      },
    });

    await flushPanel();

    requireElement(
      document.body.querySelector('[data-testid="image-open-url"]'),
      'Expected image open-url trigger',
    ).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPanel();

    expect(openSpy).not.toHaveBeenCalled();
    const previewImage = document.body.querySelector('.modal-stub img');
    expect(previewImage).toBeTruthy();
    expect((previewImage as HTMLImageElement).getAttribute('src')).toBe(
      'https://example.com/image.png',
    );

    openSpy.mockRestore();
    wrapper.unmount();
  });
});
