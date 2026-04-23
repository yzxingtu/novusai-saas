import type {
  ChatMessage,
  RagSource,
  ToolCallEvent,
  TurnFlowEvidenceKind,
  TurnFlowStageStatus,
} from './types';

import {
  normalizeObjectRecord,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';
import {
  buildToolEvidencePayload,
  getOrCreateCanonicalTurnFlow,
  normalizeThinkingStageText,
  normalizeTurnFlowViewModel,
  resolveThinkingStage,
  syncToolExecutionStage,
  upsertEvidence,
  upsertStage,
  upsertToolEvidence,
} from './chat-message-turn-flow-ingestion';

function normalizeNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function summarize(text: string, maxLength = 120): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

// Legacy assistant fields remain readable only for non-streaming persisted history.
// Live turns must hydrate canonical turnFlow via turn_stage / turn_evidence / done.
function isPersistedAssistantFallbackMessage(message: ChatMessage): boolean {
  return message.role === 'assistant' && message.streaming !== true;
}

function buildLegacyFallbackToolEvidenceId(
  toolCall: ToolCallEvent,
  index: number,
): string {
  const toolName = normalizeOptionalString(toolCall.name) ?? 'tool';
  return `legacy-tool-${toolName}-${index + 1}`;
}

function hasCanonicalToolEvidenceForLegacyCall(
  message: ChatMessage,
  toolCall: ToolCallEvent,
): boolean {
  const flow = normalizeTurnFlowViewModel(message.turnFlow);
  if (!flow) {
    return false;
  }
  const toolCallId = normalizeOptionalString(toolCall.id);
  if (toolCallId) {
    return flow.evidence.some(
      (item) => item.kind === 'tool' && item.toolCallId === toolCallId,
    );
  }
  return false;
}

function applyToolCallsToTurnFlow(
  message: ChatMessage,
  toolCalls: ToolCallEvent[] | undefined,
): void {
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  for (const [index, toolCall] of toolCalls.entries()) {
    if (!toolCall?.name) {
      continue;
    }
    if (hasCanonicalToolEvidenceForLegacyCall(message, toolCall)) {
      continue;
    }
    const toolCallId = normalizeOptionalString(toolCall.id);
    upsertToolEvidence(
      flow,
      {
        ...buildToolEvidencePayload({
          argumentsValue: toolCall.arguments,
          displayName: normalizeOptionalString(toolCall.displayName),
          durationMs: normalizeNumber(toolCall.durationMs),
          error: normalizeOptionalString(toolCall.error),
          errorType: normalizeOptionalString(toolCall.errorType),
          output: normalizeOptionalString(toolCall.output),
          resultLink: normalizeOptionalString(toolCall.resultLink),
          skillName: normalizeOptionalString(toolCall.skillName),
          skillType: normalizeOptionalString(toolCall.skillType),
          startedAt: normalizeNumber(toolCall.startedAt),
          status: toolCall.status,
          summary: normalizeOptionalString(toolCall.summary),
          summaryPayload:
            normalizeObjectRecord(toolCall.summaryPayload) ?? undefined,
          toolCallId,
          toolName: toolCall.name,
        }),
        ...(toolCallId
          ? {}
          : { id: buildLegacyFallbackToolEvidenceId(toolCall, index) }),
      },
    );
  }
  syncToolExecutionStage(flow);
  message.turnFlow = flow;
}

export function applyStreamingToolStartToTurnFlow(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const toolName = normalizeOptionalString(event.name);
  if (!toolName) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  upsertToolEvidence(
    flow,
    buildToolEvidencePayload({
      argumentsValue: normalizeObjectRecord(event.arguments) ?? undefined,
      displayName: normalizeOptionalString(
        event.display_name ?? event.displayName,
      ),
      skillName: normalizeOptionalString(event.skill_name ?? event.skillName),
      skillType: normalizeOptionalString(event.skill_type ?? event.skillType),
      startedAt: Date.now(),
      status: 'running',
      toolCallId:
        normalizeOptionalString(event.tool_call_id) ??
        normalizeOptionalString(event.toolCallId) ??
        normalizeOptionalString(event.id),
      toolName,
    }),
  );
  syncToolExecutionStage(flow);
  message.turnFlow = flow;
}

export function applyStreamingToolResultToTurnFlow(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const toolName = normalizeOptionalString(event.name);
  if (!toolName) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  upsertToolEvidence(
    flow,
    buildToolEvidencePayload({
      argumentsValue: normalizeObjectRecord(event.arguments) ?? undefined,
      displayName: normalizeOptionalString(
        event.display_name ?? event.displayName,
      ),
      durationMs: normalizeNumber(event.duration_ms ?? event.durationMs),
      error: normalizeOptionalString(event.error),
      errorType: normalizeOptionalString(event.error_type ?? event.errorType),
      output: normalizeOptionalString(event.output),
      resultLink: normalizeOptionalString(
        event.result_link ?? event.resultLink,
      ),
      skillName: normalizeOptionalString(event.skill_name ?? event.skillName),
      skillType: normalizeOptionalString(event.skill_type ?? event.skillType),
      status: event.success ? 'success' : 'error',
      summary: normalizeOptionalString(event.summary),
      summaryPayload:
        normalizeObjectRecord(event.summary_payload ?? event.summaryPayload) ??
        undefined,
      toolCallId:
        normalizeOptionalString(event.tool_call_id) ??
        normalizeOptionalString(event.toolCallId) ??
        normalizeOptionalString(event.id),
      toolName,
    }),
  );
  syncToolExecutionStage(flow);
  message.turnFlow = flow;
}

export function applyNativeSearchStatusToTurnFlow(
  message: ChatMessage,
  {
    displayName,
    status,
    toolName,
  }: {
    displayName?: string;
    status: 'running' | 'success';
    toolName: string;
  },
): void {
  const flow = getOrCreateCanonicalTurnFlow(message);
  upsertEvidence(
    flow,
    buildToolEvidencePayload({
      displayName,
      status,
      toolName,
      toolCallId: toolName,
    }),
  );
  syncToolExecutionStage(flow);
  message.turnFlow = flow;
}

export function appendThinkingDeltaToTurnFlow(
  message: ChatMessage,
  delta: string | undefined,
): void {
  if (!isPersistedAssistantFallbackMessage(message)) {
    return;
  }
  appendThinkingTextToTurnFlow(message, delta);
}

function appendThinkingTextToTurnFlow(
  message: ChatMessage,
  text: string | undefined,
): void {
  const normalizedDelta = normalizeOptionalString(text);
  if (!normalizedDelta) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  const existingStage = resolveThinkingStage(flow);
  const nextText = `${
    normalizeThinkingStageText(existingStage) ?? ''
  }${normalizedDelta}`;
  upsertStage(flow, {
    detailLines: [nextText],
    id: existingStage?.id ?? 'turn-thinking',
    status: message.streaming ? 'running' : 'completed',
    summary: summarize(nextText, 240),
    type: 'thinking',
  });
  message.turnFlow = flow;
}

export function promoteStreamingContentToThinkingTurnFlow(
  message: ChatMessage,
): void {
  if (!message.content) {
    return;
  }
  appendThinkingTextToTurnFlow(message, message.content);
  message.content = '';
}

export function applyOptimizingToolsToTurnFlow(
  message: ChatMessage,
  selection: { selected?: number; total?: number },
): void {
  if (!isPersistedAssistantFallbackMessage(message)) {
    return;
  }
  const selected = normalizeNumber(selection.selected);
  const total = normalizeNumber(selection.total);
  if (selected === undefined && total === undefined) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  const existingStage = flow.timeline.findLast(
    (stage) => stage.type === 'tool_selection',
  );
  const normalizedSelected = selected ?? 0;
  const normalizedTotal = total ?? normalizedSelected;
  let selectionStatus: TurnFlowStageStatus = 'completed';
  if (normalizedTotal > 0) {
    selectionStatus = normalizedSelected > 0 ? 'completed' : 'skipped';
  }
  upsertStage(flow, {
    id: existingStage?.id ?? 'turn-tool-selection',
    metrics: {
      ...existingStage?.metrics,
      selected: normalizedSelected,
      total: normalizedTotal,
    },
    status: selectionStatus,
    type: 'tool_selection',
  });
  message.turnFlow = flow;
}

function toEvidenceKindFromRagSource(source: RagSource): TurnFlowEvidenceKind {
  return source.source_kind === 'ephemeral_doc' ? 'web' : 'knowledge_base';
}

function toEvidenceIdFromRagSource(source: RagSource, index: number): string {
  const sourceKey =
    source.knowledge_base_id ??
    source.doc_id ??
    source.knowledge_base_name ??
    source.doc_name;
  return `rag-${toEvidenceKindFromRagSource(source)}-${sourceKey ?? index + 1}`;
}

export function applyRagSourcesToTurnFlow(
  message: ChatMessage,
  sources: RagSource[] | undefined,
): void {
  if (!isPersistedAssistantFallbackMessage(message)) {
    return;
  }
  if (!Array.isArray(sources) || sources.length === 0) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  flow.evidence = flow.evidence.filter(
    (item) => item.kind !== 'knowledge_base' && item.kind !== 'web',
  );
  sources.forEach((source, index) => {
    upsertEvidence(flow, {
      id: toEvidenceIdFromRagSource(source, index),
      kind: toEvidenceKindFromRagSource(source),
      ...(source.doc_name ? { title: source.doc_name } : {}),
      ...(source.snippet ? { snippet: source.snippet } : {}),
      ...(source.score === undefined ? {} : { score: source.score }),
      ...(source.knowledge_base_name || source.doc_name
        ? { sourceRef: source.knowledge_base_name ?? source.doc_name }
        : {}),
    });
  });
  message.turnFlow = flow;
}

export interface PersistedAssistantTurnFlowFallbackInput {
  optimizingTools?: { selected?: number; total?: number };
  ragSources?: RagSource[];
  thinkingContent?: string;
  toolCalls?: ToolCallEvent[];
}

export type AssistantTurnFlowProjectionInput =
  PersistedAssistantTurnFlowFallbackInput;

export function applyPersistedAssistantFieldFallbackToTurnFlow(
  message: ChatMessage,
  input: PersistedAssistantTurnFlowFallbackInput,
): void {
  if (!isPersistedAssistantFallbackMessage(message)) {
    return;
  }

  if (normalizeTurnFlowViewModel(message.turnFlow)) {
    return;
  }

  const thinkingContent = normalizeOptionalString(input.thinkingContent);
  const toolCalls =
    Array.isArray(input.toolCalls) && input.toolCalls.length > 0
      ? input.toolCalls
      : undefined;
  const ragSources =
    Array.isArray(input.ragSources) && input.ragSources.length > 0
      ? input.ragSources
      : undefined;
  const selected = normalizeNumber(input.optimizingTools?.selected);
  const total = normalizeNumber(input.optimizingTools?.total);
  const hasSelectionInput = selected !== undefined || total !== undefined;

  if (!thinkingContent && !toolCalls && !ragSources && !hasSelectionInput) {
    return;
  }

  // Persisted-history compatibility only: live streaming owns canonical
  // turnFlow upstream and must never route through this fallback seam.
  if (hasSelectionInput) {
    applyOptimizingToolsToTurnFlow(message, {
      ...(selected === undefined ? {} : { selected }),
      ...(total === undefined ? {} : { total }),
    });
  }

  if (thinkingContent) {
    appendThinkingDeltaToTurnFlow(message, thinkingContent);
  }

  if (toolCalls) {
    applyToolCallsToTurnFlow(message, toolCalls);
  }

  if (ragSources) {
    applyRagSourcesToTurnFlow(message, ragSources);
  }
}

export const projectAssistantFieldsIntoTurnFlow =
  applyPersistedAssistantFieldFallbackToTurnFlow;
