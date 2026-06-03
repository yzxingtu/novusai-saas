import type { Ref } from 'vue';

import type {
  AgentItem,
  ChatAttachment,
  ChatMessage,
  InteractionMode,
} from './types';

import { unref } from 'vue';

import { message } from 'ant-design-vue';

import { getChatAgentsApi } from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { clearConsents } from '#/utils/ai-consent';
import { toAvatarDisplayUrl } from '#/utils/image';

interface SendMessageOptions {
  silent?: boolean;
}

interface AIChatCoreActionOptions {
  apiPrefix: Ref<string> | string;
  initialAgentId?: number | Ref<number | undefined>;
}

interface CreateAIChatCoreActionsOptions {
  abortActiveStream: (markStoppedByUser?: boolean) => void;
  activeConversationAgentId: Ref<null | number>;
  activeConversationId: Ref<null | number>;
  agents: Ref<AgentItem[]>;
  agentsLoading: Ref<boolean>;
  bumpConversationsRequestSeq: () => void;
  bumpMessagesRequestSeq: () => void;
  chatMessages: Ref<ChatMessage[]>;
  clearConversationAnchor: () => void;
  clearMentionDraft: () => void;
  clearPendingAttachments: () => void;
  inputMessage: Ref<string>;
  interactionMode: Ref<InteractionMode>;
  interactionModeEffective: Ref<InteractionMode>;
  options: AIChatCoreActionOptions;
  pendingAttachments: Ref<ChatAttachment[]>;
  resetConversationState: () => void;
  resetMemoryState: () => void;
  resetPendingMessages: () => void;
  resetVariables: () => void;
  selectedAgentId: Ref<null | number>;
  sendMessage: (options?: SendMessageOptions) => Promise<boolean>;
  sending: Ref<boolean>;
  streaming: Ref<boolean>;
}

export function createAIChatCoreActions(
  options: CreateAIChatCoreActionsOptions,
) {
  const {
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
    options: chatOptions,
    pendingAttachments,
    resetConversationState,
    resetMemoryState,
    resetPendingMessages,
    resetVariables,
    selectedAgentId,
    sendMessage,
    sending,
    streaming,
  } = options;

  async function loadAgents(overrideAgentId?: number) {
    agentsLoading.value = true;
    try {
      const response = await getChatAgentsApi<AgentItem>(
        unref(chatOptions.apiPrefix),
      );
      agents.value = response.items.map((agent) => {
        const avatar = toAvatarDisplayUrl(agent.avatar ?? undefined);
        return {
          ...agent,
          avatar: avatar || null,
        };
      });
      const firstAgent = response.items[0];
      if (firstAgent && !selectedAgentId.value) {
        const initialId = overrideAgentId ?? unref(chatOptions.initialAgentId);
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
    activeConversationAgentId.value =
      typeof selectedAgentId.value === 'number' ? selectedAgentId.value : null;
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

    const shouldKeepConversationBinding =
      msgIndex === chatMessages.value.length - 1;

    chatMessages.value.splice(msgIndex);
    bumpMessagesRequestSeq();
    if (!shouldKeepConversationBinding) {
      clearConversationAnchor();
      activeConversationId.value = null;
      activeConversationAgentId.value =
        typeof selectedAgentId.value === 'number'
          ? selectedAgentId.value
          : null;
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
    if (!lastMessage || lastMessage.role !== 'assistant') return;
    if (!lastMessage.requestFailedRetry) return;

    const previousMessage = messages.at(-2);
    if (!previousMessage || previousMessage.role !== 'user') {
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
    cleanup,
    copyMessage,
    editAndResend,
    loadAgents,
    regenerateMessage,
    retryLastMessage,
    selectAgent,
    startNewConversation,
    stopGeneration,
  };
}
