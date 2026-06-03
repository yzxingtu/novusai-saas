import type { AgentItem, ChatMessage } from './types';

import type { RawMessageItem } from '#/api/shared/ai-chat';

import { normalizeChatAttachments } from '#/api/shared/ai-chat';

import { buildAssistantMessageFromState } from './use-ai-chat-message-merge-turn-finalize';
import { processAssistantMessage } from './use-ai-chat-message-merge-turn-processing';
import { createInitialAssistantTurnState } from './use-ai-chat-message-merge-turn-state';

export function createUserMessageForDisplay(
  messageItem: RawMessageItem,
  index: number,
): ChatMessage {
  return {
    ...(messageItem.created_at ? { created_at: messageItem.created_at } : {}),
    attachments: normalizeChatAttachments(messageItem.metadata?.attachments),
    clientKey: `persisted-user-${index}-${messageItem.created_at ?? ''}`,
    content: messageItem.content ?? '',
    role: 'user',
  };
}

export function mergeAssistantTurnForDisplay({
  agents,
  messages,
  startIndex,
}: {
  agents: AgentItem[];
  messages: RawMessageItem[];
  startIndex: number;
}): { assistantMessage?: ChatMessage; nextIndex: number } {
  const state = createInitialAssistantTurnState(startIndex);
  let index = startIndex;

  while (index < messages.length) {
    const current = messages[index];
    if (!current || current.role === 'user') {
      break;
    }
    if (current.role === 'assistant') {
      processAssistantMessage({
        agents,
        messageItem: current,
        state,
      });
    }
    index += 1;
  }

  if (index <= startIndex) {
    return { nextIndex: index };
  }

  return {
    assistantMessage: buildAssistantMessageFromState(state),
    nextIndex: index,
  };
}
