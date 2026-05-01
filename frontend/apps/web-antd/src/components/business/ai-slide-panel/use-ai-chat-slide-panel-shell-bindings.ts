import type { UseAIChatSlidePanelShellBindingsOptions } from './use-ai-chat-slide-panel-shell-bindings-contract';

import { computed } from 'vue';

import { $t } from '#/locales';

import { usePanelComposer } from './use-panel-composer';
import { usePanelShellBodyBindings } from './use-panel-shell-body-bindings';
import { usePanelShellComputedUI } from './use-panel-shell-computed-ui';
import { usePanelShellHeaderBindings } from './use-panel-shell-header-bindings';
import { usePanelShellLifecycle } from './use-panel-shell-lifecycle';
import { usePanelShellRuntimeVisuals } from './use-panel-shell-runtime-visuals';
import { usePanelWidth } from './use-panel-width';

export function useAIChatSlidePanelShellBindings(
  options: UseAIChatSlidePanelShellBindingsOptions,
) {
  const compactMessages = computed(() => true);

  const headerBindings = usePanelShellHeaderBindings({
    activeConversationId: options.activeConversationId,
    aiPanelStore: options.aiPanelStore,
    canForceReroute: options.canForceReroute,
    forceRerouteNextTurn: options.forceRerouteNextTurn,
    headerConversationSummary: options.headerConversationSummary,
    headerMemoryHasAttention: options.headerMemoryHasAttention,
    headerMoreHasAttention: options.headerMoreHasAttention,
    headerMoreMenuItems: options.headerMoreMenuItems,
    hasHeaderVariableValues: options.hasHeaderVariableValues,
    memoryLoading: options.memoryLoading,
    onEditHeaderVars: options.onEditHeaderVars,
    onToggleMemory: options.onToggleMemory,
    onToggleForceReroute: options.onToggleForceReroute,
    panelTitle: options.panelTitle,
    routeNotice: options.routeNotice,
    routing: options.routing,
    showHeaderMemoryButton: options.showHeaderMemoryButton,
    showHeaderMoreMenu: options.showHeaderMoreMenu,
    showHeaderVarsButton: options.showHeaderVarsButton,
    showHistory: options.showHistory,
    showMemoryPanel: options.showMemoryPanel,
    showContextDrawer: options.showContextDrawer,
    showTimelineDrawer: options.showTimelineDrawer,
    timelineItems: options.timelineItems,
    timelineLoading: options.timelineLoading,
    timelineRefreshing: options.timelineRefreshing,
    refreshTimeline: options.refreshTimeline,
    isPinned: options.isPinned,
    toggleHistory: () => {
      options.showHistory.value = !options.showHistory.value;
      if (!options.showHistory.value) {
        options.conversationSearch.value = '';
      }
    },
    onStartNewChat: options.onStartNewChat,
    handleClose: options.handleClose,
    handleMinimize: options.handleMinimize,
    handleToggleDock: options.handleToggleDock,
    handleToggleMode: options.handleToggleMode,
  });

  const {
    composerAttachmentLimitHint,
    composerAttachments,
    composerBoundKnowledgeBases,
    composerMentionCandidates,
    onSelectMentionCandidate,
    composerSelectedKnowledgeBases,
    composerSelectedSkillPackages,
    composerSendDisabled,
    composerSendState,
  } = usePanelComposer({
    agents: options.agents,
    agentKBBindings: options.agentKBBindings,
    inputMessage: options.inputMessage,
    mentionActiveIndex: options.mentionActiveIndex,
    mentionCandidates: options.mentionCandidates,
    pendingAttachments: options.pendingAttachments,
    routing: options.routing,
    selectedKBIds: options.selectedKBIds,
    selectedSkillNames: options.selectedSkillNames,
    selectMentionKnowledgeBase: options.selectMentionKnowledgeBase,
    selectMentionSkillPackage: options.selectMentionSkillPackage,
    sending: options.sending,
    showAttachments: options.showAttachments,
    streaming: options.streaming,
    uploading: options.uploading,
  });

  const {
    mentionEmptyHint,
    resolvedAttachmentAccept,
  } = usePanelShellComputedUI({
    agentKBBindings: options.agentKBBindings,
    agentsLoading: options.agentsLoading,
    chatAcceptAttribute: options.chatAcceptAttribute,
    mentionCandidates: options.mentionCandidates,
  });

  const overlayBindings = usePanelShellRuntimeVisuals({
    aiPanelStore: options.aiPanelStore,
    conversationContextDiagnostics: options.conversationContextDiagnostics,
    lastRunSummary: options.lastRunSummary,
    refreshTimeline: headerBindings.refreshTimeline,
    showContextDrawer: headerBindings.showContextDrawer,
    showTimelineDrawer: headerBindings.showTimelineDrawer,
    timelineItems: headerBindings.timelineItems,
    timelineLoading: headerBindings.timelineLoading,
    timelineRefreshing: headerBindings.timelineRefreshing,
  });

  function registerMessagesContainer(element: HTMLDivElement | null) {
    options.messagesContainer.value = element;
  }

  const { panelBodyListeners, panelBodyProps } = usePanelShellBodyBindings({
    actionClick: options.actionClick,
    activeConversationId: options.activeConversationId,
    agentKBBindings: options.agentKBBindings,
    agentKnowledgeBaseMap: computed(
      () => options.agentKBBindingsByAgentId?.value ?? {},
    ),
    agentSkillMap: computed(
      () => options.agentSkillBindingsByAgentId?.value ?? {},
    ),
    agents: options.agents,
    apiPrefix: options.apiPrefix,
    askSuggested: options.askSuggested,
    attachmentAccept: resolvedAttachmentAccept,
    attachmentLimitHint: composerAttachmentLimitHint,
    attachments: composerAttachments,
    attachDisabled: computed(
      () => options.agents.value.length === 0 || options.sending.value,
    ),
    boundKnowledgeBases: composerBoundKnowledgeBases,
    cancelEditTitle: options.cancelEditTitle,
    chatMessages: options.chatMessages,
    characterCount: computed(() => options.inputMessage.value.length),
    commitEditTitle: options.commitEditTitle,
    compactMessages,
    composerMentionCandidates,
    confirmAction: options.confirmAction,
    confirmConsent: options.confirmConsent,
    conversationSearch: options.conversationSearch,
    conversationsCount: computed(() => options.conversations.value.length),
    conversationsLoading: options.conversationsLoading,
    copyMessage: options.copyMessage,
    editAndResend: options.editAndResend,
    editingConversationId: options.editingConversationId,
    editingTitle: options.editingTitle,
    effectiveSuggestedQuestions: options.effectiveSuggestedQuestions,
    effectiveWelcomeMessage: options.effectiveWelcomeMessage,
    exportMenuItems: options.exportMenuItems,
    fileSelect: options.handleFileSelect,
    groupedConversations: options.groupedConversations,
    handleDragOver: options.handleDragOver,
    handleDrop: options.handleDrop,
    handleInputKeyDown: options.handleInputKeyDown,
    handleMessagesScroll: options.handleMessagesScroll,
    handleOpenUrl: overlayBindings.handleOpenUrl,
    handleSendMessage: options.handleSendMessage,
    ensureAgentKnowledgeBases: options.loadAgentKBBindings,
    ensureAgentSkills: options.loadAgentSkillBindings,
    inputMessage: options.inputMessage,
    mentionEmptyHint,
    mentionLoading: options.agentsLoading,
    mentionMixedHint: $t('common.globalAiChat.mentionMixedHint'),
    mentionOpen: options.mentionOpen,
    newChat: options.onStartNewChat,
    onDeleteConversation: options.onDeleteConversation,
    onSelectConversation: options.onSelectConversation,
    onSelectMentionCandidate,
    paste: options.handlePaste,
    regenerateMessage: options.regenerateMessage,
    registerMessagesContainer,
    rejectAction: options.rejectAction,
    rejectConsent: options.rejectConsent,
    removeAttachment: options.removePendingAttachment,
    removeSelectedKnowledgeBase: options.removeSelectedKnowledgeBase,
    removeSelectedSkillName: options.removeSelectedSkillName,
    retryLastMessage: options.retryLastMessage,
    routing: options.routing,
    scrollToBottom: options.scrollToBottom,
    scrollToTop: options.scrollToTop,
    selectedAgent: options.selectedAgent,
    selectedKnowledgeBases: composerSelectedKnowledgeBases,
    selectedSkillPackages: composerSelectedSkillPackages,
    sendDisabled: composerSendDisabled,
    sending: options.sending,
    sendState: composerSendState,
    shiftEnterHint: $t('common.globalAiChat.shiftEnterHint'),
    showAttachments: options.showAttachments,
    showHistory: options.showHistory,
    showScrollToBottom: options.showScrollToBottom,
    showScrollToTop: options.showScrollToTop,
    startEditTitle: options.startEditTitle,
    stopGeneration: options.stopGeneration,
    streaming: options.streaming,
    totalTokensUsed: options.totalTokensUsed,
  });

  const {
    dragging,
    effectivePanelStyle,
    isFullMode,
    loadSavedWidth,
    onDragStart,
  } = usePanelWidth(options.aiPanelStore);

  usePanelShellLifecycle({
    activeConversationId: options.activeConversationId,
    agents: options.agents,
    cleanup: options.cleanup,
    ensureAgentVarsLoaded: options.ensureAgentVarsLoaded,
    loadSavedWidth,
    manualNewConversationAgentId: options.manualNewConversationAgentId,
    onDocumentClick: options.onDocumentClick,
    panelStore: options.aiPanelStore,
    selectedAgentId: options.selectedAgentId,
  });

  return {
    dragging,
    effectivePanelStyle,
    headerListeners: headerBindings.headerListeners,
    headerProps: headerBindings.headerProps,
    isFullMode,
    onDragStart,
    overlayListeners: overlayBindings.overlayListeners,
    overlayProps: overlayBindings.overlayProps,
    panelBodyListeners,
    panelBodyProps,
    panelRef: options.panelRef,
    toolbarListeners: headerBindings.toolbarListeners,
    toolbarProps: headerBindings.toolbarProps,
  };
}
