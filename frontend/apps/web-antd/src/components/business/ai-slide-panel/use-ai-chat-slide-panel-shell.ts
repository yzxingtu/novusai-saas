import type { ComponentPublicInstance } from 'vue';

import { computed, ref, toRef } from 'vue';

import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';
import { getAgentInputVariables } from '#/types/ai-chat';

import { useAgentRouter } from './use-agent-router';
import { useAIChatSlidePanelShellBindings } from './use-ai-chat-slide-panel-shell-bindings';
import { usePanelHistory } from './use-panel-history';
import { usePanelSendMessage } from './use-panel-send-message';
import { usePanelShellActions } from './use-panel-shell-actions';
import { usePanelShellContext } from './use-panel-shell-context';

export interface AIChatSlidePanelShellProps {
  apiPrefix: string;
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
  const apiPrefix = toRef(props, 'apiPrefix');
  const showAttachments = computed(() => props.showAttachments ?? true);
  const uploadUrl = toRef(props, 'uploadUrl');
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
    onStreamComplete: () => {
      aiPanelStore.markUnread();
    },
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
    selectMentionSkillPackage,
    removeSelectedKnowledgeBase,
    removeSelectedSkillName,
    selectedKBIds,
    selectedSkillNames,
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
    pendingConversationId: toRef(props, 'pendingConversationId'),
    pendingMessage: toRef(props, 'pendingMessage'),
    routing,
    selectedAgent,
    selectedAgentId,
    sending,
    sendMessage: ({ agentId }) => sendMessage({ agentId }),
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
    headerConversationSummary,
    headerMemoryHasAttention,
    headerMoreHasAttention,
    headerMoreMenuItems,
    hasHeaderVariableValues,
    manualNewConversationAgentId,
    onClearMemory,
    onEditHeaderVars,
    onToggleMemory,
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

  const { handleSendMessage: dispatchPanelMessage } = usePanelSendMessage({
    activeConversationId,
    agents,
    allAgentsVariables,
    deferSendForMissingVariables,
    ensureAgentVarsLoaded,
    forceRerouteNextTurn,
    inputMessage,
    isPinned,
    manualNewConversationAgentId,
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
    clearingMemory,
    commitEditTitle: history.commitEditTitle,
    confirmAction,
    confirmConsent,
    conversationContextDiagnostics,
    conversationSearch: history.conversationSearch,
    conversations,
    conversationsLoading,
    copyMessage,
    editAndResend,
    editingConversationId: history.editingConversationId,
    editingTitle: history.editingTitle,
    effectiveSuggestedQuestions: shellActions.effectiveSuggestedQuestions,
    effectiveWelcomeMessage: shellActions.effectiveWelcomeMessage,
    ensureAgentVarsLoaded,
    exportMenuItems,
    forceRerouteNextTurn,
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
    onSelectConversation: history.onSelectConversation,
    onStartNewChat: history.onStartNewChat,
    onToggleForceReroute,
    panelRef: shellActions.panelRef,
    panelTitle,
    pendingAttachments,
    refreshTimeline,
    regenerateMessage,
    rejectAction,
    rejectConsent,
    removePendingAttachment,
    removeSelectedKnowledgeBase,
    removeSelectedSkillName,
    retryLastMessage,
    routeNotice,
    routing,
    scrollToBottom,
    scrollToTop,
    selectedAgent,
    selectedAgentId,
    selectedKBIds,
    selectedSkillNames,
    selectMentionKnowledgeBase,
    selectMentionSkillPackage,
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
