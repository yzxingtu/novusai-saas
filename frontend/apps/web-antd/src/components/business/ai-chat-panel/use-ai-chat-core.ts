/**
 * AI 对话 Composable / AI Chat Composable
 *
 * 封装全部 AI 对话业务逻辑：智能体加载、会话管理、SSE 流式、文件上传、
 * 工具调用、授权确认等。全页对话与全局抽屉对话共用。
 * Encapsulates all AI chat business logic: agent loading, conversation management,
 * SSE streaming, file uploads, tool calls, consent handling.
 * Used by both the full-page chat and the global drawer chat.
 */
import type { AgentItem, ChatMessage, InteractionMode } from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming';

import type { RawMessageItem } from '#/api/shared/ai-chat';

import { computed, ref, watch } from 'vue';

import { useFileUpload } from '#/composables/use-file-upload';
import { useAIPanelStore } from '#/store/shared/ai-panel';
import { clearConsents } from '#/utils/ai-consent';

import { useAIChatAttachments } from './use-ai-chat-attachments';
import { useAIChatComposer } from './use-ai-chat-composer';
import { useAIChatConversations } from './use-ai-chat-conversations';
import { createAIChatCoreActions } from './use-ai-chat-core-actions';
import { useAIChatExport } from './use-ai-chat-export';
import { useAIChatInteractions } from './use-ai-chat-interactions';
import { useAIChatMemory } from './use-ai-chat-memory';
import { mergeMessagesForDisplay as mergeMessagesForDisplayHelper } from './use-ai-chat-message-helpers';
import { useAIChatStreaming } from './use-ai-chat-streaming';
import { useAIChatVariables } from './use-ai-chat-variables';

export type { UseAIChatOptions } from './use-ai-chat-options';

interface SendMessageOptions {
  agentId?: number;
  routeSource?: null | string;
  silent?: boolean;
}

export function useAIChat(options: UseAIChatOptions) {
  const { validateChatFile, revokePreviewUrls } = useFileUpload();
  const aiPanelStore = useAIPanelStore();

  const interactionMode = ref<InteractionMode>('trusted_auto');
  const interactionModeEffective = ref<InteractionMode>('trusted_auto');

  watch(
    interactionMode,
    (mode) => {
      interactionModeEffective.value = mode;
    },
    { flush: 'sync' },
  );

  let abortActiveStreamImpl: (markStoppedByUser?: boolean) => void = () => {};
  let resetPendingMessagesImpl = () => {};
  let scrollToBottomImpl: (force?: boolean) => void = () => {};
  let sendMessageImpl: (
    options?: SendMessageOptions,
  ) => Promise<boolean> = async () => false;

  const abortActiveStream = (markStoppedByUser = false) =>
    abortActiveStreamImpl(markStoppedByUser);
  const resetPendingMessages = () => resetPendingMessagesImpl();
  const scrollToBottom = (force = false) => scrollToBottomImpl(force);
  const sendMessage = (sendOptions?: SendMessageOptions) =>
    sendMessageImpl(sendOptions);

  // ============ Agents / 智能体 ============

  const agents = ref<AgentItem[]>([]);
  const agentsLoading = ref(false);
  const selectedAgentId = ref<null | number>(null);
  const selectedAgent = computed(
    () =>
      agents.value.find((agent) => agent.id === selectedAgentId.value) ?? null,
  );

  // ============ Chat Messages / 消息区 ============

  const chatMessages = ref<ChatMessage[]>([]);

  const {
    agentKBBindings,
    agentKBBindingsByAgentId,
    agentSkillBindingsByAgentId,
    clearMentionDraft,
    getAgentKBBindings,
    getAgentSkillBindings,
    handleInputKeyDown,
    inputMessage,
    loadAgentKBBindings,
    loadAgentSkillBindings,
    mentionActiveIndex,
    mentionCandidates,
    mentionOpen,
    removeSelectedKnowledgeBase,
    removeSelectedSkillName,
    selectMentionKnowledgeBase,
    selectMentionSkillPackage,
    selectedKBIds,
    selectedSkillNames,
  } = useAIChatComposer({ options, selectedAgentId });

  const {
    agentsWithVarsInConversation,
    allAgentsVariables,
    applyVariables,
    clearConversationVarsCache,
    ensureAgentVarsLoaded,
    resetVariables,
  } = useAIChatVariables(agents, chatMessages);

  const lastMemoryUpdated = ref(false);

  // ============ Conversations / 会话 ============

  const {
    activeConversationAgentId,
    activeConversationId,
    bumpConversationsRequestSeq,
    bumpMessagesRequestSeq,
    clearConversationAnchor,
    conversationAnchorAgentId,
    conversationAnchorId,
    conversationContextDiagnostics,
    conversations,
    conversationsLoading,
    deleteConversation,
    lastRunSummary,
    loadConversationMessages,
    loadConversations,
    nextClientKey,
    recoverConversationIdFromHistory,
    rememberConversationAnchor,
    resetConversationState,
    syncConversationAfterInterrupt,
    updateConversationTitle,
  } = useAIChatConversations({
    agents,
    chatMessages,
    clearConsents,
    clearMentionDraft,
    ensureAgentVarsLoaded,
    interactionMode,
    interactionModeEffective,
    lastMemoryUpdated,
    mergeMessagesForDisplay: (rawMessages: RawMessageItem[]) =>
      mergeMessagesForDisplayHelper(rawMessages, agents.value),
    options,
    resetPendingMessages,
    scrollToBottom,
    selectedAgentId,
    abortActiveStream,
  });

  const {
    clearConversationMemory,
    clearingMemory,
    fetchConversationMemory,
    lastMemoryUpdated: sharedLastMemoryUpdated,
    memoryLoading,
    memoryState,
    resetMemoryState,
  } = useAIChatMemory({
    activeConversationId,
    lastMemoryUpdated,
    options,
  });

  // ============ Model Capabilities / 模型能力 ============

  const supportsVision = computed(
    () => selectedAgent.value?.model_capabilities?.supports_vision !== false,
  );
  const totalTokensUsed = computed(() =>
    chatMessages.value.reduce(
      (sum, messageItem) => sum + (messageItem.tokenUsage || 0),
      0,
    ),
  );

  const imageParams = ref({
    n: 1,
    quality: 'standard',
    size: '1024x1024',
    style: 'vivid',
  });

  const maxImageCount = computed(
    () => selectedAgent.value?.model_capabilities?.max_image_count ?? 5,
  );
  const maxImageSizeMb = computed(
    () => selectedAgent.value?.model_capabilities?.max_image_size_mb ?? 10,
  );

  const {
    chatAcceptAttribute,
    clearPendingAttachments,
    fileInput,
    handleDragOver,
    handleDrop,
    handleFileSelect,
    handlePaste,
    pendingAttachments,
    removePendingAttachment,
    uploadFile,
    uploading,
  } = useAIChatAttachments({
    maxImageCount,
    maxImageSizeMb,
    options,
    revokePreviewUrls,
    supportsVision,
    validateChatFile,
  });

  // ============ Interactions / 交互 ============

  const pendingInteractionUpdates = ref<PendingInteractionUpdate[]>([]);
  const {
    clickActionButton,
    confirmAction,
    confirmConsent,
    rejectAction,
    rejectConsent,
  } = useAIChatInteractions({
    chatMessages,
    inputMessage,
    pendingInteractionUpdates,
    sendMessage,
  });

  // ============ Streaming / 流式 ============

  const {
    handleMessagesScroll,
    messagesContainer,
    resetPendingMessages: resetPendingMessagesFromStreaming,
    scrollToBottom: scrollToBottomFromStreaming,
    scrollToTop,
    sendMessage: sendMessageFromStreaming,
    sending,
    streaming,
    userNotAtTop,
    userScrolledUp,
    abortActiveStream: abortActiveStreamFromStreaming,
  } = useAIChatStreaming({
    activeConversationAgentId,
    activeConversationId,
    agentKBBindings,
    agents,
    allAgentsVariables,
    apiPrefix: options.apiPrefix,
    bumpMessagesRequestSeq,
    chatMessages,
    clearConversationAnchor,
    clearPendingAttachments,
    conversationAnchorAgentId,
    conversationAnchorId,
    conversationContextDiagnostics,
    conversations,
    ensureAgentVarsLoaded,
    imageParams,
    inputMessage,
    interactionMode,
    interactionModeEffective,
    lastMemoryUpdated: sharedLastMemoryUpdated,
    lastRunSummary,
    loadConversations,
    memoryState,
    nextClientKey,
    options,
    pendingAttachments,
    pendingInteractionUpdates,
    recoverConversationIdFromHistory,
    rememberConversationAnchor,
    selectedAgentId,
    selectedKBIds,
    selectedSkillNames,
    syncConversationAfterInterrupt,
    uiPanelStore: aiPanelStore,
  });

  abortActiveStreamImpl = abortActiveStreamFromStreaming;
  resetPendingMessagesImpl = resetPendingMessagesFromStreaming;
  scrollToBottomImpl = scrollToBottomFromStreaming;
  sendMessageImpl = sendMessageFromStreaming;

  // ============ Export / 导出 ============

  const { exportAsMarkdown, exportAsPlainText } = useAIChatExport({
    activeConversationId,
    chatMessages,
    selectedAgent,
  });

  const {
    cleanup,
    copyMessage,
    editAndResend,
    loadAgents,
    regenerateMessage,
    retryLastMessage,
    selectAgent,
    startNewConversation,
    stopGeneration,
  } = createAIChatCoreActions({
    abortActiveStream,
    activeConversationAgentId,
    activeConversationId,
    agents,
    agentsLoading,
    bumpConversationsRequestSeq,
    bumpMessagesRequestSeq,
    chatMessages,
    clearConversationAnchor,
    clearMentionDraft,
    clearPendingAttachments,
    inputMessage,
    interactionMode,
    interactionModeEffective,
    options,
    pendingAttachments,
    resetConversationState,
    resetMemoryState,
    resetPendingMessages,
    resetVariables,
    selectedAgentId,
    sendMessage,
    sending,
    streaming,
  });

  return {
    agents,
    agentsLoading,
    selectedAgentId,
    selectedAgent,
    loadAgents,
    selectAgent,

    conversations,
    conversationsLoading,
    activeConversationId,
    conversationContextDiagnostics,
    loadConversations,
    startNewConversation,
    deleteConversation,
    updateConversationTitle,
    clearConversationMemory,
    clearingMemory,
    fetchConversationMemory,
    memoryState,
    memoryLoading,
    lastMemoryUpdated: sharedLastMemoryUpdated,
    loadConversationMessages,

    chatMessages,
    inputMessage,
    mentionOpen,
    mentionCandidates,
    mentionActiveIndex,
    selectedKBIds,
    selectedSkillNames,
    agentKBBindings,
    agentKBBindingsByAgentId,
    agentSkillBindingsByAgentId,
    getAgentKBBindings,
    getAgentSkillBindings,
    loadAgentKBBindings,
    loadAgentSkillBindings,
    allAgentsVariables,
    ensureAgentVarsLoaded,
    agentsWithVarsInConversation,
    applyVariables,
    resetVariables,
    clearConversationVarsCache,
    sending,
    streaming,
    messagesContainer,
    sendMessage,
    stopGeneration,
    scrollToBottom,
    scrollToTop,
    handleMessagesScroll,
    showScrollToBottom: userScrolledUp,
    showScrollToTop: userNotAtTop,
    copyMessage,
    handleInputKeyDown,
    selectMentionKnowledgeBase,
    selectMentionSkillPackage,
    removeSelectedKnowledgeBase,
    removeSelectedSkillName,
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
    cleanup,

    supportsVision,
    imageParams,
    exportAsMarkdown,
    exportAsPlainText,
    lastRunSummary,
    totalTokensUsed,

    pendingAttachments,
    uploading,
    fileInput,
    chatAcceptAttribute,
    uploadFile,
    handleFileSelect,
    handlePaste,
    handleDrop,
    handleDragOver,
    removePendingAttachment,
    clearPendingAttachments,
  };
}
