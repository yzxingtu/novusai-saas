import type { ComponentPublicInstance } from 'vue';

import type { AIPageMode } from '@vben/types';

import { computed, ref, toRef } from 'vue';

import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { useModalDetector } from '#/composables/use-modal-detector';
import { getActivePageSessionId } from '#/composables/use-page-session';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { usePublicConfigStore } from '#/store/shared/public-config';
import { getAgentInputVariables } from '#/types/ai-chat';
import { normalizePageAIMode } from '#/utils/ai-page-capabilities';

import { useAgentRouter } from './use-agent-router';
import { useAIChatSlidePanelShellBindings } from './use-ai-chat-slide-panel-shell-bindings';
import { usePageAICapability } from './use-page-ai-capability';
import { usePanelHistory } from './use-panel-history';
import { usePanelSendMessage } from './use-panel-send-message';
import { usePanelShellActions } from './use-panel-shell-actions';
import { usePanelShellContext } from './use-panel-shell-context';
import { usePendingPageOps } from './use-pending-page-ops';

export interface AIChatSlidePanelShellProps {
  aiMode?: AIPageMode;
  apiPrefix: string;
  disabledCapabilities?: string[];
  disabledOperations?: string[];
  pageContextKey?: string;
  pendingConversationId?: null | number;
  pendingMessage?: null | string;
  showAttachments?: boolean;
  uploadUrl: string;
}

export interface AIChatSlidePanelShellEmit {
  (event: 'conversationRestored' | 'messageSent'): void;
}

export function useAIChatSlidePanelShell(
  props: AIChatSlidePanelShellProps,
  emit: AIChatSlidePanelShellEmit,
) {
  const aiPanelStore = useAIPanelStore();
  const publicConfigStore = usePublicConfigStore();
  const apiPrefix = toRef(props, 'apiPrefix');
  const disabledCapabilities = toRef(props, 'disabledCapabilities');
  const pageContextKey = toRef(props, 'pageContextKey');
  const showAttachments = computed(() => props.showAttachments ?? true);
  const uploadUrl = toRef(props, 'uploadUrl');
  const { modalState } = useModalDetector();
  const normalizedPageMode = computed(() => normalizePageAIMode(props.aiMode));
  const pageAIPolicy = computed(() => ({
    mode: normalizedPageMode.value,
    disabledCapabilities: props.disabledCapabilities,
    disabledOperations: props.disabledOperations,
  }));
  const panelTitle = computed(() => {
    return $t('common.aiPanel.title');
  });
  const isPinned = computed(
    () => !!aiPanelStore.pinnedAgentId && !!aiPanelStore.pinnedAgentName,
  );
  const unpinAgentRef = ref<() => void>(() => {});

  let openVarsModalRef: (
    vars: ReturnType<typeof getAgentInputVariables>,
    agentId: number,
    agentName: string,
  ) => void = () => {};

  const chat = useAIChat({
    apiPrefix,
    uploadUrl,
    onToolCall: (name: string, output: string) => {
      aiPanelStore.dispatchToolCall(name, output);
    },
    onStreamComplete: () => {
      aiPanelStore.markUnread();
    },
    pageContextResolver: () => currentPageContext.value,
    pageSessionIdGetter: getActivePageSessionId,
    onVariablesMissing: () => {
      const agent = selectedAgent.value;
      if (!agent) return;
      const inputVariables = getAgentInputVariables(agent);
      if (inputVariables.length > 0) {
        openVarsModalRef(inputVariables, agent.id, agent.name);
      }
    },
  });

  const {
    agents,
    agentsLoading,
    selectedAgentId,
    selectedAgent,
    loadAgents,
    conversations,
    conversationsLoading,
    activeConversationId,
    conversationContextDiagnostics,
    loadConversations,
    startNewConversation,
    deleteConversation,
    updateConversationTitle,
    loadConversationMessages,
    chatMessages,
    inputMessage,
    mentionOpen,
    mentionCandidates,
    mentionActiveIndex,
    sending,
    streaming,
    messagesContainer,
    sendMessage,
    stopGeneration,
    handleMessagesScroll,
    showScrollToBottom,
    showScrollToTop,
    scrollToBottom,
    scrollToTop,
    copyMessage,
    handleInputKeyDown,
    selectMentionKnowledgeBase,
    removeSelectedKnowledgeBase,
    selectedKBIds,
    cleanup,
    pendingAttachments,
    uploading,
    chatAcceptAttribute,
    handleFileSelect,
    handlePaste,
    handleDrop,
    handleDragOver,
    removePendingAttachment,
    confirmAction,
    rejectAction,
    confirmConsent,
    rejectConsent,
    interactionMode,
    interactionModeEffective,
    clickActionButton,
    regenerateMessage,
    editAndResend,
    retryLastMessage,
    clearConversationMemory,
    clearingMemory,
    fetchConversationMemory,
    memoryState,
    memoryLoading,
    lastMemoryUpdated,
    exportAsMarkdown,
    exportAsPlainText,
    lastRunSummary,
    totalTokensUsed,
    supportsVision,
    agentKBBindings,
    agentKBBindingsByAgentId,
    agentSkillBindingsByAgentId,
    allAgentsVariables,
    ensureAgentVarsLoaded,
    agentsWithVarsInConversation,
    applyVariables,
    loadAgentKBBindings,
    loadAgentSkillBindings,
  } = chat;

  const { countdownNow, getPendingOpsForMessage, unassociatedPendingOps } =
    usePendingPageOps({
      chatMessages,
      pendingPageOps: toRef(aiPanelStore, 'pendingPageOps'),
    });

  const exportMenuItems = computed(() => [
    {
      key: 'md',
      label: $t('common.globalAiChat.exportFormatMarkdown'),
      onClick: () => exportAsMarkdown(),
    },
    {
      key: 'txt',
      label: $t('common.globalAiChat.exportFormatPlainText'),
      onClick: () => exportAsPlainText(),
    },
  ]);

  const { routing, routeMessage } = useAgentRouter({
    apiPrefix,
    agents,
    pinnedAgentId: toRef(aiPanelStore, 'pinnedAgentId'),
    pinnedAgentName: toRef(aiPanelStore, 'pinnedAgentName'),
    activeConversationId,
  });

  const panelShellContext = usePanelShellContext({
    activeConversationId,
    agents,
    applyVariables,
    agentsWithVarsInConversation,
    allAgentsVariables,
    apiPrefix,
    chatMessages,
    clearConversationMemory,
    clearResolvedPageOps: () => aiPanelStore.clearResolvedPageOps?.(),
    consumePendingAgentId: () => aiPanelStore.consumePendingAgentId() ?? null,
    conversations,
    ensureAgentVarsLoaded,
    exportMenuItems,
    fetchConversationMemory,
    handleSendMessage: () => handleSendMessage(),
    inputMessage,
    isPinned,
    lastMemoryUpdated,
    loadAgents,
    loadConversationMessages,
    loadConversations,
    onConversationRestored: () => emit('conversationRestored'),
    onMessageSent: () => emit('messageSent'),
    panelStore: aiPanelStore,
    pendingConversationId: toRef(props, 'pendingConversationId'),
    pendingMessage: toRef(props, 'pendingMessage'),
    routing,
    selectedAgent,
    selectedAgentId,
    sending,
    sendMessage: ({ agentId, pageContext, routeSource }) =>
      sendMessage({ agentId, pageContext, routeSource }),
    startNewConversation,
    storePendingAgentId: toRef(aiPanelStore, 'pendingAgentId'),
    storePendingConversationId: toRef(aiPanelStore, 'pendingConversationId'),
    storePendingMessage: toRef(aiPanelStore, 'pendingMessage'),
    streaming,
    totalTokensUsed,
    unpinAgent: () => unpinAgentRef.value(),
    visible: toRef(aiPanelStore, 'visible'),
  });

  const {
    agentVarsModalListeners,
    agentVarsModalProps,
    canForceReroute,
    clearRoutingIntent,
    deferSendForMissingVariables,
    forceRerouteNextTurn,
    getRichTextDraftState,
    headerConversationSummary,
    headerMemoryHasAttention,
    headerMoreHasAttention,
    headerMoreMenuItems,
    hasHeaderVariableValues,
    manualNewConversationAgentId,
    onClearMemory,
    onEditHeaderVars,
    onToggleMemory,
    onRichTextApply,
    onRichTextDiscard,
    onRichTextUndo,
    onToggleForceReroute,
    openVarsModal,
    routeNotice,
    showContextDrawer,
    showHeaderMemoryButton,
    showHeaderMoreMenu,
    showHeaderVarsButton,
    showHistory,
    showMemoryPanel,
    showRouteNotice,
    showTimelineDrawer,
    timelineItems,
    timelineLoading,
    timelineRefreshing,
    refreshTimeline,
  } = panelShellContext;
  openVarsModalRef = openVarsModal;

  const pageContextLimitBytes = computed(
    () =>
      publicConfigStore.platformConfig?.runtimeLimits?.pageContextMaxBytes ||
      publicConfigStore.tenantConfig?.runtimeLimits?.pageContextMaxBytes,
  );
  const pageAICapability = usePageAICapability({
    apiPrefix,
    disabledCapabilities,
    modalState,
    normalizedPageMode,
    pageAIPolicy,
    pageContextKey,
    pageContextLimitBytes,
  });
  const currentPageContext = pageAICapability.currentPageContext;

  const { handleSendMessage: dispatchPanelMessage } = usePanelSendMessage({
    activeConversationId,
    agents,
    allAgentsVariables,
    currentPageContext,
    deferSendForMissingVariables,
    ensureAgentVarsLoaded,
    forceRerouteNextTurn,
    inputMessage,
    isPinned,
    manualNewConversationAgentId,
    pageContextKey,
    pendingAttachments,
    pinnedAgentId: toRef(aiPanelStore, 'pinnedAgentId'),
    routeMessage,
    selectedAgentId,
    sendMessage,
    showRouteNotice,
  });

  async function handleSendMessage() {
    return dispatchPanelMessage();
  }

  const history = usePanelHistory({
    clearResolvedPageOps: aiPanelStore.clearResolvedPageOps,
    clearRoutingIntent,
    conversations,
    deleteConversation,
    loadConversationMessages,
    showHistory,
    showMemoryPanel,
    startNewConversation,
    updateConversationTitle,
  });

  const shellActions = usePanelShellActions({
    aiPanelStore,
    handleSendMessage,
    inputMessage,
    selectedAgent,
  });
  unpinAgentRef.value = shellActions.unpinAgent;

  function setPanelRef(element: ComponentPublicInstance | Element | null) {
    const resolvedElement =
      element instanceof Element
        ? element
        : ((element?.$el as Element | null | undefined) ?? null);
    shellActions.panelRef.value =
      resolvedElement instanceof HTMLElement ? resolvedElement : null;
  }

  const bindings = useAIChatSlidePanelShellBindings({
    actionClick: clickActionButton,
    activeConversationId,
    agentKBBindings,
    agentKBBindingsByAgentId,
    agentSkillBindingsByAgentId,
    agents,
    agentsLoading,
    aiPanelStore,
    apiPrefix,
    askSuggested: shellActions.askSuggested,
    canForceReroute,
    cancelEditTitle: history.cancelEditTitle,
    chatAcceptAttribute,
    chatMessages,
    cleanup,
    clearResolvedPageOps: aiPanelStore.clearResolvedPageOps,
    clearingMemory,
    commitEditTitle: history.commitEditTitle,
    confirmAction,
    confirmConsent,
    conversationContextDiagnostics,
    conversationSearch: history.conversationSearch,
    conversations,
    conversationsLoading,
    copyMessage,
    countdownNow,
    editAndResend,
    editingConversationId: history.editingConversationId,
    editingTitle: history.editingTitle,
    effectiveSuggestedQuestions: shellActions.effectiveSuggestedQuestions,
    effectiveWelcomeMessage: shellActions.effectiveWelcomeMessage,
    ensureAgentVarsLoaded,
    exportMenuItems,
    forceRerouteNextTurn,
    getPendingOpsForMessage,
    getRichTextDraftState,
    groupedConversations: history.groupedConversations,
    handleClose: shellActions.handleClose,
    handleDragOver,
    handleDrop,
    handleFileSelect,
    handleInputKeyDown,
    handleMessagesScroll,
    handleMinimize: shellActions.handleMinimize,
    handlePaste,
    handleSendMessage,
    handleToggleDock: shellActions.handleToggleDock,
    handleToggleMode: shellActions.handleToggleMode,
    hasHeaderVariableValues,
    headerConversationSummary,
    headerMemoryHasAttention,
    headerMoreHasAttention,
    headerMoreMenuItems,
    inputMessage,
    interactionMode,
    interactionModeEffective,
    isPinned,
    lastRunSummary,
    manualNewConversationAgentId,
    memoryLoading,
    memoryState,
    mentionActiveIndex,
    mentionCandidates,
    mentionOpen,
    messagesContainer,
    loadAgentKBBindings,
    loadAgentSkillBindings,
    onClearMemory,
    onDeleteConversation: history.onDeleteConversation,
    onDocumentClick: shellActions.onDocumentClick,
    onEditHeaderVars,
    onToggleMemory,
    onRichTextApply,
    onRichTextDiscard,
    onRichTextUndo,
    onSelectConversation: history.onSelectConversation,
    onStartNewChat: history.onStartNewChat,
    onToggleForceReroute,
    pageAICapability,
    panelRef: shellActions.panelRef,
    panelTitle,
    pendingAttachments,
    refreshTimeline,
    regenerateMessage,
    rejectAction,
    rejectConsent,
    removePendingAttachment,
    removeSelectedKnowledgeBase,
    resolvePendingOp: (invokeId: string, allowed: boolean) =>
      aiPanelStore.resolvePageOp(invokeId, allowed),
    retryLastMessage,
    routeNotice,
    routing,
    scrollToBottom,
    scrollToTop,
    selectedAgent,
    selectedAgentId,
    selectedKBIds,
    selectMentionKnowledgeBase,
    sending,
    showAttachments,
    showHeaderMemoryButton,
    showContextDrawer,
    showHeaderMoreMenu,
    showHeaderVarsButton,
    showHistory,
    showMemoryPanel,
    showScrollToBottom,
    showScrollToTop,
    showTimelineDrawer,
    startEditTitle: history.startEditTitle,
    stopGeneration,
    streaming,
    supportsVision,
    timelineItems,
    timelineLoading,
    timelineRefreshing,
    totalTokensUsed,
    unassociatedPendingOps,
    uploadUrl,
    uploading,
  });

  return {
    aiPanelStore,
    agentVarsModalListeners,
    agentVarsModalProps,
    clearingMemory,
    headerListeners: bindings.headerListeners,
    headerProps: bindings.headerProps,
    isFullMode: bindings.isFullMode,
    dragging: bindings.dragging,
    effectivePanelStyle: bindings.effectivePanelStyle,
    onDragStart: bindings.onDragStart,
    memoryLoading,
    memoryState,
    onClearMemory,
    overlayListeners: bindings.overlayListeners,
    overlayProps: bindings.overlayProps,
    panelBodyListeners: bindings.panelBodyListeners,
    panelBodyProps: bindings.panelBodyProps,
    setPanelRef,
    showHistory,
    showMemoryPanel,
    streaming,
    toolbarListeners: bindings.toolbarListeners,
    toolbarProps: bindings.toolbarProps,
  };
}
