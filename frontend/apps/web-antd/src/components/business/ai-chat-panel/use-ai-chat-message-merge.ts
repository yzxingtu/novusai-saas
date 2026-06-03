import type { AgentItem, ChatMessage } from './types';

import type { RawMessageItem } from '#/api/shared/ai-chat';

import {
  createUserMessageForDisplay,
  mergeAssistantTurnForDisplay,
} from './use-ai-chat-message-merge-turn';

/**
 * Merge raw DB messages into display ChatMessages / 将原始 DB 消息合并为展示用 ChatMessages
 *
 * During streaming, all tool call rounds are accumulated into a single
 * assistant ChatMessage. Persisted history may still contain several assistant
 * and tool rows for one turn, but the display model merges them back into one
 * canonical assistant view.
 *
 * This function groups consecutive non-user messages between user messages
 * into a single ChatMessage with canonical turnFlow reconstructed.
 */
export function mergeMessagesForDisplay(
  rawMessages: RawMessageItem[],
  agents: AgentItem[] = [],
): ChatMessage[] {
  // Filter out system messages / 过滤 system 消息
  const filteredMessages = rawMessages.filter(
    (messageItem) => messageItem.role !== 'system',
  );
  if (filteredMessages.length === 0) {
    return [];
  }

  const result: ChatMessage[] = [];
  let index = 0;

  while (index < filteredMessages.length) {
    const current = filteredMessages[index];
    if (!current) {
      break;
    }
    if (current.role === 'user') {
      result.push(createUserMessageForDisplay(current, index));
      index += 1;
      continue;
    }

    const { assistantMessage, nextIndex } = mergeAssistantTurnForDisplay({
      agents,
      messages: filteredMessages,
      startIndex: index,
    });
    if (assistantMessage) {
      result.push(assistantMessage);
    }
    index = nextIndex;
  }

  return result;
}
