// @vitest-environment happy-dom
/**
 * Test type: behavioral
 * Verifies: the slide-panel shell drops stale welcome responses and starts a welcome request for the current agent after an in-flight agent switch.
 * Mock strategy: chat/runtime collaborators are stubbed, while useAIChatSlidePanelShell's welcome watcher and stale-response guards run real.
 */
import { computed, nextTick, ref } from 'vue';

import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { generateWelcomeMessageApi } from '#/api/shared/ai-chat';
import { useAIPanelStore } from '#/store';

import { useAIChatSlidePanelShell } from '../use-ai-chat-slide-panel-shell';

const mockState = vi.hoisted(() => ({
  chatState: undefined as any,
  createBindings: undefined as any,
  createPanelHistory: undefined as any,
  createPanelShellActions: undefined as any,
  createPanelShellContext: undefined as any,
}));

vi.mock('#/api/shared/ai-chat', () => ({
  generateWelcomeMessageApi: vi.fn(),
}));

vi.mock('#/components/business/ai-chat-panel/use-ai-chat', () => ({
  useAIChat: vi.fn(() => mockState.chatState),
}));

vi.mock('#/locales', () => ({
  $t: (key: string, vars?: Record<string, unknown>) =>
    vars?.agent ? `${String(vars.agent)} loading` : key,
}));

vi.mock('#/locales/runtime-locale', () => ({
  resolveRuntimeLocale: () => 'zh-CN',
}));

vi.mock('@vben/stores', () => ({
  useUserStore: () => ({
    userInfo: {
      realName: '测试用户',
    },
  }),
}));

vi.mock('../use-agent-router', () => ({
  useAgentRouter: vi.fn(() => ({
    routeMessage: vi.fn(),
    routing: ref(false),
  })),
}));

vi.mock('../use-ai-chat-slide-panel-shell-bindings', () => ({
  useAIChatSlidePanelShellBindings: vi.fn((options) =>
    mockState.createBindings(options),
  ),
}));

vi.mock('../use-panel-history', () => ({
  usePanelHistory: vi.fn((options) => mockState.createPanelHistory(options)),
}));

vi.mock('../use-panel-send-message', () => ({
  usePanelSendMessage: vi.fn(() => ({
    handleSendMessage: vi.fn(async () => true),
  })),
}));

vi.mock('../use-panel-shell-actions', () => ({
  usePanelShellActions: vi.fn((options) =>
    mockState.createPanelShellActions(options),
  ),
}));

vi.mock('../use-panel-shell-context', () => ({
  usePanelShellContext: vi.fn((options) =>
    mockState.createPanelShellContext(options),
  ),
}));

interface Deferred<T> {
  promise: Promise<T>;
  reject: (reason?: unknown) => void;
  resolve: (value: T) => void;
}

function createDeferred<T>(): Deferred<T> {
  let reject!: (reason?: unknown) => void;
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

async function flushAsync() {
  await Promise.resolve();
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

function createAgent(id: number, name: string) {
  return {
    avatar: null,
    description: null,
    id,
    name,
    status: 'published',
    tenant_id: 1,
  };
}

function createChatState() {
  const alphaAgent = createAgent(1, 'Alpha');
  const betaAgent = createAgent(2, 'Beta');
  const selectedAgent = ref(alphaAgent);
  const selectedAgentId = ref(alphaAgent.id);

  return {
    activeConversationId: ref(null),
    agentKBBindings: ref([]),
    agentKBBindingsByAgentId: computed(() => new Map()),
    agentSkillBindingsByAgentId: computed(() => new Map()),
    agents: ref([alphaAgent, betaAgent]),
    agentsLoading: ref(false),
    agentsWithVarsInConversation: computed(() => []),
    allAgentsVariables: ref([]),
    applyVariables: vi.fn(),
    chatAcceptAttribute: computed(() => ''),
    chatMessages: ref([]),
    clearingMemory: ref(false),
    cleanup: vi.fn(),
    clickActionButton: vi.fn(),
    confirmAction: vi.fn(),
    confirmConsent: vi.fn(),
    conversationContextDiagnostics: ref(null),
    conversations: ref([]),
    conversationsLoading: ref(false),
    copyMessage: vi.fn(async () => undefined),
    deleteConversation: vi.fn(),
    editAndResend: vi.fn(),
    ensureAgentVarsLoaded: vi.fn(async () => undefined),
    exportAsMarkdown: vi.fn(),
    exportAsPlainText: vi.fn(),
    fetchConversationMemory: vi.fn(async () => undefined),
    handleDragOver: vi.fn(),
    handleDrop: vi.fn(),
    handleFileSelect: vi.fn(),
    handleInputKeyDown: vi.fn(() => false),
    handleMessagesScroll: vi.fn(),
    handlePaste: vi.fn(),
    inputMessage: ref(''),
    interactionMode: ref('balanced'),
    interactionModeEffective: computed(() => 'balanced'),
    lastMemoryUpdated: ref(null),
    lastRunSummary: ref(null),
    loadAgentKBBindings: vi.fn(async () => []),
    loadAgentSkillBindings: vi.fn(async () => []),
    loadAgents: vi.fn(async () => undefined),
    loadConversationMessages: vi.fn(async () => undefined),
    loadConversations: vi.fn(async () => undefined),
    memoryLoading: ref(false),
    memoryState: ref(null),
    mentionActiveIndex: ref(-1),
    mentionCandidates: computed(() => []),
    mentionOpen: ref(false),
    messagesContainer: ref(null),
    pendingAttachments: ref([]),
    regenerateMessage: vi.fn(),
    rejectAction: vi.fn(),
    rejectConsent: vi.fn(),
    removePendingAttachment: vi.fn(),
    removeSelectedKnowledgeBase: vi.fn(),
    resetComposerEndpointState: vi.fn(),
    retryLastMessage: vi.fn(),
    selectedAgent,
    selectedAgentId,
    selectedKBIds: ref([]),
    selectMentionKnowledgeBase: vi.fn(),
    selectMentionSkillPackage: vi.fn(),
    sendMessage: vi.fn(async () => true),
    sending: ref(false),
    showScrollToBottom: ref(false),
    showScrollToTop: ref(false),
    startNewConversation: vi.fn(),
    stopGeneration: vi.fn(),
    streaming: ref(false),
    supportsVision: ref(false),
    totalTokensUsed: ref(0),
    updateConversationTitle: vi.fn(),
    uploading: ref(false),
  };
}

function installCollaboratorMocks() {
  mockState.createBindings = (options: any) => ({
    dragging: ref(false),
    effectivePanelStyle: computed(() => ({})),
    headerListeners: {},
    headerProps: computed(() => ({})),
    isFullMode: computed(() => false),
    onDragStart: vi.fn(),
    overlayListeners: {},
    overlayProps: computed(() => ({})),
    panelBodyListeners: {
      send: options.handleSendMessage,
    },
    panelBodyProps: computed(() => ({
      welcomeLoading: options.welcomeLoading.value,
      welcomeLoadingHint: options.welcomeLoadingHint.value,
    })),
    toolbarListeners: {},
    toolbarProps: computed(() => ({})),
  });

  mockState.createPanelHistory = () => ({
    cancelEditTitle: vi.fn(),
    commitEditTitle: vi.fn(),
    conversationSearch: ref(''),
    editingConversationId: ref(null),
    editingTitle: ref(''),
    groupedConversations: computed(() => []),
    onDeleteConversation: vi.fn(),
    onSelectConversation: vi.fn(),
    onStartNewChat: vi.fn(),
    startEditTitle: vi.fn(),
  });

  mockState.createPanelShellActions = () => ({
    askSuggested: vi.fn(),
    effectiveSuggestedQuestions: computed(() => []),
    effectiveWelcomeMessage: computed(() => ''),
    handleClose: vi.fn(),
    handleMinimize: vi.fn(),
    handleToggleDock: vi.fn(),
    handleToggleMode: vi.fn(),
    onDocumentClick: vi.fn(),
    panelRef: ref(null),
    unpinAgent: vi.fn(),
  });

  mockState.createPanelShellContext = () => ({
    agentVarsModalListeners: {},
    agentVarsModalProps: computed(() => ({})),
    canForceReroute: computed(() => false),
    clearRoutingIntent: vi.fn(),
    deferSendForMissingVariables: vi.fn(async () => false),
    forceRerouteNextTurn: ref(false),
    hasHeaderVariableValues: computed(() => false),
    headerConversationSummary: computed(() => null),
    headerMemoryHasAttention: computed(() => false),
    headerMoreHasAttention: computed(() => false),
    headerMoreMenuItems: computed(() => []),
    manualNewConversationAgentId: ref(null),
    onClearMemory: vi.fn(),
    onEditHeaderVars: vi.fn(),
    onToggleForceReroute: vi.fn(),
    onToggleMemory: vi.fn(),
    openVarsModal: vi.fn(),
    refreshTimeline: vi.fn(async () => undefined),
    routeNotice: computed(() => null),
    showContextDrawer: ref(false),
    showHeaderMemoryButton: computed(() => false),
    showHeaderMoreMenu: computed(() => false),
    showHeaderVarsButton: computed(() => false),
    showHistory: ref(false),
    showMemoryPanel: ref(false),
    showRouteNotice: computed(() => false),
    showTimelineDrawer: ref(false),
    timelineItems: computed(() => []),
    timelineLoading: ref(false),
    timelineRefreshing: ref(false),
  });
}

describe('useAIChatSlidePanelShell welcome loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockState.chatState = createChatState();
    installCollaboratorMocks();
  });

  it('drops an in-flight stale welcome response and requests welcome content for the switched agent', async () => {
    const alphaWelcome = createDeferred<{
      suggested_actions: string[];
      welcome_message: string;
    }>();
    const betaWelcome = createDeferred<{
      suggested_actions: string[];
      welcome_message: string;
    }>();
    vi.mocked(generateWelcomeMessageApi).mockImplementation(
      (_apiPrefix: string, agentId: number) => {
        return agentId === 1 ? alphaWelcome.promise : betaWelcome.promise;
      },
    );

    const aiPanelStore = useAIPanelStore();
    aiPanelStore.open();

    const shell = useAIChatSlidePanelShell(
      {
        apiPrefix: '/tenant',
        uploadUrl: '/upload',
      },
      vi.fn(),
    );

    await flushAsync();

    expect(generateWelcomeMessageApi).toHaveBeenCalledTimes(1);
    expect(vi.mocked(generateWelcomeMessageApi).mock.calls[0]?.[1]).toBe(1);
    expect(shell.panelBodyProps.value.welcomeLoading).toBe(true);

    const betaAgent = mockState.chatState.agents.value[1];
    mockState.chatState.selectedAgent.value = betaAgent;
    mockState.chatState.selectedAgentId.value = betaAgent.id;

    await flushAsync();

    expect(generateWelcomeMessageApi).toHaveBeenCalledTimes(1);

    alphaWelcome.resolve({
      suggested_actions: ['Alpha action'],
      welcome_message: 'Alpha stale welcome',
    });

    await flushAsync();

    expect(aiPanelStore.dynamicWelcomeMessage).toBeNull();
    expect(generateWelcomeMessageApi).toHaveBeenCalledTimes(2);
    expect(vi.mocked(generateWelcomeMessageApi).mock.calls[1]?.[1]).toBe(2);
    expect(shell.panelBodyProps.value.welcomeLoading).toBe(true);

    betaWelcome.resolve({
      suggested_actions: ['Beta action'],
      welcome_message: 'Beta current welcome',
    });

    await flushAsync();

    expect(aiPanelStore.dynamicWelcomeMessage).toBe('Beta current welcome');
    expect(aiPanelStore.welcomeSuggestedActions).toEqual(['Beta action']);
    expect(shell.panelBodyProps.value.welcomeLoading).toBe(false);
  });
});
