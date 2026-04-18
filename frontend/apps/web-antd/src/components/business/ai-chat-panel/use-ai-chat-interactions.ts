import type { Ref } from 'vue';

import type { ChatMessage } from './types';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming';

import type { PageContext } from '#/api/shared/ai-chat';

import { ref } from 'vue';

interface UseAIChatInteractionsDeps {
  chatMessages: Ref<ChatMessage[]>;
  inputMessage: Ref<string>;
  pendingInteractionUpdates?: Ref<PendingInteractionUpdate[]>;
  sendMessage: (options?: {
    agentId?: number;
    pageContext?: null | PageContext;
    routeSource?: null | string;
    silent?: boolean;
  }) => boolean | Promise<boolean> | Promise<undefined> | undefined;
}

export function useAIChatInteractions(deps: UseAIChatInteractionsDeps) {
  const { chatMessages, inputMessage, sendMessage } = deps;

  const pendingInteractionUpdates =
    deps.pendingInteractionUpdates ?? ref<PendingInteractionUpdate[]>([]);

  function confirmAction(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConfirmation || msg.pendingConfirmation.resolved) return;
    msg.pendingConfirmation.resolved = true;
    pendingInteractionUpdates.value.push({
      action: msg.pendingConfirmation.action,
      kind: 'pending_confirmation',
      rejected: false,
      table: msg.pendingConfirmation.table,
      tool_name: msg.pendingConfirmation.toolName,
    });
    sendMessage({ silent: true });
  }

  function rejectAction(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConfirmation || msg.pendingConfirmation.resolved) return;
    msg.pendingConfirmation.resolved = true;
    pendingInteractionUpdates.value.push({
      action: msg.pendingConfirmation.action,
      kind: 'pending_confirmation',
      rejected: true,
      table: msg.pendingConfirmation.table,
      tool_name: msg.pendingConfirmation.toolName,
    });
    sendMessage({ silent: true });
  }

  function confirmConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    pendingInteractionUpdates.value.push({
      kind: 'pending_consent',
      rejected: false,
      tool_name: msg.pendingConsent.toolName,
    });
    sendMessage({ silent: true });
  }

  function rejectConsent(msgIndex: number) {
    const msg = chatMessages.value[msgIndex];
    if (!msg?.pendingConsent || msg.pendingConsent.resolved) return;
    msg.pendingConsent.resolved = true;
    msg.pendingConsent.rejected = true;
    pendingInteractionUpdates.value.push({
      kind: 'pending_consent',
      rejected: true,
      tool_name: msg.pendingConsent.toolName,
    });
    sendMessage({ silent: true });
  }

  function clickActionButton(msgIndex: number, value: string) {
    const msg = chatMessages.value[msgIndex];
    if (!msg || msg.actionButtonsUsed) return;
    msg.actionButtonsUsed = true;
    pendingInteractionUpdates.value.push({
      kind: 'action_buttons',
      value,
    });
    inputMessage.value = value;
    sendMessage();
  }

  return {
    clickActionButton,
    confirmAction,
    confirmConsent,
    pendingInteractionUpdates,
    rejectAction,
    rejectConsent,
  };
}
