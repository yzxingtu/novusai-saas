import type { ToolCallEvent } from './types';

import type { RawMessageItem } from '#/api/shared/ai-chat';

export interface PersistedToolResponse {
  content: string;
  displayName?: string;
  error?: string;
  errorType?: string;
  name?: string;
  resultLink?: string;
  success: boolean;
  summary?: string;
  summaryPayload?: Record<string, unknown>;
}

export type PersistedToolResponseMap = Map<string, PersistedToolResponse>;

export function buildToolResponseMap(
  messages: RawMessageItem[],
): PersistedToolResponseMap {
  const responseMap: PersistedToolResponseMap = new Map();
  for (const messageItem of messages) {
    if (messageItem.role !== 'tool' || !messageItem.tool_call_id) {
      continue;
    }
    const metadata = (messageItem.metadata ?? {}) as Record<string, unknown>;
    const toolSuccess = metadata.tool_success !== false; // default true for legacy data
    responseMap.set(messageItem.tool_call_id, {
      content: messageItem.content ?? '',
      displayName: (metadata.tool_display_name as string) || undefined,
      error: (metadata.tool_error as string) || undefined,
      errorType: (metadata.tool_error_type as string) || undefined,
      name: messageItem.tool_name ?? undefined,
      resultLink: (metadata.tool_result_link as string) || undefined,
      success: toolSuccess,
      summary: (metadata.tool_summary as string) || undefined,
      summaryPayload:
        (metadata.tool_summary_payload as Record<string, unknown>) || undefined,
    });
  }
  return responseMap;
}

export function resolveToolCallStatus(
  response: PersistedToolResponse | undefined,
  persistedTc: Record<string, unknown>,
): ToolCallEvent['status'] {
  if (response) {
    return response.success ? 'success' : 'error';
  }
  if (persistedTc.pending_confirmation || persistedTc.pending_consent) {
    return 'running';
  }
  if (persistedTc.success === true) {
    return 'success';
  }
  return 'error';
}
