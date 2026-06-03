import type { ChatMessage } from './types';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import { toTurnFlowFirstChatMessage } from './turn-flow-first-message';
import { isTurnFailure } from './use-ai-chat-message-context';

export function buildAssistantMessageFromState(
  state: AssistantTurnMergeState,
): ChatMessage {
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
  };
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

  return toTurnFlowFirstChatMessage(assistantMessage);
}
