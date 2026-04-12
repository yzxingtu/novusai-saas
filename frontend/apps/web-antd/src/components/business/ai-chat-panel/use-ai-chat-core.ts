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
import type { PageContext, RawMessageItem } from '#/api/shared/ai-chat';
import type { UseAIChatOptions } from './use-ai-chat-options';

import { computed, ref, unref, watch } from 'vue';

import { message } from 'ant-design-vue';

import { getChatAgentsApi } from '#/api/shared/ai-chat';
import {
  normalizePageKey,
  resolveRoutePageKey,
} from '#/components/business/ai-runtime/page-key-utils';
import { useFileUpload } from '#/composables/use-file-upload';
import { waitForPageSessionJoin } from '#/composables/use-ui-action-channel';
import { $t } from '#/locales';
import { useSocketIOStore } from '#/store';
import { useAIPanelStore } from '#/store/shared/ai-panel';
import { clearConsents } from '#/utils/ai-consent';
import { toAvatarDisplayUrl } from '#/utils/image';

import { useAIChatAttachments } from './use-ai-chat-attachments';
import { useAIChatComposer } from './use-ai-chat-composer';
import { useAIChatConversations } from './use-ai-chat-conversations';
import { useAIChatExport } from './use-ai-chat-export';
import { useAIChatInteractions } from './use-ai-chat-interactions';
import { useAIChatMemory } from './use-ai-chat-memory';
import { mergeMessagesForDisplay as mergeMessagesForDisplayHelper } from './use-ai-chat-message-helpers';
import { useAIChatStreaming, type PendingInteractionUpdate } from './use-ai-chat-streaming';
import { useAIChatVariables } from './use-ai-chat-variables';

export type { UseAIChatOptions } from './use-ai-chat-options';

interface SendMessageOptions {
  agentId?: number;
  pageContext?: null | PageContext;
  routeSource?: null | string;
  silent?: boolean;
}

export function useAIChat(options: UseAIChatOptions) {
  const { validateChatFile, revokePreviewUrls } = useFileUpload();
  const socketIOStore = useSocketIOStore();
  const aiPanelStore = useAIPanelStore();
  const PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS = 3000;
  const PAGE_OPERATION_SOCKET_READY_POLL_MS = 100;
  const PAGE_OPERATION_SOCKET_SETTLE_MS = 250;

  const interactionMode = ref<InteractionMode>('confirm');
  const interactionModeEffective = ref<InteractionMode>('confirm');

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

  function refreshPageSessionRoom(pageContext?: null | PageContext): void {
    const pageSessionId = options.pageSessionIdGetter?.();
    if (!pageSessionId || !socketIOStore.isConnected) return;
    socketIOStore.emit('page_session_join', {
      page_session_id: pageSessionId,
      page_key:
        normalizePageKey(pageContext?.page_key ?? '') ||
        resolveRoutePageKey(undefined, window.location.pathname),
    });
  }

  function hasInteractivePageContext(pageContext?: null | PageContext): boolean {
    if (!pageContext?.page_key) {
      return false;
    }

    const pageContextRecord = pageContext as unknown as Record<string, unknown>;

    if (
      typeof pageContextRecord.ui_epoch === 'number' ||
      Array.isArray(pageContextRecord.surface_stack as unknown[]) ||
      typeof pageContextRecord.active_surface_id === 'string' ||
      typeof pageContextRecord.active_form_session_id === 'string'
    ) {
      return true;
    }

    const suggestedTools = pageContextRecord.suggested_tools;
    return !!(
      suggestedTools &&
      typeof suggestedTools === 'object' &&
      Array.isArray((suggestedTools as Record<string, unknown>).primary) &&
      ((suggestedTools as Record<string, unknown>).primary as unknown[]).length >
        0
    );
  }

  function hasPageOperations(pageContext?: null | PageContext): boolean {
    return hasInteractivePageContext(pageContext);
  }

  function resolveSocketEndpoint(apiPrefix: string): 'admin' | 'tenant' | 'user' {
    if (apiPrefix.startsWith('/admin')) {
      return 'admin';
    }
    if (apiPrefix.startsWith('/api/user')) {
      return 'user';
    }
    return 'tenant';
  }

  async function ensurePageOperationChannelReady(
    apiPrefix: string,
    pageContext?: null | PageContext,
  ): Promise<boolean> {
    if (!hasInteractivePageContext(pageContext) || !options.pageSessionIdGetter) {
      return true;
    }

    if (!socketIOStore.isConnected) {
      socketIOStore.connect?.(resolveSocketEndpoint(apiPrefix));

      const startedAt = Date.now();
      while (
        !socketIOStore.isConnected &&
        Date.now() - startedAt < PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS
      ) {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, PAGE_OPERATION_SOCKET_READY_POLL_MS);
        });
      }
    }

    if (!socketIOStore.isConnected) {
      return false;
    }

    refreshPageSessionRoom(pageContext);
    const pageSessionId = options.pageSessionIdGetter?.() || '';
    const pageKey =
      normalizePageKey(pageContext?.page_key ?? '') ||
      resolveRoutePageKey(undefined, window.location.pathname);
    if (!pageSessionId || !pageKey) {
      return false;
    }

    const joined = await waitForPageSessionJoin(
      pageSessionId,
      pageKey,
      PAGE_OPERATION_SOCKET_READY_TIMEOUT_MS,
      PAGE_OPERATION_SOCKET_READY_POLL_MS,
    );
    if (!joined) {
      return false;
    }

    await new Promise<void>((resolve) => {
      setTimeout(resolve, PAGE_OPERATION_SOCKET_SETTLE_MS);
    });
    return true;
  }

  // ============ Agents / 智能体 ============

  const agents = ref<AgentItem[]>([]);
  const agentsLoading = ref(false);
  const selectedAgentId = ref<null | number>(null);
  const selectedAgent = computed(
    () => agents.value.find((agent) => agent.id === selectedAgentId.value) ?? null,
  );

  // ============ Chat Messages / 消息区 ============

  const chatMessages = ref<ChatMessage[]>([]);

  const {
    agentKBBindings,
    clearMentionDraft,
    handleInputKeyDown,
    inputMessage,
    loadAgentKBBindings,
    mentionActiveIndex,
    mentionCandidates,
    mentionOpen,
    removeSelectedKnowledgeBase,
    selectMentionKnowledgeBase,
    selectedKBIds,
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
    chatMessages.value.reduce((sum, messageItem) => sum + (messageItem.tokenUsage || 0), 0),
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
    ensurePageOperationChannelReady,
    hasPageOperations,
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

  async function loadAgents(overrideAgentId?: number) {
    agentsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const response = await getChatAgentsApi<AgentItem>(prefix);
      agents.value = response.items.map((agent) => {
        const avatar = toAvatarDisplayUrl(agent.avatar ?? undefined);
        return {
          ...agent,
          avatar: avatar || null,
        };
      });
      const firstAgent = response.items[0];
      if (firstAgent && !selectedAgentId.value) {
        const initialId = overrideAgentId ?? unref(options.initialAgentId);
        selectedAgentId.value =
          initialId && response.items.some((item) => item.id === initialId)
            ? initialId
            : firstAgent.id;
      }
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      agentsLoading.value = false;
    }
  }

  function selectAgent(agentId: number) {
    if (selectedAgentId.value === agentId) return;
    abortActiveStream();
    clearConsents();
    selectedAgentId.value = agentId;
    bumpConversationsRequestSeq();
    bumpMessagesRequestSeq();
    resetConversationState();
    interactionModeEffective.value = interactionMode.value;
    clearPendingAttachments();
    clearMentionDraft();
  }

  /**
   * Reset chat state / 重置对话状态
   * @param keepVars - When true (panel open/reopen), session vars are preserved.
   *                   When false (explicit "+" new chat), session vars are cleared.
   */
  function startNewConversation(keepVars = false) {
    abortActiveStream();
    clearConsents();
    bumpMessagesRequestSeq();
    resetPendingMessages();
    resetConversationState();
    interactionModeEffective.value = interactionMode.value;
    clearMentionDraft();
    resetMemoryState();
    if (!keepVars) {
      resetVariables();
    }
  }

  async function copyMessage(content: string) {
    try {
      await navigator.clipboard.writeText(content);
      message.success($t('common.globalAiChat.copySuccess'));
    } catch {
      // fallback silently / 剪贴板失败则静默
    }
  }

  function editAndResend(msgIndex: number) {
    if (sending.value || streaming.value) return;
    const messageItem = chatMessages.value[msgIndex];
    if (!messageItem || messageItem.role !== 'user') return;

    inputMessage.value = messageItem.content;
    chatMessages.value.splice(msgIndex);
    bumpMessagesRequestSeq();
    clearConversationAnchor();
    activeConversationId.value = null;
    if (typeof selectedAgentId.value === 'number') {
      activeConversationAgentId.value = selectedAgentId.value;
    } else {
      activeConversationAgentId.value = null;
    }
  }

  function regenerateMessage(msgIndex: number) {
    if (sending.value || streaming.value) return;
    const assistantMessage = chatMessages.value[msgIndex];
    if (!assistantMessage || assistantMessage.role !== 'assistant') return;

    let userMsgIndex = -1;
    for (let index = msgIndex - 1; index >= 0; index -= 1) {
      if (chatMessages.value[index]?.role === 'user') {
        userMsgIndex = index;
        break;
      }
    }
    if (userMsgIndex < 0) return;

    const userMessage = chatMessages.value[userMsgIndex];
    if (!userMessage || userMessage.role !== 'user') return;

    chatMessages.value.splice(msgIndex);
    bumpMessagesRequestSeq();
    clearConversationAnchor();
    activeConversationId.value = null;
    if (typeof selectedAgentId.value === 'number') {
      activeConversationAgentId.value = selectedAgentId.value;
    } else {
      activeConversationAgentId.value = null;
    }

    inputMessage.value = userMessage.content;
    clearPendingAttachments();
    if (userMessage.attachments?.length) {
      pendingAttachments.value = [...userMessage.attachments];
    }
    void sendMessage({ silent: true });
  }

  function stopGeneration() {
    abortActiveStream(true);
  }

  function retryLastMessage() {
    abortActiveStream();
    const messages = chatMessages.value;
    if (messages.length < 2) return;
    const lastMessage = messages.at(-1);
    if (lastMessage?.role !== 'assistant' || !lastMessage.requestFailedRetry) {
      return;
    }
    const previousMessage = messages.at(-2);
    if (previousMessage?.role !== 'user') {
      return;
    }

    chatMessages.value = messages.slice(0, -1);
    inputMessage.value = previousMessage.content;
    if (previousMessage.attachments?.length) {
      pendingAttachments.value = [...previousMessage.attachments];
    }
    void sendMessage({ silent: true });
  }

  function cleanup() {
    abortActiveStream();
  }

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
    agentKBBindings,
    loadAgentKBBindings,
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
    removeSelectedKnowledgeBase,
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
