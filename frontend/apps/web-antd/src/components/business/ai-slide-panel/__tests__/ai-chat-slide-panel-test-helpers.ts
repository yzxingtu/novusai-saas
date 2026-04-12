import type { PageContext } from '#/api/shared/ai-chat';
import type { SourceEditorRegistration } from '#/components/business/rich-text-editor/types';
import type { AgentItem, ChatMessage, RichTextAITask } from '#/types/ai-chat';
import type { useRichTextTaskOrchestration } from '../use-rich-text-task-orchestration';

import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, reactive, ref } from 'vue';

import { expect, vi } from 'vitest';

const hoistedUseAIChatState = vi.hoisted(() => ({
  chatMessages: undefined as unknown as { value: ChatMessage[] },
  sending: undefined as unknown as { value: boolean },
  streaming: undefined as unknown as { value: boolean },
}));
export const useAIChatState = hoistedUseAIChatState;

const hoistedSourceEditorMockState = vi.hoisted(() => ({
  editors: new Map<string, SourceEditorRegistration>(),
  prepareRichTextContent: vi.fn(
    (content: string, options?: { mode?: 'formatted' | 'plain' }) =>
      `prepared::${options?.mode ?? 'plain'}::${content}`,
  ),
  version: undefined as unknown as { value: number },
}));
export const sourceEditorMockState = hoistedSourceEditorMockState;

const hoistedComposerInteractionState = vi.hoisted(() => ({
  agentKBBindings: undefined as unknown as {
    value: Array<{ kb_name?: string; knowledge_base_id: number }>;
  },
  removeSelectedKnowledgeBase: vi.fn(),
  selectedKBIds: undefined as unknown as { value: number[] },
}));
export const composerInteractionState = hoistedComposerInteractionState;

export const visible = ref(true);
export const docked = ref(true);
export const minimized = ref(false);
export const mode = ref<'full' | 'panel'>('panel');
export const panelWidth = ref(460);
export const selectedAgentIdValue = ref<null | number>(1);
export const supportsVisionValue = ref(false);
export const activeConversationIdValue = ref<null | number>(null);
export const inputMessageValue = ref('');
export const pendingAttachmentsValue = ref<Array<{ type: string }>>([]);
export const pageContextValue = ref<
  null | (PageContext & { page_data?: Record<string, unknown> })
>(null);
export const pageOperationsValue = ref<
  Array<{
    description?: string;
    label: string;
    name: string;
    params?: Record<string, unknown>;
    readonly: boolean;
  }>
>([]);
export const routeMessageMock = vi.fn();
export const sendMessageMock = vi.fn();
export const startNewConversationMock = vi.fn();
export const deleteConversationMock = vi.fn();
export const loadConversationMessagesMock = vi.fn();
export const loadConversationsMock = vi.fn();
export const loadAgentsMock = vi.fn();
export const updateConversationTitleMock = vi.fn();
export const fetchConversationMemoryMock = vi.fn();
export const clearConversationMemoryMock = vi.fn();
export const pendingPageOpsValue = ref<
  Array<{
    invokeId: string;
    operationDescription: string;
    operationLabel: string;
    resolved: boolean;
    startedAt: number;
  }>
>([]);
export const resolvePageOp = vi.fn();
const hoistedAntMessageMocks = vi.hoisted(() => ({
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}));
export const antMessageMocks = hoistedAntMessageMocks;

export interface MockAIPanelStore {
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

export function requireElement<T>(value: null | T | undefined, message: string): T {
  expect(value).toBeTruthy();
  if (value === null || value === undefined) {
    throw new Error(message);
  }
  return value;
}

export function createAIPanelStore() {
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

export function createRichTextTask(
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

export function createRichTextMessage(
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

export function createSourceEditorMock(
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

export async function flushPanel() {
  const isFakeTimers =
    (vi as typeof vi & { isFakeTimers?: () => boolean }).isFakeTimers?.() ??
    false;
  if (isFakeTimers) {
    const first = flushPromises();
    vi.runOnlyPendingTimers();
    await first;
    const second = flushPromises();
    vi.runOnlyPendingTimers();
    await second;
    return;
  }
  await flushPromises();
  await flushPromises();
}

export type PanelMountOverrides = {
  attachTo?: Element;
  global?: { stubs?: Record<string, unknown> } & Record<string, unknown>;
  props?: Record<string, unknown>;
};

export function createPanelMountOptions(overrides: PanelMountOverrides = {}) {
  const stubs = {
    ChatMessageItem: true,
    ...(overrides.global?.stubs ?? {}),
  };

  return {
    props: {
      apiPrefix: '/tenant',
      uploadUrl: '/upload',
      ...(overrides.props ?? {}),
    },
    attachTo: overrides.attachTo ?? document.body,
    global: {
      ...(overrides.global ?? {}),
      stubs,
    },
  };
}

export function createIconifyMock() {
  return {
    IconifyIcon: defineComponent({
      name: 'IconifyIconStub',
      template: '<span class="iconify-stub"></span>',
    }),
  };
}

export function createImageMock() {
  return {
    toAbsoluteApiUrl: (url?: string) =>
      typeof url === 'string' && url.startsWith('/')
        ? `http://localhost:8000${url}`
        : (url ?? ''),
  };
}

export function createAntDesignVueMock() {
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

  const Image = defineComponent({
    name: 'ImageStub',
    props: {
      preview: {
        default: false,
        type: [Boolean, Object],
      },
      src: {
        default: '',
        type: String,
      },
    },
    template: `
      <div class="image-stub">
        <img v-if="src" class="image-inline-stub" :src="src" alt="" />
        <div
          v-if="preview && typeof preview === 'object' && preview.visible"
          class="image-preview-stub"
        >
          <img :src="preview.src || src" alt="" />
        </div>
      </div>
    `,
  });

  const Drawer = defineComponent({
    name: 'DrawerStub',
    props: {
      open: {
        default: false,
        type: Boolean,
      },
    },
    emits: ['update:open'],
    template: '<div v-if="open" class="drawer-stub"><slot /></div>',
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
    Drawer,
    Image,
    Input,
    Menu,
    Modal,
    Popover,
    Spin,
    Tooltip,
    message: antMessageMocks,
  };
}

export async function createUseAIChatMock() {
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
          agents.value.find((agent) => agent.id === selectedAgentIdValue.value) ??
          null,
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
      removeSelectedKnowledgeBase: composerInteractionState.removeSelectedKnowledgeBase,
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
}

export async function createSourceEditorRegistryMock() {
  const vue = await import('vue');
  sourceEditorMockState.version = vue.ref(0);
  return {
    prepareRichTextContent: sourceEditorMockState.prepareRichTextContent,
    resolveSourceEditor: (pageKey: string, editorInstanceId: string) =>
      sourceEditorMockState.editors.get(`${pageKey}::${editorInstanceId}`) ?? null,
    sourceEditorRegistryVersion: sourceEditorMockState.version,
  };
}

export function createUseAgentRouterMock() {
  return {
    useAgentRouter: () => ({
      routing: ref(false),
      routeMessage: routeMessageMock,
    }),
  };
}

export function createUseModalDetectorMock() {
  return {
    useModalDetector: () => ({ modalState: {} }),
  };
}

export function createUsePageSessionMock() {
  return {
    getActivePageSessionId: () => null,
  };
}

export function createUsePageScreenshotMock() {
  return {
    DEFAULT_PAGE_SCREENSHOT_EXCLUDE_SELECTORS: ['[data-ai-panel]', '.ant-message'],
    usePageScreenshot: () => ({
      captureAndUpload: vi.fn(),
      capturing: ref(false),
    }),
  };
}

export function createFormStateTrackerMock() {
  return {
    formStateTracker: {
      getFieldDescriptors: vi.fn(() => null),
      isOpenWithFallback: vi.fn(() => false),
      track: vi.fn(),
      untrack: vi.fn(),
    },
  };
}

export function createRuntimeBridgeMock() {
  return {
    getRuntimePageContextDiagnostics: () => ({
      interactables_count: pageOperationsValue.value.length,
      size_bytes: 128,
      source: 'ui_runtime',
      ui_epoch: 1,
    }),
    getRuntimeThinPageContext: (explicitPageKey?: string) => {
      const context = pageContextValue.value;
      const pageKey = explicitPageKey?.trim() || context?.page_key?.trim() || '';
      if (!pageKey) {
        return null;
      }
      const uiToolPool = [
        'ui_get_snapshot',
        'ui_list_interactables',
        'ui_read_region',
        'ui_read_table',
        'ui_click',
        'ui_open_surface',
        'ui_get_form_state',
        'ui_set_field',
        'ui_fill_form',
        'ui_submit_form',
      ] as const;
      const suggestedFromOps = pageOperationsValue.value
        .map((operation, index) => {
          const rawName = String(operation.name || '').trim();
          if (rawName.startsWith('ui_')) {
            return rawName;
          }
          return uiToolPool[index % uiToolPool.length];
        })
        .filter(Boolean);
      const suggestedTools =
        context?.suggested_tools ||
        (suggestedFromOps.length > 0
          ? {
              primary: suggestedFromOps.slice(0, 3),
              reason: 'test_mock',
              secondary: suggestedFromOps.slice(3, 6),
            }
          : {
              primary: ['ui_get_snapshot'],
              reason: 'test_mock_fallback',
              secondary: ['ui_read_region'],
            });
      return {
        active_form_session_id: context?.active_form_session_id,
        active_form_summary: context?.active_form_summary,
        active_surface_id: context?.active_surface_id,
        locale: context?.locale,
        page_key: pageKey,
        page_session_id: context?.page_session_id,
        page_title: context?.page_title || pageKey,
        suggested_tools: suggestedTools,
        surface_stack: context?.surface_stack,
        ui_epoch: context?.ui_epoch ?? 1,
      };
    },
  };
}

export function resetPanelState(
  now = 1_000_000_000_000,
  options?: { useFakeTimers?: boolean },
) {
  if (options?.useFakeTimers) {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  } else {
    vi.useRealTimers();
  }
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
  const store = createAIPanelStore();
  store.visible = visible.value;
  store.docked = docked.value;
  store.minimized = minimized.value;
  store.mode = mode.value;
  store.panelWidth = panelWidth.value;
  store.pendingPageOps = pendingPageOpsValue.value;
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
  return store;
}

export function cleanupPanelDom() {
  vi.clearAllTimers();
  vi.useRealTimers();
  document.body.innerHTML = '';
}

type RichTextTaskPanelStore = Parameters<
  typeof useRichTextTaskOrchestration
>[0]['store'];

export function createRichTextTaskStoreStub(
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

export async function mountRichTextOrchestrationHarness(options: {
  activeConversationId?: null | number;
  chatMessages: ChatMessage[];
  store?: RichTextTaskPanelStore;
}) {
  const { useRichTextTaskOrchestration: runtimeUseRichTextTaskOrchestration } =
    await import('../use-rich-text-task-orchestration');
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
        const orchestration = runtimeUseRichTextTaskOrchestration({
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
