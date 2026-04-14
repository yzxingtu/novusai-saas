import type { PendingConfirmation, PendingConsent } from './types';
import type { PersistedToolResponseMap } from './use-ai-chat-message-merge-tool-responses';
import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import type { RawMessageItem } from '#/api/shared/ai-chat';

import { resolveToolCallStatus } from './use-ai-chat-message-merge-tool-responses';

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

export function collectToolCallsFromAssistantMessage(
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
