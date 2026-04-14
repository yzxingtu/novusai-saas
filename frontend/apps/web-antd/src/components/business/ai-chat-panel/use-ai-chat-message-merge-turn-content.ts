import type { RagSource } from './types';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import type { RawMessageItem } from '#/api/shared/ai-chat';

import { appendDistinctMergedTextPart } from './use-ai-chat-message-normalizers';

function collectTurnFlags(
  state: AssistantTurnMergeState,
  assistantMetadata: null | Record<string, unknown>,
  persistedErrorOnly: boolean,
) {
  if (
    !persistedErrorOnly &&
    (assistantMetadata?.partial || state.turnOutcome === 'partial')
  ) {
    state.hasPartial = true;
  }
  if (
    !persistedErrorOnly &&
    (assistantMetadata?.interrupted ||
      state.turnTerminationReason === 'interrupted')
  ) {
    state.hasInterrupted = true;
  }
  if (state.hasInterrupted) {
    state.hasPartial = true;
  }
  if (assistantMetadata?.completion_reason) {
    state.turnCompletionReason = assistantMetadata.completion_reason as string;
  }
  if (!state.turnCompletionReason && state.turnTerminationReason) {
    state.turnCompletionReason = state.turnTerminationReason;
  }
}

function collectTurnText(
  state: AssistantTurnMergeState,
  messageItem: RawMessageItem,
  assistantMetadata: null | Record<string, unknown>,
  persistedErrorOnly: boolean,
): boolean {
  const persistedThinking =
    typeof assistantMetadata?.thinking_content === 'string'
      ? assistantMetadata.thinking_content
      : '';
  if (persistedThinking.trim()) {
    appendDistinctMergedTextPart(state.thinkingContentParts, persistedThinking);
  }

  if (!(messageItem.content && messageItem.content.trim())) {
    return false;
  }
  if (persistedErrorOnly) {
    return true;
  }
  if (messageItem.tool_calls?.length) {
    if (!persistedThinking.trim()) {
      appendDistinctMergedTextPart(
        state.thinkingContentParts,
        messageItem.content,
      );
    }
  } else {
    appendDistinctMergedTextPart(state.contentParts, messageItem.content);
  }
  return false;
}

function collectTurnRagSources(
  state: AssistantTurnMergeState,
  assistantMetadata: null | Record<string, unknown>,
) {
  const ragSources = assistantMetadata?.rag_sources;
  if (Array.isArray(ragSources) && ragSources.length > 0) {
    state.turnRagSources = ragSources as RagSource[];
  }
}

export function collectTurnContentMetadata({
  assistantMetadata,
  messageItem,
  persistedErrorOnly,
  state,
}: {
  assistantMetadata: null | Record<string, unknown>;
  messageItem: RawMessageItem;
  persistedErrorOnly: boolean;
  state: AssistantTurnMergeState;
}): boolean {
  collectTurnFlags(state, assistantMetadata, persistedErrorOnly);

  const skipRemaining = collectTurnText(
    state,
    messageItem,
    assistantMetadata,
    persistedErrorOnly,
  );
  if (skipRemaining) {
    return true;
  }

  collectTurnRagSources(state, assistantMetadata);
  return false;
}
