import type {
  MonitoringConversationMessage,
  MonitoringTurnFlowPayload,
} from '../../api';

import type {
  ChatAttachment,
  ChatMessage,
} from '#/types/ai-chat';

import { toTurnFlowFirstChatMessage } from '#/components/business/ai-chat-panel/turn-flow-first-message';
import { $t } from '#/locales';
import { visibleRuntimeDiagnosticTokens } from '#/utils/ai-runtime-diagnostics';
import { toAbsoluteApiUrl } from '#/utils/image';

function asRecord(value: unknown): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function normalizeIdentityPart(value: unknown): string | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return asString(value);
}

function normalizeStringList(value: unknown): string[] {
  return visibleRuntimeDiagnosticTokens(value);
}

function normalizeContextSources(
  value: unknown,
): ChatMessage['contextSources'] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const normalized: NonNullable<ChatMessage['contextSources']> = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) {
      continue;
    }
    const metadata = asRecord(record.metadata);
    normalized.push({
      active: asBoolean(record.active),
      kind: asString(record.kind),
      metadata: metadata ?? undefined,
      name: asString(record.name),
    });
  }
  return normalized.length > 0 ? normalized : undefined;
}

function resolvePersistedAssistantError(
  metadata: null | Record<string, unknown>,
  fallbackContent: string,
): ChatMessage['error'] | undefined {
  if (!metadata || metadata.error !== true) {
    return undefined;
  }
  const messageText =
    asString(metadata.error_message) ||
    asString(fallbackContent) ||
    $t('common.http.internalServerError');
  return {
    code: asString(metadata.error_type),
    debugMessage:
      asString(metadata.error_debug_message) ||
      asString(metadata.raw_error_message),
    message: messageText,
    raw: metadata,
    source: 'sse',
    traceId: asString(metadata.error_trace_id),
  };
}

function normalizeAttachments(value: unknown): ChatAttachment[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const attachments = value
    .map((item) => {
      const record = asRecord(item);
      if (!record) {
        return null;
      }
      const rawUrl = asString(record.url);
      if (!rawUrl) {
        return null;
      }
      const normalizedUrl = toAbsoluteApiUrl(rawUrl) || rawUrl;
      const rawType = asString(record.type);
      let type: ChatAttachment['type'] = 'file';
      if (
        rawType === 'audio' ||
        rawType === 'file' ||
        rawType === 'image' ||
        rawType === 'video'
      ) {
        type = rawType;
      }
      return {
        attachment_id:
          typeof record.attachment_id === 'number'
            ? record.attachment_id
            : undefined,
        type,
        url: normalizedUrl,
        name: asString(record.name),
        mime_type: asString(record.mime_type),
      } as ChatAttachment;
    })
    .filter((item): item is ChatAttachment => item !== null);
  return attachments.length > 0 ? attachments : undefined;
}

function hasTurnFlowShape(value: unknown): value is MonitoringTurnFlowPayload {
  const record = asRecord(value);
  if (!record) {
    return false;
  }
  return Array.isArray(record.timeline) || Array.isArray(record.evidence);
}

export function extractMonitoringMessageTurnFlow(
  message: MonitoringConversationMessage,
): MonitoringTurnFlowPayload | undefined {
  if (hasTurnFlowShape(message.turn_flow)) {
    return message.turn_flow;
  }
  const metadata = asRecord(message.metadata);
  if (!metadata) {
    return undefined;
  }
  if (hasTurnFlowShape(metadata.turn_flow)) {
    return metadata.turn_flow as MonitoringTurnFlowPayload;
  }
  if (hasTurnFlowShape(metadata.turnFlow)) {
    return metadata.turnFlow as MonitoringTurnFlowPayload;
  }
  return undefined;
}

function normalizeMonitoringRole(rawRole: unknown): ChatMessage['role'] {
  const normalized = asString(rawRole) ?? 'assistant';
  if (normalized === 'assistant' || normalized === 'user') {
    return normalized;
  }
  return normalized as ChatMessage['role'];
}

function resolveMonitoringClientKey(
  message: MonitoringConversationMessage,
  role: ChatMessage['role'],
): string {
  const messageRecord = message as unknown as Record<string, unknown>;
  const persistedIdentity = [
    message.id,
    messageRecord.message_id,
    messageRecord.messageId,
    messageRecord.id,
  ]
    .map((value) => normalizeIdentityPart(value))
    .find(Boolean);
  if (persistedIdentity) {
    return `monitoring-message-${persistedIdentity}`;
  }
  return [
    'monitoring-message-fallback',
    normalizeIdentityPart(message.created_at) ?? 'unknown-time',
    role,
    normalizeIdentityPart(message.sequence) ?? 'unknown-sequence',
  ].join('-');
}

export function toMonitoringChatMessage(
  message: MonitoringConversationMessage,
  _index?: number,
): ChatMessage {
  const metadata = asRecord(message.metadata);
  const role = normalizeMonitoringRole(message.role);
  const turnFlow = extractMonitoringMessageTurnFlow(message);
  const turnFlowRecord = asRecord(turnFlow);
  const turnRecord = asRecord(metadata?.turn_record);

  const failureKind =
    asString(metadata?.failure_kind) ||
    asString(turnRecord?.failure_kind) ||
    asString(turnFlowRecord?.failure_kind) ||
    asString(turnFlowRecord?.failureKind);
  const finalStageStatus =
    asString(turnFlowRecord?.final_stage_status) ||
    asString(turnFlowRecord?.finalStageStatus);

  let turnOutcome =
    asString(metadata?.turn_outcome) ||
    asString(turnRecord?.turn_outcome) ||
    asString(turnFlowRecord?.turn_outcome) ||
    asString(turnFlowRecord?.turnOutcome);
  if (
    finalStageStatus === 'error' ||
    finalStageStatus === 'failed' ||
    (turnOutcome === 'partial' && failureKind) ||
    (!turnOutcome && failureKind)
  ) {
    turnOutcome = 'failed';
  }

  const completionReasonFromTurnFlow =
    asString(turnFlowRecord?.completion_reason) ||
    asString(turnFlowRecord?.completionReason);
  const terminationReason =
    asString(metadata?.termination_reason) ||
    asString(turnRecord?.termination_reason) ||
    completionReasonFromTurnFlow;
  const completionReason =
    asString(metadata?.completion_reason) ||
    terminationReason ||
    completionReasonFromTurnFlow;

  const selectedToolNames = (() => {
    const fromMetadata = normalizeStringList(metadata?.selected_tool_names);
    if (fromMetadata.length > 0) {
      return fromMetadata;
    }
    const fromTurnRecord = normalizeStringList(turnRecord?.selected_tool_names);
    return fromTurnRecord.length > 0 ? fromTurnRecord : undefined;
  })();

  const selectedSkillNames = (() => {
    const fromMetadata = normalizeStringList(metadata?.selected_skill_names);
    if (fromMetadata.length > 0) {
      return fromMetadata;
    }
    const fromTurnRecord = normalizeStringList(
      turnRecord?.selected_skill_names,
    );
    return fromTurnRecord.length > 0 ? fromTurnRecord : undefined;
  })();

  const contextSources =
    normalizeContextSources(metadata?.context_sources) ||
    normalizeContextSources(turnRecord?.context_sources);

  const persistedError = resolvePersistedAssistantError(
    metadata,
    message.content ?? '',
  );
  const interrupted =
    typeof metadata?.interrupted === 'boolean'
      ? metadata.interrupted
      : terminationReason === 'interrupted';
  const partialFromMetadata =
    typeof metadata?.partial === 'boolean'
      ? metadata.partial
      : turnOutcome === 'partial';
  const partial = partialFromMetadata || interrupted;

  const nextMessage: ChatMessage = {
    clientKey: resolveMonitoringClientKey(message, role),
    role,
    content: message.content ?? '',
    streaming: false,
    created_at: message.created_at,
    tokenUsage: message.token_count ?? undefined,
    agent_id: message.agent_id ?? null,
    agent_name: message.agent_name ?? null,
    agent_avatar: message.agent_avatar ?? null,
    turnFlow: turnFlow as ChatMessage['turnFlow'],
    attachments: normalizeAttachments(metadata?.attachments),
    completionReason,
    interrupted,
    partial,
    turnOutcome,
    terminationReason,
    protocolPath:
      asString(metadata?.protocol_path) || asString(turnRecord?.protocol_path),
    selectedToolNames,
    selectedSkillNames,
    contextSources,
    error: persistedError,
  };
  return toTurnFlowFirstChatMessage(nextMessage);
}
