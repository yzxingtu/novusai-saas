import type { ToolCallEvent } from './types';

import { $t } from '#/locales';

import {
  normalizeObjectRecord,
  normalizeObjectRecordList,
  normalizeOptionalString,
  normalizeStringList,
} from './use-ai-chat-message-normalizers';

export const NATIVE_WEB_SEARCH_PROVIDER = 'native_hosted';
export const NATIVE_WEB_SEARCH_TOOL_NAME = 'native_web_search';

export function buildNativeSearchSummaryPayload(
  status: ToolCallEvent['status'],
): Record<string, unknown> {
  return {
    provider: NATIVE_WEB_SEARCH_PROVIDER,
    ...(status === 'success' ? { status: 'success' } : {}),
  };
}

export function hasConcreteWebSearchToolCall(
  toolCalls?: ToolCallEvent[],
): boolean {
  return Boolean(toolCalls?.some((toolCall) => toolCall.name === 'web_search'));
}

export function removeNativeSearchToolCall(
  toolCalls?: ToolCallEvent[],
): ToolCallEvent[] | undefined {
  if (!toolCalls?.length) {
    return toolCalls;
  }
  const filtered = toolCalls.filter(
    (toolCall) => toolCall.name !== NATIVE_WEB_SEARCH_TOOL_NAME,
  );
  return filtered.length === toolCalls.length ? toolCalls : filtered;
}

export function upsertNativeSearchToolCall(
  toolCalls: ToolCallEvent[] | undefined,
  status: Extract<ToolCallEvent['status'], 'running' | 'success'>,
): ToolCallEvent[] {
  const nextToolCalls = [...(toolCalls ?? [])];
  if (hasConcreteWebSearchToolCall(nextToolCalls)) {
    return nextToolCalls;
  }

  const existing = nextToolCalls.findLast(
    (toolCall) => toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME,
  );
  if (existing) {
    existing.displayName =
      existing.displayName || $t('common.globalAiChat.toolNativeSearch');
    existing.status = status;
    if (status === 'running' && !existing.startedAt) {
      existing.startedAt = Date.now();
    }
    existing.summaryPayload = {
      ...existing.summaryPayload,
      ...buildNativeSearchSummaryPayload(status),
    };
    return nextToolCalls;
  }

  nextToolCalls.push({
    displayName: $t('common.globalAiChat.toolNativeSearch'),
    name: NATIVE_WEB_SEARCH_TOOL_NAME,
    startedAt: status === 'running' ? Date.now() : undefined,
    status,
    summaryPayload: buildNativeSearchSummaryPayload(status),
  });
  return nextToolCalls;
}

export function finalizeNativeSearchToolCall(
  toolCalls: ToolCallEvent[] | undefined,
): ToolCallEvent[] | undefined {
  if (!toolCalls?.length || hasConcreteWebSearchToolCall(toolCalls)) {
    return toolCalls;
  }
  const runningNativeTool = toolCalls.findLast(
    (toolCall) =>
      toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
      toolCall.status === 'running',
  );
  if (!runningNativeTool) {
    return toolCalls;
  }
  return upsertNativeSearchToolCall(toolCalls, 'success');
}

export function markNativeSearchToolCallError(
  toolCalls: ToolCallEvent[] | undefined,
): ToolCallEvent[] | undefined {
  if (!toolCalls?.length || hasConcreteWebSearchToolCall(toolCalls)) {
    return toolCalls;
  }
  const runningNativeTool = toolCalls.findLast(
    (toolCall) =>
      toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
      toolCall.status === 'running',
  );
  if (!runningNativeTool) {
    return toolCalls;
  }

  runningNativeTool.displayName =
    runningNativeTool.displayName || $t('common.globalAiChat.toolNativeSearch');
  runningNativeTool.status = 'error';
  runningNativeTool.summaryPayload = {
    ...runningNativeTool.summaryPayload,
    provider: NATIVE_WEB_SEARCH_PROVIDER,
    status: 'error',
  };
  return toolCalls;
}

export function hasNativeSearchProgressSignal(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }
  const metadata = normalizeObjectRecord(payload.metadata);
  const progressKinds = new Set([
    ...normalizeStringList(metadata?.stream_progress_kinds),
    ...normalizeStringList(payload.stream_progress_kinds),
  ]);
  if (
    progressKinds.has('web_search_in_progress') ||
    progressKinds.has('native_search_in_progress')
  ) {
    return true;
  }
  if (!metadata) {
    return false;
  }
  if (metadata.native_search_progress === true) {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search_status) === 'running') {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search) === 'running') {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search_state) === 'running') {
    return true;
  }
  return normalizeObjectRecordList(payload.provider_events).some((item) => {
    const itemMetadata = normalizeObjectRecord(item.metadata);
    return (
      normalizeOptionalString(itemMetadata?.auto_fetch_gate_reason) ===
      'native_search_running'
    );
  });
}

export function hasIntentPlanNativeSearchCompletion(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }

  const metadata = normalizeObjectRecord(payload.metadata);
  const intentPlanItems = [
    ...normalizeObjectRecordList(payload.intent_plan),
    ...normalizeObjectRecordList(metadata?.intent_plan),
  ];

  return intentPlanItems.some((item) => {
    const completedTools = normalizeStringList(item.completed_by_tool_names);
    return (
      completedTools.includes(NATIVE_WEB_SEARCH_TOOL_NAME) ||
      completedTools.includes('web_search')
    );
  });
}

export function hasNativeSearchCompletionSignal(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }
  const metadata = normalizeObjectRecord(payload.metadata);
  if (metadata) {
    if (metadata.native_search_completed === true) {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search_status) === 'success') {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search) === 'success') {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search_state) === 'success') {
      return true;
    }
  }
  if (hasIntentPlanNativeSearchCompletion(payload)) {
    return true;
  }
  return normalizeObjectRecordList(payload.intent_plan).some((item) => {
    const itemMetadata = normalizeObjectRecord(item.metadata);
    return (
      normalizeOptionalString(itemMetadata?.auto_fetch_gate_reason) ===
      'native_search_completed'
    );
  });
}

export function resolveNativeSearchToolStatus(
  ...sources: unknown[]
): Extract<ToolCallEvent['status'], 'running' | 'success'> | null {
  let sawProgress = false;
  for (const source of sources) {
    if (hasNativeSearchCompletionSignal(source)) {
      return 'success';
    }
    if (hasNativeSearchProgressSignal(source)) {
      sawProgress = true;
    }
  }
  return sawProgress ? 'running' : null;
}
