import type { ComponentPublicInstance } from 'vue';

import { computed, ref, toRef, watch } from 'vue';

import { generateWelcomeMessageApi } from '#/api/shared/ai-chat';
import { useAIChat } from '#/components/business/ai-chat-panel/use-ai-chat';
import { $t } from '#/locales';
import { resolveRuntimeLocale } from '#/locales/runtime-locale';
import { useAIPanelStore } from '#/store';
import { getAgentInputVariables } from '#/types/ai-chat';
import { useUserStore } from '@vben/stores';

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
    resetComposerEndpointState,
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

  // ============ Welcome message trigger / 欢迎语触发 ============
  const welcomeTriggerInFlight = ref(false);
  let welcomeRequestSeq = 0;
  let queuedWelcomeAgentId: null | number = null;
  const hasPendingStarterMessage = computed(() => {
    const propMessage = props.pendingMessage?.trim();
    const storeMessage = aiPanelStore.pendingMessage?.trim();
    return Boolean(propMessage || storeMessage);
  });
  const welcomeLoading = computed(
    () =>
      welcomeTriggerInFlight.value &&
      aiPanelStore.visible &&
      activeConversationId.value === null &&
      chatMessages.value.length === 0 &&
      !hasPendingStarterMessage.value &&
      !sending.value &&
      !routing.value,
  );
  const welcomeLoadingHint = computed(() => {
    const agentName = selectedAgent.value?.name?.trim();
    if (agentName) {
      return $t('common.globalAiChat.welcomeLoadingWithAgent', {
        agent: agentName,
      });
    }
    return $t('common.globalAiChat.welcomeLoading');
  });

  function canGenerateWelcomeForAgent(agentId: number) {
    return (
      aiPanelStore.visible &&
      activeConversationId.value === null &&
      chatMessages.value.length === 0 &&
      !hasPendingStarterMessage.value &&
      selectedAgent.value?.id === agentId &&
      !aiPanelStore.dynamicWelcomeMessage
    );
  }

  async function runWelcomeRequest(agentId: number) {
    if (welcomeTriggerInFlight.value) {
      queuedWelcomeAgentId = agentId;
      return;
    }

    const requestSeq = welcomeRequestSeq + 1;
    welcomeRequestSeq = requestSeq;
    welcomeTriggerInFlight.value = true;
    try {
      const userStore = useUserStore();
      const welcomePayload = {
        page_context: aiPanelStore.pageContext ?? undefined,
        user_context: {
          user_nickname: userStore.userInfo?.realName || '',
          current_time: new Date().toISOString(),
          locale: resolveRuntimeLocale(),
        },
      };
      const result = await generateWelcomeMessageApi(
        apiPrefix.value,
        agentId,
        welcomePayload,
      );
      if (
        requestSeq !== welcomeRequestSeq ||
        !aiPanelStore.visible ||
        activeConversationId.value !== null ||
        chatMessages.value.length > 0 ||
        selectedAgent.value?.id !== agentId ||
        hasPendingStarterMessage.value
      ) {
        return;
      }
      aiPanelStore.setDynamicWelcome(
        result.welcome_message,
        result.suggested_actions,
      );
    } catch {
      // Silently fall back to static welcome message
    } finally {
      if (requestSeq === welcomeRequestSeq) {
        welcomeTriggerInFlight.value = false;
        const queuedAgentId = queuedWelcomeAgentId;
        queuedWelcomeAgentId = null;
        if (
          queuedAgentId !== null &&
          queuedAgentId !== agentId &&
          canGenerateWelcomeForAgent(queuedAgentId)
        ) {
          void runWelcomeRequest(queuedAgentId);
        }
      }
    }
  }

  // Clear dynamic welcome when conversation resets to new state
  // 当对话重置为新会话时清除动态欢迎语
  watch(
    () =>
      [
        activeConversationId.value,
        selectedAgent.value?.id ?? null,
        chatMessages.value.length,
      ] as const,
    ([convId, , msgCount]) => {
      if (convId === null && msgCount === 0) {
        aiPanelStore.clearDynamicWelcome();
      }
    },
  );

  watch(
    () =>
      [
        activeConversationId.value,
        selectedAgent.value?.id ?? null,
        chatMessages.value.length,
        aiPanelStore.visible,
        hasPendingStarterMessage.value,
      ] as const,
    async ([convId, agentId, msgCount, visible, hasPendingMessage]) => {
      // Only trigger for new conversations with no messages when panel is visible
      if (
        convId !== null ||
        agentId === null ||
        msgCount > 0 ||
        !visible ||
        hasPendingMessage
      ) {
        queuedWelcomeAgentId = null;
        return;
      }
      // Don't re-trigger if already set
      if (aiPanelStore.dynamicWelcomeMessage) {
        queuedWelcomeAgentId = null;
        return;
      }

      void runWelcomeRequest(agentId);
    },
    { immediate: true },
  );

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
    onPageContextCollected: (ctx) => {
      aiPanelStore.setPageContext(
        ctx as Parameters<typeof aiPanelStore.setPageContext>[0],
      );
    },
    pendingConversationId: toRef(props, 'pendingConversationId'),
    pendingMessage: toRef(props, 'pendingMessage'),
    routing,
    selectedAgent,
    selectedAgentId,
    sending,
    sendMessage: ({ agentId }) => sendMessage({ agentId }),
    startNewConversation,
    resetEndpointCaches: resetComposerEndpointState,
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
    if (welcomeLoading.value) {
      return false;
    }
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
    retryLastMessage,
    routeNotice,
    routing,
    scrollToBottom,
    scrollToTop,
    selectedAgent,
    selectedAgentId,
    selectedKBIds,
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
    welcomeLoading,
    welcomeLoadingHint,
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
