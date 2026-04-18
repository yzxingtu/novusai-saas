import type { Ref } from 'vue';

import type {
  AgentItem,
  ChatMessage,
  ConversationItem,
  InteractionMode,
} from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';

import type {
  ConversationDetailResponse,
  RawMessageItem,
} from '#/api/shared/ai-chat';

import { ref, unref } from 'vue';

import {
  deleteChatConversationApi,
  getChatConversationMessagesApi,
  getGlobalConversationsApi,
  updateChatConversationTitleApi,
} from '#/api/shared/ai-chat';

import { shouldDisplayConversationInHistory } from './use-ai-chat-history';

interface UseAIChatConversationsDeps {
  agents: Ref<AgentItem[]>;
  chatMessages: Ref<ChatMessage[]>;
  clearConsents: () => void;
  clearMentionDraft: () => void;
  ensureAgentVarsLoaded: (agentId: number) => void;
  interactionMode: Ref<InteractionMode>;
  interactionModeEffective: Ref<InteractionMode>;
  lastMemoryUpdated: Ref<boolean>;
  mergeMessagesForDisplay: (rawMessages: RawMessageItem[]) => ChatMessage[];
  options: UseAIChatOptions;
  resetPendingMessages: () => void;
  scrollToBottom: (force?: boolean) => void;
  selectedAgentId: Ref<null | number>;
  abortActiveStream: () => void;
}

const INTERRUPTED_HISTORY_SYNC_ATTEMPTS = 3;
const INTERRUPTED_HISTORY_SYNC_RETRY_DELAY_MS = 300;

export function useAIChatConversations(deps: UseAIChatConversationsDeps) {
  const {
    chatMessages,
    clearConsents,
    clearMentionDraft,
    ensureAgentVarsLoaded,
    interactionMode,
    interactionModeEffective,
    lastMemoryUpdated,
    mergeMessagesForDisplay,
    options,
    resetPendingMessages,
    scrollToBottom,
    selectedAgentId,
    abortActiveStream,
  } = deps;

  const conversations = ref<ConversationItem[]>([]);
  const conversationsLoading = ref(false);
  const activeConversationId = ref<null | number>(null);
  const activeConversationAgentId = ref<null | number>(null);
  const conversationContextDiagnostics = ref<null | Record<string, unknown>>(
    null,
  );
  const lastRunSummary = ref<null | Record<string, unknown>>(null);
  const conversationAnchorId = ref<null | number>(null);
  const conversationAnchorAgentId = ref<null | number>(null);

  /** Request sequence guard: prevents stale async responses from overriding latest state / 请求序号防护：避免旧异步响应覆盖最新状态 */
  let conversationsRequestSeq = 0;
  let messagesRequestSeq = 0;
  let clientMessageSeq = 0;

  /** Guard: only restore initialConversationId once / 仅恢复一次 initialConversationId */
  let _initialConvRestored = false;

  function nextClientKey(prefix: string) {
    clientMessageSeq += 1;
    return `${prefix}-${Date.now()}-${clientMessageSeq}`;
  }

  function bumpMessagesRequestSeq() {
    messagesRequestSeq += 1;
  }

  function bumpConversationsRequestSeq() {
    conversationsRequestSeq += 1;
  }

  function rememberConversationAnchor(
    conversationId: null | number,
    agentId?: null | number,
  ) {
    if (typeof conversationId === 'number' && Number.isFinite(conversationId)) {
      conversationAnchorId.value = conversationId;
    }
    if (agentId !== undefined) {
      conversationAnchorAgentId.value = agentId ?? null;
    }
  }

  function clearConversationAnchor() {
    conversationAnchorId.value = null;
    conversationAnchorAgentId.value = null;
  }

  function resetConversationState() {
    activeConversationId.value = null;
    activeConversationAgentId.value = null;
    clearConversationAnchor();
    chatMessages.value = [];
    conversationContextDiagnostics.value = null;
    lastRunSummary.value = null;
  }

  async function loadConversations() {
    const reqSeq = ++conversationsRequestSeq;
    conversationsLoading.value = true;
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getGlobalConversationsApi<ConversationItem>(prefix);
      if (reqSeq !== conversationsRequestSeq) {
        return;
      }
      const nowMs = Date.now();
      conversations.value = res.items.filter((conversation) =>
        shouldDisplayConversationInHistory(conversation, {
          activeConversationId: activeConversationId.value,
          nowMs,
        }),
      );

      // Auto-load initial conversation (only once) / 仅一次自动加载初始会话
      const initConvId = unref(options.initialConversationId);
      if (
        initConvId &&
        !_initialConvRestored &&
        conversations.value.some((c) => c.id === initConvId)
      ) {
        _initialConvRestored = true;
        await loadConversationMessages(initConvId);
      }
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    } finally {
      if (reqSeq === conversationsRequestSeq) {
        conversationsLoading.value = false;
      }
    }
  }

  function applyConversationDetailState(
    convId: number,
    res: ConversationDetailResponse,
    mergedMessages = mergeMessagesForDisplay(res.message_list ?? []),
  ) {
    const resolvedAgentId =
      res.agent_id ??
      activeConversationAgentId.value ??
      conversationAnchorAgentId.value ??
      selectedAgentId.value;
    if (resolvedAgentId) {
      selectedAgentId.value = resolvedAgentId;
      activeConversationAgentId.value = resolvedAgentId;
    }
    rememberConversationAnchor(convId, resolvedAgentId ?? null);

    const agentId = selectedAgentId.value;
    if (agentId) {
      ensureAgentVarsLoaded(agentId);
    }

    chatMessages.value = mergedMessages;
    conversationContextDiagnostics.value =
      (res.context_diagnostics as null | Record<string, unknown> | undefined) ??
      null;
    lastRunSummary.value =
      (res.last_run_summary as null | Record<string, unknown> | undefined) ??
      null;
    lastMemoryUpdated.value = mergedMessages.some((m) => m.memoryUpdated);
    const nextInteractionModeEffective =
      res.interaction_mode_effective ?? 'trusted_auto';
    interactionMode.value =
      res.interaction_mode_requested ?? nextInteractionModeEffective;
    interactionModeEffective.value = nextInteractionModeEffective;
    scrollToBottom(true);
  }

  async function syncConversationAfterInterrupt(
    convId: number,
    minimumMessageCount: number,
  ) {
    await loadConversations();
    if (activeConversationId.value !== convId) {
      return;
    }

    const prefix = unref(options.apiPrefix) as string;
    let fallbackMerged: ChatMessage[] | null = null;
    let fallbackResponse: ConversationDetailResponse | null = null;

    for (
      let attempt = 0;
      attempt < INTERRUPTED_HISTORY_SYNC_ATTEMPTS;
      attempt++
    ) {
      const res = await getChatConversationMessagesApi(prefix, convId);
      if (!res || typeof res !== 'object') {
        if (attempt < INTERRUPTED_HISTORY_SYNC_ATTEMPTS - 1) {
          await new Promise<void>((resolve) => {
            setTimeout(resolve, INTERRUPTED_HISTORY_SYNC_RETRY_DELAY_MS);
          });
        }
        continue;
      }
      if (activeConversationId.value !== convId) {
        return;
      }

      const merged = mergeMessagesForDisplay(res.message_list ?? []);
      fallbackResponse = res;
      fallbackMerged = merged;

      if (minimumMessageCount <= 0 || merged.length >= minimumMessageCount) {
        applyConversationDetailState(convId, res, merged);
        return;
      }

      if (attempt < INTERRUPTED_HISTORY_SYNC_ATTEMPTS - 1) {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, INTERRUPTED_HISTORY_SYNC_RETRY_DELAY_MS);
        });
      }
    }

    if (
      !fallbackResponse ||
      !fallbackMerged ||
      activeConversationId.value !== convId
    ) {
      return;
    }

    if (
      minimumMessageCount > 0 &&
      fallbackMerged.length < minimumMessageCount &&
      chatMessages.value.length >= minimumMessageCount
    ) {
      return;
    }

    applyConversationDetailState(convId, fallbackResponse, fallbackMerged);
  }

  function recoverConversationIdFromHistory(
    knownConversationIds: ReadonlySet<number>,
    targetAgentId: number,
  ): null | number {
    const candidates = conversations.value.filter((conversation) => {
      if (knownConversationIds.has(conversation.id)) {
        return false;
      }
      return Number(conversation.agent_id ?? 0) === targetAgentId;
    });

    if (candidates.length !== 1) {
      return null;
    }
    return candidates[0]?.id ?? null;
  }

  async function deleteConversation(convId: number) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      await deleteChatConversationApi(prefix, convId);
      if (activeConversationId.value === convId) {
        clearConsents();
        bumpMessagesRequestSeq();
        resetConversationState();
      }
      await loadConversations();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function updateConversationTitle(convId: number, title: string) {
    try {
      const prefix = unref(options.apiPrefix) as string;
      await updateChatConversationTitleApi(prefix, convId, title);
      const conv = conversations.value.find((c) => c.id === convId);
      if (conv) conv.title = title || null;
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function loadConversationMessages(convId: number) {
    abortActiveStream();
    clearConsents();
    const reqSeq = ++messagesRequestSeq;
    resetPendingMessages();
    activeConversationId.value = convId;
    clearMentionDraft();
    const currentConversation = conversations.value.find(
      (c) => c.id === convId,
    );
    if (currentConversation?.agent_id) {
      selectedAgentId.value = currentConversation.agent_id;
      activeConversationAgentId.value = currentConversation.agent_id;
      rememberConversationAnchor(convId, currentConversation.agent_id);
    } else {
      activeConversationAgentId.value = null;
      rememberConversationAnchor(convId);
    }
    try {
      const prefix = unref(options.apiPrefix) as string;
      const res = await getChatConversationMessagesApi(prefix, convId);
      if (
        reqSeq !== messagesRequestSeq ||
        activeConversationId.value !== convId
      ) {
        return;
      }
      applyConversationDetailState(convId, res);
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  return {
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
  };
}
