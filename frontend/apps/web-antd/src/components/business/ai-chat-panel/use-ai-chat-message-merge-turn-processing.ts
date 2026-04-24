import type {
  ActionButton,
  AgentItem,
  PendingConfirmation,
  PendingConsent,
} from './types';
import type { PersistedToolResponseMap } from './use-ai-chat-message-merge-tool-responses';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import type { RawMessageItem } from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

import { $t } from '#/locales';

import { collectToolCallsFromAssistantMessage } from './use-ai-chat-message-merge-tool-call-collector';
import { collectTurnContentMetadata } from './use-ai-chat-message-merge-turn-content';
import { collectTurnDiagnostics } from './use-ai-chat-message-merge-turn-diagnostics';
import {
  normalizeObjectRecord,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';
import {
  mergeTurnFlow,
  normalizeTurnFlowViewModel,
} from './chat-message-turn-flow-ingestion';

function resolvePersistedAssistantError(
  metadata: null | Record<string, unknown>,
  fallbackContent: string,
): null | { appError: AppErrorInfo; errorOnly: boolean } {
  if (!metadata || metadata.error !== true) {
    return null;
  }

  const messageText =
    normalizeOptionalString(metadata.error_message) ||
    normalizeOptionalString(fallbackContent) ||
    $t('common.http.internalServerError');
  const debugMessage =
    normalizeOptionalString(metadata.error_debug_message) ||
    normalizeOptionalString(metadata.raw_error_message);
  const traceId = normalizeOptionalString(metadata.error_trace_id);
  const errorType = normalizeOptionalString(metadata.error_type);

  return {
    appError: {
      code: errorType,
      debugMessage,
      message: messageText,
      raw: metadata,
      source: 'sse',
      traceId,
    },
    errorOnly: metadata.error_only !== false,
  };
}

function resolvePendingConfirmationFromMetadata(
  pendingValue: Record<string, unknown>,
): PendingConfirmation {
  const action = normalizeOptionalString(pendingValue.action);
  const table = normalizeOptionalString(pendingValue.table);
  const toolName = normalizeOptionalString(
    pendingValue.tool_name || pendingValue.toolName,
  );
  return {
    ...(action ? { action } : {}),
    preview: pendingValue.preview as Record<string, unknown> | undefined,
    resolved: pendingValue.resolved as boolean | undefined,
    ...(table ? { table } : {}),
    ...(toolName ? { toolName } : {}),
  };
}

function resolvePendingConsentFromMetadata(
  pendingValue: Record<string, unknown>,
  fallbackToolName = '',
): PendingConsent {
  return {
    arguments: pendingValue.arguments as Record<string, unknown> | undefined,
    autoApproved:
      (pendingValue.auto_approved as boolean | undefined) ??
      (pendingValue.autoApproved as boolean | undefined),
    rejected: pendingValue.rejected as boolean | undefined,
    resolved: pendingValue.resolved as boolean | undefined,
    skillName: (pendingValue.skill_name as string) || undefined,
    skillType: (pendingValue.package_name as string) || undefined,
    toolName: String(
      pendingValue.tool_name || pendingValue.toolName || fallbackToolName,
    ),
  };
}

function assignAgentStateFromMessage(
  state: AssistantTurnMergeState,
  messageItem: RawMessageItem,
  assistantMetadata: null | Record<string, unknown>,
  agents: AgentItem[],
) {
  if (messageItem.created_at) {
    state.turnCreatedAt = messageItem.created_at;
  }
  if (state.turnAgentId === null && messageItem.agent_id) {
    state.turnAgentId = messageItem.agent_id;
    state.turnAgentName = messageItem.agent_name ?? null;
    state.turnAgentAvatar = messageItem.agent_avatar ?? null;
    const agentInfo = agents.find((agent) => agent.id === messageItem.agent_id);
    if (agentInfo) {
      state.turnAgentDescription = agentInfo.description ?? null;
      if (!state.turnModelName) {
        state.turnModelName = agentInfo.model_name ?? null;
      }
      if (!state.turnAgentAvatar && agentInfo.avatar) {
        state.turnAgentAvatar = agentInfo.avatar;
      }
    }
  }
  if (state.turnModelName === null) {
    state.turnModelName =
      messageItem.model_name ??
      (typeof assistantMetadata?.model_name === 'string'
        ? assistantMetadata.model_name
        : null);
  }
}

function collectPendingStateFromMetadata(
  state: AssistantTurnMergeState,
  assistantMetadata: null | Record<string, unknown>,
) {
  if (
    !state.turnPendingConfirmation &&
    assistantMetadata?.pending_confirmation &&
    typeof assistantMetadata.pending_confirmation === 'object'
  ) {
    state.turnPendingConfirmation = resolvePendingConfirmationFromMetadata(
      assistantMetadata.pending_confirmation as Record<string, unknown>,
    );
  }
  if (
    !state.turnPendingConsent &&
    assistantMetadata?.pending_consent &&
    typeof assistantMetadata.pending_consent === 'object'
  ) {
    state.turnPendingConsent = resolvePendingConsentFromMetadata(
      assistantMetadata.pending_consent as Record<string, unknown>,
    );
  }
}

export function processAssistantMessage({
  agents,
  messageItem,
  state,
  toolResponseMap,
}: {
  agents: AgentItem[];
  messageItem: RawMessageItem;
  state: AssistantTurnMergeState;
  toolResponseMap: PersistedToolResponseMap;
}) {
  const assistantMetadata = normalizeObjectRecord(messageItem.metadata);
  const persistedErrorState = resolvePersistedAssistantError(
    assistantMetadata,
    messageItem.content ?? '',
  );
  if (persistedErrorState) {
    state.turnPersistedError = persistedErrorState.appError;
    state.turnPersistedErrorOnly =
      state.turnPersistedErrorOnly || persistedErrorState.errorOnly;
  }

  assignAgentStateFromMessage(state, messageItem, assistantMetadata, agents);
  if (
    state.turnRouteSource === null &&
    typeof assistantMetadata?.route_source === 'string'
  ) {
    state.turnRouteSource = assistantMetadata.route_source;
  }
  if (Array.isArray(assistantMetadata?.action_buttons)) {
    state.turnActionButtons =
      assistantMetadata.action_buttons as ActionButton[];
  }
  if (assistantMetadata?.action_buttons_used === true) {
    state.turnActionButtonsUsed = true;
  }

  collectPendingStateFromMetadata(state, assistantMetadata);
  const persistedTurnFlow = normalizeTurnFlowViewModel(
    messageItem.turn_flow ?? assistantMetadata?.turn_flow,
  );
  if (persistedTurnFlow) {
    state.hasCanonicalTurnFlow = true;
    state.turnFlow = mergeTurnFlow(state.turnFlow, persistedTurnFlow);
    if (persistedTurnFlow.completionReason) {
      state.turnCompletionReason = persistedTurnFlow.completionReason;
    }
    if (persistedTurnFlow.interrupted) {
      state.hasInterrupted = true;
      state.hasPartial = true;
      state.turnTerminationReason =
        state.turnTerminationReason || 'interrupted';
    }
    if (persistedTurnFlow.finalStageStatus === 'error') {
      state.turnOutcome = 'failed';
      state.turnTerminationReason =
        state.turnTerminationReason || state.turnCompletionReason || 'error';
    } else if (persistedTurnFlow.finalStageStatus === 'interrupted') {
      state.hasInterrupted = true;
      state.hasPartial = true;
      state.turnOutcome = state.turnOutcome || 'partial';
      state.turnTerminationReason =
        state.turnTerminationReason || 'interrupted';
    }
  }
  collectToolCallsFromAssistantMessage(state, messageItem, toolResponseMap);

  if (assistantMetadata?.memory_updated) {
    state.hasMemoryUpdated = true;
  }
  collectTurnDiagnostics(state, assistantMetadata);
  collectTurnContentMetadata({
    assistantMetadata,
    messageItem,
    persistedErrorOnly: persistedErrorState?.errorOnly === true,
    state,
  });
}
