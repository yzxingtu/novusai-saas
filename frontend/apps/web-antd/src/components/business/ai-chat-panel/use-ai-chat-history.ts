import type { ConversationItem } from './types';

const EMPTY_CONVERSATION_VISIBLE_WINDOW_MS = 24 * 60 * 60 * 1000;

function parseTimestamp(value: null | string | undefined): number | null {
  if (!value) {
    return null;
  }
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

export function shouldDisplayConversationInHistory(
  conversation: ConversationItem,
  options: {
    activeConversationId?: null | number;
    nowMs?: number;
  } = {},
): boolean {
  const messageCount = Number(conversation.message_count ?? 0);
  if (messageCount > 0) {
    return true;
  }

  if (
    typeof options.activeConversationId === 'number' &&
    conversation.id === options.activeConversationId
  ) {
    return true;
  }

  const status = String(conversation.status ?? '').toLowerCase();
  if (status === 'active') {
    return true;
  }

  const referenceTime =
    parseTimestamp(conversation.updated_at) ??
    parseTimestamp(conversation.created_at);
  if (referenceTime === null) {
    return false;
  }

  const nowMs = options.nowMs ?? Date.now();
  return nowMs - referenceTime <= EMPTY_CONVERSATION_VISIBLE_WINDOW_MS;
}
