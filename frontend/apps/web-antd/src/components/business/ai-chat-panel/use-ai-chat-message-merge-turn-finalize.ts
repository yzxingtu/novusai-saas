import type { ChatMessage, ToolCallEvent } from './types';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import { isTurnFailure } from './use-ai-chat-message-context';
import {
  finalizeNativeSearchToolCall,
  markNativeSearchToolCallError,
  NATIVE_WEB_SEARCH_TOOL_NAME,
  resolveNativeSearchToolStatus,
  upsertNativeSearchToolCall,
} from './use-ai-chat-message-native-search';

function resolveMergedToolCalls(
  state: AssistantTurnMergeState,
): ToolCallEvent[] {
  const nativeSearchStatus = resolveNativeSearchToolStatus(
    state.turnContextDiagnosticsRaw,
    state.turnLastRunSummaryRaw,
    state.turnRecordRaw,
  );
  let mergedToolCalls = nativeSearchStatus
    ? upsertNativeSearchToolCall(state.toolCalls, nativeSearchStatus)
    : state.toolCalls;

  const hasPendingNativeSearchTool = mergedToolCalls.some(
    (toolCall) =>
      toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
      toolCall.status === 'running',
  );
  if (!hasPendingNativeSearchTool) {
    return mergedToolCalls;
  }

  const shouldFinalizeNativeSearchAsSuccess =
    state.turnSelectedToolNames.includes('web_search') ||
    (!state.hasPartial &&
      !state.hasInterrupted &&
      !isTurnFailure(
        state.turnOutcome,
        state.turnTerminationReason ?? state.turnCompletionReason,
      ));

  mergedToolCalls =
    (shouldFinalizeNativeSearchAsSuccess
      ? finalizeNativeSearchToolCall(mergedToolCalls)
      : markNativeSearchToolCallError(mergedToolCalls)) ?? [];
  return mergedToolCalls;
}

export function buildAssistantMessageFromState(
  state: AssistantTurnMergeState,
): ChatMessage {
  const mergedToolCalls = resolveMergedToolCalls(state);
  const mergedContent =
    state.trustedFinalContent ?? state.contentParts.join('\n\n');
  const assistantMessage: ChatMessage = {
    agent_avatar: state.turnAgentAvatar,
    agent_description: state.turnAgentDescription,
    agent_id: state.turnAgentId,
    agent_name: state.turnAgentName,
    clientKey: `persisted-assistant-${state.startIndex}-${
      state.turnCreatedAt ?? ''
    }`,
    content: state.turnPersistedErrorOnly ? '' : mergedContent,
    model_name: state.turnModelName,
    role: 'assistant',
    routeSource: state.turnRouteSource,
    toolCalls: mergedToolCalls.length > 0 ? mergedToolCalls : undefined,
  };
  if (state.turnRouteSource === 'rich_text_ai') {
    assistantMessage.source = 'rich_text_ai';
  }
  if (state.turnCreatedAt) {
    assistantMessage.created_at = state.turnCreatedAt;
  }
  if (state.hasMemoryUpdated) {
    assistantMessage.memoryUpdated = true;
  }
  if (state.hasPartial) {
    assistantMessage.partial = true;
  }
  if (state.hasInterrupted) {
    assistantMessage.interrupted = true;
  }
  if (state.turnOutcome) {
    assistantMessage.turnOutcome = state.turnOutcome;
  }
  if (state.turnTerminationReason) {
    assistantMessage.terminationReason = state.turnTerminationReason;
  }
  if (state.turnProtocolPath) {
    assistantMessage.protocolPath = state.turnProtocolPath;
  }
  if (state.turnSelectedToolNames.length > 0) {
    assistantMessage.selectedToolNames = state.turnSelectedToolNames;
  }
  if (state.turnSelectedSkillNames.length > 0) {
    assistantMessage.selectedSkillNames = state.turnSelectedSkillNames;
  }
  if (state.turnContextSources.length > 0) {
    assistantMessage.contextSources = state.turnContextSources;
  }
  if (state.turnRecordPayload) {
    assistantMessage.turnRecord = state.turnRecordPayload;
  }
  if (state.turnCompletionReason) {
    assistantMessage.completionReason = state.turnCompletionReason;
  }
  if (
    isTurnFailure(
      state.turnOutcome,
      state.turnTerminationReason ?? state.turnCompletionReason,
    )
  ) {
    assistantMessage.requestFailedRetry = true;
  }
  if (state.turnPersistedError) {
    assistantMessage.error = state.turnPersistedError;
    assistantMessage.requestFailedRetry = true;
  }
  if (state.thinkingContentParts.length > 0) {
    assistantMessage.thinkingContent = state.thinkingContentParts.join('\n\n');
  }
  if (state.turnRagSources?.length) {
    assistantMessage.ragSources = state.turnRagSources;
  }
  if (state.turnActionButtons?.length) {
    assistantMessage.actionButtons = state.turnActionButtons;
  }
  if (state.turnActionButtonsUsed === true) {
    assistantMessage.actionButtonsUsed = true;
  }
  if (state.turnPendingConfirmation) {
    assistantMessage.pendingConfirmation = state.turnPendingConfirmation;
  }
  if (state.turnPendingConsent) {
    assistantMessage.pendingConsent = state.turnPendingConsent;
  }
  if (state.turnPersistedErrorOnly) {
    delete assistantMessage.partial;
    delete assistantMessage.interrupted;
  }
  if (state.turnFlow) {
    assistantMessage.turnFlow = state.turnFlow;
  }
  return assistantMessage;
}
