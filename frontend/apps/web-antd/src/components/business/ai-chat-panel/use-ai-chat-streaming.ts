import type { Ref } from 'vue';

import type {
  AgentItem,
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  InteractionMode,
} from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';
import type {
  StreamControl,
  StreamRequestDeps,
} from './use-ai-chat-streaming-request';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

import type {
  ChatKBBindingInfo,
  MemoryState,
} from '#/api/shared/ai-chat';
import type { AIInteractionUpdate } from '#/store/shared/ai-panel';

import { nextTick, ref } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';

import { resolveConversationRequestState } from './conversation-binding';
import { formatLocalizedList } from './display-formatters';
import { getAgentInputVariables } from './types';
import { runStreamRequest } from './use-ai-chat-streaming-request';
import { createAIChatStreamingScroll } from './use-ai-chat-streaming-scroll';

export type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

interface UseAIChatStreamingDeps {
  activeConversationAgentId: Ref<null | number>;
  activeConversationId: Ref<null | number>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  agents: Ref<AgentItem[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  apiPrefix: Ref<string> | string;
  chatMessages: Ref<ChatMessage[]>;
  clearConversationAnchor: () => void;
  clearPendingAttachments: () => void;
  conversationAnchorAgentId: Ref<null | number>;
  conversationAnchorId: Ref<null | number>;
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  conversations: Ref<ConversationItem[]>;
  ensureAgentVarsLoaded: (agentId: number) => void;
  inputMessage: Ref<string>;
  interactionMode: Ref<InteractionMode>;
  interactionModeEffective: Ref<InteractionMode>;
  lastMemoryUpdated: Ref<boolean>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  loadConversations: () => Promise<void>;
  memoryState: Ref<MemoryState | null>;
  imageParams: Ref<{
    n: number;
    quality: string;
    size: string;
    style: string;
  }>;
  options: UseAIChatOptions;
  pendingAttachments: Ref<ChatAttachment[]>;
  pendingInteractionUpdates: Ref<PendingInteractionUpdate[]>;
  recoverConversationIdFromHistory: (
    knownConversationIds: Set<number>,
    agentId: number,
  ) => null | number;
  rememberConversationAnchor: (conversationId: number, agentId: number) => void;
  selectedAgentId: Ref<null | number>;
  selectedKBIds: Ref<number[]>;
  selectedSkillNames: Ref<string[]>;
  syncConversationAfterInterrupt: (
    conversationId: number,
    interruptedHistoryBaseline: number,
  ) => Promise<void>;
  uiPanelStore: {
    consumeInteractionUpdates: () => AIInteractionUpdate[];
    restoreInteractionUpdates: (updates: AIInteractionUpdate[]) => void;
  };
  bumpMessagesRequestSeq: () => void;
  nextClientKey: (prefix: string) => string;
}

export function useAIChatStreaming(deps: UseAIChatStreamingDeps) {
  const {
    activeConversationAgentId,
    activeConversationId,
    agentKBBindings,
    agents,
    allAgentsVariables,
    chatMessages,
    clearConversationAnchor,
    clearPendingAttachments,
    conversationAnchorAgentId,
    conversationAnchorId,
    conversationContextDiagnostics,
    conversations,
    ensureAgentVarsLoaded,
    inputMessage,
    interactionMode,
    interactionModeEffective,
    lastMemoryUpdated,
    lastRunSummary,
    loadConversations,
    memoryState,
    options,
    pendingAttachments,
    pendingInteractionUpdates,
    recoverConversationIdFromHistory,
    rememberConversationAnchor,
    selectedAgentId,
    selectedKBIds,
    selectedSkillNames,
    syncConversationAfterInterrupt,
    uiPanelStore,
    imageParams,
    bumpMessagesRequestSeq,
    nextClientKey,
  } = deps;

  const sending = ref(false);
  const streaming = ref(false);

  /** 发送前 800ms 防抖：多条消息合并为一次请求 */
  const SEND_DEBOUNCE_MS = 800;
  const pendingMessages = ref<{ text: string }[]>([]);
  let debounceTimerId: null | ReturnType<typeof setTimeout> = null;

  const streamControl: StreamControl = {
    abortController: null,
    lifecycle: null,
  };

  /** Deferred auto-confirm flag: set when trusted_auto auto-approves during active stream */
  const deferredAutoConfirm = ref(false);

  const {
    handleMessagesScroll,
    messagesContainer,
    scrollToBottom,
    scrollToTop,
    userNotAtTop,
    userScrolledUp,
  } = createAIChatStreamingScroll();

  /**
   * Abort active SSE stream; call before switching agent/conversation or closing panel.
   */
  function abortActiveStream(markStoppedByUser = false): void {
    if (streamControl.abortController) {
      if (streamControl.lifecycle) {
        streamControl.lifecycle.abortReason = markStoppedByUser
          ? 'user'
          : 'context_switch';
      }
      streamControl.abortController.abort();
      streamControl.abortController = null;
    }
    sending.value = false;
    streaming.value = false;
    userScrolledUp.value = false;
    const last = chatMessages.value.at(-1);
    if (last?.streaming) {
      last.streaming = false;
      if (last.role === 'assistant' && markStoppedByUser) {
        last.stoppedByUser = true;
      }
    }
  }

  function resetPendingMessages() {
    if (debounceTimerId) {
      clearTimeout(debounceTimerId);
      debounceTimerId = null;
    }
    pendingMessages.value = [];
  }

  function buildStreamRequestDeps(): StreamRequestDeps {
    return {
      activeConversationAgentId,
      activeConversationId,
      agentKBBindings,
      allAgentsVariables,
      chatMessages,
      conversationAnchorId,
      conversationContextDiagnostics,
      conversations,
      deferredAutoConfirm,
      interactionMode,
      interactionModeEffective,
      lastMemoryUpdated,
      lastRunSummary,
      loadConversations,
      options,
      pendingInteractionUpdates,
      recoverConversationIdFromHistory,
      rememberConversationAnchor,
      selectedKBIds,
      selectedSkillNames,
      sendMessage,
      streamControl,
      streaming,
      sending,
      syncConversationAfterInterrupt,
      uiPanelStore,
      userScrolledUp,
      scrollToBottom,
      imageParams,
    };
  }

  async function sendMessage(opts?: {
    agentId?: number;
    silent?: boolean;
  }): Promise<boolean> {
    const silent = opts?.silent ?? false;
    const explicitAgentSelection =
      opts?.agentId !== null && opts?.agentId !== undefined;
    const anchoredConversationId =
      !explicitAgentSelection &&
      activeConversationId.value === null &&
      chatMessages.value.length > 0
        ? conversationAnchorId.value
        : null;
    const effectiveConversationId =
      activeConversationId.value ?? anchoredConversationId;
    const effectiveConversationAgentId =
      effectiveConversationId === null
        ? null
        : (activeConversationAgentId.value ?? conversationAnchorAgentId.value);
    const maybeTargetAgentId =
      opts?.agentId ?? effectiveConversationAgentId ?? selectedAgentId.value;
    const hasText = inputMessage.value.trim().length > 0;
    const hasAttachments = pendingAttachments.value.length > 0;
    const hasInteractionUpdates = pendingInteractionUpdates.value.length > 0;
    if (
      (!hasText && !hasAttachments && !hasInteractionUpdates) ||
      maybeTargetAgentId === null ||
      maybeTargetAgentId === undefined ||
      sending.value
    ) {
      return false;
    }
    const targetAgentId = maybeTargetAgentId;

    if (
      !explicitAgentSelection &&
      effectiveConversationId !== null &&
      activeConversationId.value === null
    ) {
      activeConversationId.value = effectiveConversationId;
    }
    if (
      !explicitAgentSelection &&
      effectiveConversationAgentId !== null &&
      activeConversationAgentId.value === null
    ) {
      activeConversationAgentId.value = effectiveConversationAgentId;
    }
    if (
      !explicitAgentSelection &&
      effectiveConversationAgentId !== null &&
      selectedAgentId.value !== effectiveConversationAgentId
    ) {
      selectedAgentId.value = effectiveConversationAgentId;
    }

    const agent = agents.value.find((a) => a.id === targetAgentId);
    const requiredVars = getAgentInputVariables(agent).filter(
      (v) => v.required,
    );
    if (requiredVars.length > 0) {
      ensureAgentVarsLoaded(targetAgentId);
      const agentVars = allAgentsVariables.value[targetAgentId] ?? {};
      const missingVars = requiredVars.filter(
        (v) => !agentVars[v.name]?.trim(),
      );
      if (missingVars.length > 0) {
        message.warning(
          $t('user.aiChat.varsModal.fillRequired', {
            fields: formatLocalizedList(
              missingVars.map((v) => v.label || v.name),
            ),
          }),
        );
        options.onVariablesMissing?.();
        return false;
      }
    }

    const conversationRequestState = resolveConversationRequestState({
      activeConversationAgentId:
        effectiveConversationAgentId ?? activeConversationAgentId.value,
      activeConversationId: effectiveConversationId,
      targetAgentId,
    });
    if (conversationRequestState.shouldForkConversation) {
      bumpMessagesRequestSeq();
      activeConversationId.value = null;
      activeConversationAgentId.value = null;
      clearConversationAnchor();
      memoryState.value = null;
      lastMemoryUpdated.value = false;
    } else if (conversationRequestState.conversationId !== null) {
      rememberConversationAnchor(
        conversationRequestState.conversationId,
        effectiveConversationAgentId ?? targetAgentId,
      );
    }

    const userMsg = inputMessage.value.trim();
    const msgAttachments = [...pendingAttachments.value];
    const displayAttachments =
      msgAttachments.length > 0
        ? msgAttachments.map(
            ({ attachment_id, type, url, name, mime_type }) => ({
              attachment_id,
              type,
              url,
              name,
              mime_type,
            }),
          )
        : undefined;

    const useDebounce =
      !silent &&
      !hasAttachments &&
      msgAttachments.length === 0 &&
      !hasInteractionUpdates &&
      selectedKBIds.value.length === 0 &&
      selectedSkillNames.value.length === 0 &&
      userMsg.length > 0;

    if (useDebounce) {
      if (!silent) {
        chatMessages.value.push({
          clientKey: nextClientKey('user'),
          role: 'user',
          content: userMsg,
          created_at: new Date().toISOString(),
        });
      }
      pendingMessages.value.push({ text: userMsg });
      inputMessage.value = '';
      clearPendingAttachments();
      userScrolledUp.value = false;
      scrollToBottom(true);

      if (debounceTimerId) clearTimeout(debounceTimerId);
      debounceTimerId = setTimeout(() => {
        debounceTimerId = null;
        flushPendingAndSend({
          targetAgentId,
        });
      }, SEND_DEBOUNCE_MS);
      return true;
    }

    if (!silent) {
      chatMessages.value.push({
        clientKey: nextClientKey('user'),
        role: 'user',
        content: userMsg,
        attachments: displayAttachments,
        created_at: new Date().toISOString(),
      });
    }
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
      clientKey: nextClientKey('assistant'),
      role: 'assistant',
      content: '',
      streaming: true,
      agent_id: targetAgentId,
      agent_name: targetAgent?.name ?? null,
      agent_avatar: targetAgent?.avatar ?? null,
      agent_description: targetAgent?.description ?? null,
      model_name: targetAgent?.model_name ?? null,
      created_at: new Date().toISOString(),
    });
    userScrolledUp.value = false;
    scrollToBottom(true);

    inputMessage.value = '';
    clearPendingAttachments();
    await nextTick();

    await runStreamRequest(buildStreamRequestDeps(), {
      texts: [userMsg],
      apiAttachments:
        msgAttachments.length > 0
          ? msgAttachments.map(
              ({ attachment_id, type, url, name, mime_type }) => ({
                attachment_id,
                type,
                url,
                name,
                mime_type,
              }),
            )
          : undefined,
      targetAgentId,
    });
    return true;
  }

  async function flushPendingAndSend(opts: {
    targetAgentId: number;
  }) {
    const msgs = [...pendingMessages.value];
    pendingMessages.value = [];
    if (msgs.length === 0) return;
    if (sending.value) return;

    const { targetAgentId } = opts;
    const targetAgent = agents.value.find((a) => a.id === targetAgentId);
    chatMessages.value.push({
      clientKey: nextClientKey('assistant'),
      role: 'assistant',
      content: '',
      streaming: true,
      agent_id: targetAgentId,
      agent_name: targetAgent?.name ?? null,
      agent_avatar: targetAgent?.avatar ?? null,
      agent_description: targetAgent?.description ?? null,
      model_name: targetAgent?.model_name ?? null,
      created_at: new Date().toISOString(),
    });
    userScrolledUp.value = false;
    scrollToBottom(true);
    await nextTick();

    await runStreamRequest(buildStreamRequestDeps(), {
      texts: msgs.map((m) => m.text),
      apiAttachments: undefined,
      targetAgentId,
    });
  }

  return {
    abortActiveStream,
    handleMessagesScroll,
    messagesContainer,
    resetPendingMessages,
    scrollToBottom,
    scrollToTop,
    sendMessage,
    sending,
    streaming,
    userNotAtTop,
    userScrolledUp,
  };
}
