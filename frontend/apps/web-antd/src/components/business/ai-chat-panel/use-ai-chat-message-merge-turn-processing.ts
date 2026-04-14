import type {
  ActionButton,
  AgentItem,
  PendingConfirmation,
  PendingConsent,
  RagSource,
} from './types';
import type { PersistedToolResponseMap } from './use-ai-chat-message-merge-tool-responses';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import type { RawMessageItem } from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

import { $t } from '#/locales';

import {
  normalizeContextSources,
  normalizeTurnRecord,
} from './use-ai-chat-message-context';
import { resolveToolCallStatus } from './use-ai-chat-message-merge-tool-responses';
import {
  appendDistinctMergedTextPart,
  normalizeObjectRecord,
  normalizeOptionalString,
  normalizeStringList,
} from './use-ai-chat-message-normalizers';

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
  return {
    action: String(pendingValue.action || ''),
    preview: pendingValue.preview as Record<string, unknown> | undefined,
    resolved: pendingValue.resolved as boolean | undefined,
    table: String(pendingValue.table || ''),
    toolName: String(pendingValue.tool_name || pendingValue.toolName || ''),
  };
}

function resolvePendingConfirmationFromToolCall(
  pendingValue: Record<string, unknown>,
  fallbackToolName = '',
): PendingConfirmation {
  return {
    action: String(pendingValue.action || ''),
    preview: pendingValue.preview as Record<string, unknown> | undefined,
    table: String(pendingValue.table || ''),
    toolName: String(
      pendingValue.tool_name || pendingValue.toolName || fallbackToolName,
    ),
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

function resolvePendingConsentFromToolCall(
  pendingValue: Record<string, unknown>,
  parsedArgs: Record<string, unknown> | undefined,
  fallbackToolName = '',
): PendingConsent {
  return {
    arguments:
      (pendingValue.arguments as Record<string, unknown> | undefined) ??
      parsedArgs,
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

function collectToolCallsFromAssistantMessage(
  state: AssistantTurnMergeState,
  messageItem: RawMessageItem,
  toolResponseMap: PersistedToolResponseMap,
) {
  if (!messageItem.tool_calls?.length) {
    return;
  }
  for (const toolCall of messageItem.tool_calls) {
    const toolCallId = toolCall.id ?? '';
    const functionName = toolCall.function?.name ?? 'unknown';
    const persistedToolCall = toolCall as Record<string, unknown>;
    let parsedArgs: Record<string, unknown> | undefined;
    try {
      parsedArgs = toolCall.function?.arguments
        ? JSON.parse(toolCall.function.arguments)
        : undefined;
    } catch {
      parsedArgs = toolCall.function?.arguments
        ? { raw: toolCall.function.arguments }
        : undefined;
    }

    const response = toolCallId ? toolResponseMap.get(toolCallId) : undefined;

    if (
      !state.turnPendingConfirmation &&
      persistedToolCall.pending_confirmation &&
      typeof persistedToolCall.pending_confirmation === 'object'
    ) {
      state.turnPendingConfirmation = resolvePendingConfirmationFromToolCall(
        persistedToolCall.pending_confirmation as Record<string, unknown>,
        functionName,
      );
    }
    if (
      !state.turnPendingConsent &&
      persistedToolCall.pending_consent &&
      typeof persistedToolCall.pending_consent === 'object'
    ) {
      state.turnPendingConsent = resolvePendingConsentFromToolCall(
        persistedToolCall.pending_consent as Record<string, unknown>,
        parsedArgs,
        functionName,
      );
    }

    state.toolCalls.push({
      arguments: parsedArgs,
      displayName:
        (persistedToolCall.display_name as string) ?? response?.displayName,
      durationMs: persistedToolCall.duration_ms as number | undefined,
      error:
        response && !response.success
          ? response.error || response.content
          : (persistedToolCall.error as string | undefined) || response?.error,
      errorType:
        (persistedToolCall.error_type as string) ?? response?.errorType,
      id: toolCallId || undefined,
      name: functionName,
      output: response?.success
        ? response.content
        : (persistedToolCall.output as string | undefined),
      resultLink:
        (persistedToolCall.result_link as string) ?? response?.resultLink,
      skillName:
        (persistedToolCall.skill_name as string) ??
        (persistedToolCall.package_name as string) ??
        undefined,
      status: resolveToolCallStatus(response, persistedToolCall),
      summary: (persistedToolCall.summary as string) ?? response?.summary,
      summaryPayload:
        (persistedToolCall.summary_payload as Record<string, unknown>) ??
        response?.summaryPayload,
    });
  }
}

function collectTurnDiagnostics(
  state: AssistantTurnMergeState,
  assistantMetadata: null | Record<string, unknown>,
) {
  state.turnContextDiagnosticsRaw =
    normalizeObjectRecord(assistantMetadata?.context_diagnostics) ??
    state.turnContextDiagnosticsRaw;
  state.turnLastRunSummaryRaw =
    normalizeObjectRecord(assistantMetadata?.last_run_summary) ??
    state.turnLastRunSummaryRaw;
  state.turnRecordRaw =
    normalizeObjectRecord(assistantMetadata?.turn_record) ??
    state.turnRecordRaw;

  const turnRecord = normalizeTurnRecord(assistantMetadata?.turn_record);
  if (turnRecord) {
    state.turnRecordPayload = turnRecord;
  }

  const metadataTurnOutcome = normalizeOptionalString(
    assistantMetadata?.turn_outcome,
  );
  if (!state.turnOutcome && metadataTurnOutcome) {
    state.turnOutcome = metadataTurnOutcome;
  }
  if (!state.turnOutcome && turnRecord?.turn_outcome) {
    state.turnOutcome = turnRecord.turn_outcome;
  }

  const metadataTerminationReason = normalizeOptionalString(
    assistantMetadata?.termination_reason,
  );
  if (!state.turnTerminationReason && metadataTerminationReason) {
    state.turnTerminationReason = metadataTerminationReason;
  }
  if (!state.turnTerminationReason && turnRecord?.termination_reason) {
    state.turnTerminationReason = turnRecord.termination_reason;
  }

  const metadataProtocolPath = normalizeOptionalString(
    assistantMetadata?.protocol_path,
  );
  if (!state.turnProtocolPath && metadataProtocolPath) {
    state.turnProtocolPath = metadataProtocolPath;
  }
  if (!state.turnProtocolPath && turnRecord?.protocol_path) {
    state.turnProtocolPath = turnRecord.protocol_path;
  }

  const metadataSelectedToolNames = normalizeStringList(
    assistantMetadata?.selected_tool_names,
  );
  if (metadataSelectedToolNames.length > 0) {
    state.turnSelectedToolNames = metadataSelectedToolNames;
  } else if (
    state.turnSelectedToolNames.length === 0 &&
    (turnRecord?.selected_tool_names?.length ?? 0) > 0
  ) {
    state.turnSelectedToolNames = [...(turnRecord?.selected_tool_names ?? [])];
  }

  const metadataSelectedSkillNames = normalizeStringList(
    assistantMetadata?.selected_skill_names,
  );
  if (metadataSelectedSkillNames.length > 0) {
    state.turnSelectedSkillNames = metadataSelectedSkillNames;
  } else if (
    state.turnSelectedSkillNames.length === 0 &&
    (turnRecord?.selected_skill_names?.length ?? 0) > 0
  ) {
    state.turnSelectedSkillNames = [
      ...(turnRecord?.selected_skill_names ?? []),
    ];
  }

  const metadataContextSources = normalizeContextSources(
    assistantMetadata?.context_sources,
  );
  if (metadataContextSources.length > 0) {
    state.turnContextSources = metadataContextSources;
  } else if (
    state.turnContextSources.length === 0 &&
    (turnRecord?.context_sources?.length ?? 0) > 0
  ) {
    state.turnContextSources = [...(turnRecord?.context_sources ?? [])];
  }
}

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
  collectToolCallsFromAssistantMessage(state, messageItem, toolResponseMap);

  if (assistantMetadata?.memory_updated) {
    state.hasMemoryUpdated = true;
  }
  collectTurnDiagnostics(state, assistantMetadata);
  collectTurnFlags(
    state,
    assistantMetadata,
    persistedErrorState?.errorOnly === true,
  );

  const skipRemaining =
    collectTurnText(
      state,
      messageItem,
      assistantMetadata,
      persistedErrorState?.errorOnly === true,
    ) === true;
  if (skipRemaining) {
    return;
  }

  const ragSources = assistantMetadata?.rag_sources;
  if (Array.isArray(ragSources) && ragSources.length > 0) {
    state.turnRagSources = ragSources as RagSource[];
  }
}
