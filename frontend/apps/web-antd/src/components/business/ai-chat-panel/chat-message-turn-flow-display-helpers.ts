import type {
  ChatMessage,
  RagSource,
  ToolCallEvent,
  TurnFlowStage,
  TurnFlowStageStatus,
  TurnFlowStageType,
  TurnFlowViewModel,
} from './types';

import { $t } from '#/locales';

import {
  cloneAnswerCard,
  cloneEvidence,
  cloneStage,
  normalizeNumber,
  normalizeThinkingStageText,
  normalizeTurnFlowViewModel,
  resolveThinkingStage,
} from './chat-message-turn-flow-core';
import {
  normalizeObjectRecord,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';

export type TurnFlowStageForDisplay = TurnFlowStage;

export interface TurnFlowForDisplay extends TurnFlowViewModel {
  failureKind?: string;
  turnFlowComplete?: boolean;
  turnOutcome?: string;
  timeline: TurnFlowStageForDisplay[];
}

const FAILURE_COMPLETION_REASONS = new Set([
  'content_filter',
  'incomplete',
  'length',
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'tool_error',
  'tool_round_failed',
  'cancelled',
  'canceled',
]);

const TERMINAL_STAGE_TYPES = new Set<TurnFlowStageType>([
  'completed',
  'failed',
]);

const TOOL_SELECTION_SELECTED_METRIC_KEYS = [
  'selected',
  'candidate_tools_count',
  'candidateToolsCount',
  'selected_count',
  'selectedCount',
] as const;

const TOOL_SELECTION_TOTAL_METRIC_KEYS = [
  'total',
  'all_tools_count',
  'allToolsCount',
  'total_tools_count',
  'totalToolsCount',
  'tool_rounds',
  'count',
  'source_count',
  'sourceCount',
  'result_count',
  'resultCount',
  'evidence_count',
  'evidenceCount',
] as const;
const TRANSCRIPT_COPY_MEANINGFUL_CHAR_RE = /[\p{L}\p{N}]/u;
const TRANSCRIPT_COPY_SYMBOL_ONLY_RE = /^[\p{P}\p{S}\s]+$/u;

function normalizeMeaningfulStageCopy(value: unknown): string | undefined {
  const normalized = normalizeOptionalString(value);
  if (
    !normalized ||
    TRANSCRIPT_COPY_SYMBOL_ONLY_RE.test(normalized) ||
    !TRANSCRIPT_COPY_MEANINGFUL_CHAR_RE.test(normalized)
  ) {
    return undefined;
  }
  return normalized;
}

function readMetricNumber(
  source: Record<string, number | string> | undefined,
  keys: readonly string[],
): number | undefined {
  if (!source) {
    return undefined;
  }
  for (const key of keys) {
    const normalized = normalizeNumber(source[key]);
    if (normalized !== undefined) {
      return normalized;
    }
  }
  return undefined;
}

function toDisplayStage(stage: TurnFlowStage): TurnFlowStageForDisplay {
  const clonedStage = cloneStage(stage);
  clonedStage.summary = normalizeMeaningfulStageCopy(clonedStage.summary);
  clonedStage.title = normalizeMeaningfulStageCopy(clonedStage.title);
  return clonedStage;
}

function toDisplayFailureKind(msg: ChatMessage): string | undefined {
  const record = normalizeObjectRecord(msg.turnFlow);
  if (!record) {
    return undefined;
  }
  return normalizeOptionalString(record.failure_kind ?? record.failureKind);
}

function toDisplayTurnOutcome(msg: ChatMessage): string | undefined {
  const record = normalizeObjectRecord(msg.turnFlow);
  if (!record) {
    return undefined;
  }
  return normalizeOptionalString(record.turn_outcome ?? record.turnOutcome);
}

function createDisplayFlowFromCanonical(
  msg: ChatMessage,
  flow: TurnFlowViewModel,
): TurnFlowForDisplay {
  const answerCard = cloneAnswerCard(flow.answerCard);
  const failureKind = toDisplayFailureKind(msg);
  const turnOutcome = toDisplayTurnOutcome(msg);
  return {
    evidence: flow.evidence.map((item) => cloneEvidence(item)),
    timeline: flow.timeline.map((stage) => toDisplayStage(stage)),
    ...(answerCard ? { answerCard } : {}),
    ...(flow.completionReason
      ? { completionReason: flow.completionReason }
      : {}),
    ...(failureKind ? { failureKind } : {}),
    ...(flow.finalStageStatus
      ? { finalStageStatus: flow.finalStageStatus }
      : {}),
    ...(flow.interrupted ? { interrupted: true } : {}),
    ...(flow.errorSurface ? { errorSurface: { ...flow.errorSurface } } : {}),
    ...(flow.traceId ? { traceId: flow.traceId } : {}),
    ...(flow.complete === undefined ? {} : { complete: flow.complete }),
    ...(flow.complete === undefined ? {} : { turnFlowComplete: flow.complete }),
    ...(turnOutcome ? { turnOutcome } : {}),
  };
}

function createEmptyTurnFlowForDisplay(msg: ChatMessage): TurnFlowForDisplay {
  const completionReason = normalizeOptionalString(msg.completionReason);
  const turnOutcome = normalizeOptionalString(msg.turnOutcome);
  return {
    evidence: [],
    timeline: [],
    ...(completionReason ? { completionReason } : {}),
    ...(turnOutcome ? { turnOutcome } : {}),
    ...(msg.interrupted ? { interrupted: true } : {}),
  };
}

function extractErrorSurfaceMessage(
  flow: TurnFlowForDisplay,
): string | undefined {
  return (
    normalizeOptionalString(flow.errorSurface?.message) ??
    normalizeOptionalString(flow.errorSurface?.summary) ??
    normalizeOptionalString(flow.errorSurface?.detail) ??
    normalizeOptionalString(flow.errorSurface?.error) ??
    normalizeOptionalString(flow.errorSurface?.reason)
  );
}

function isFailureCompletionReason(reason: string | undefined) {
  return !!reason && FAILURE_COMPLETION_REASONS.has(reason.toLowerCase());
}

function pickFailureSummary(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
  timeline: TurnFlowStageForDisplay[],
): string | undefined {
  for (let index = timeline.length - 1; index >= 0; index -= 1) {
    if (timeline[index]?.type !== 'failed') {
      continue;
    }
    const summary = normalizeOptionalString(timeline[index]?.summary);
    if (summary) {
      return summary;
    }
  }
  return (
    extractErrorSurfaceMessage(flow) ??
    normalizeOptionalString(msg.error?.message) ??
    normalizeOptionalString(flow.failureKind) ??
    normalizeOptionalString(flow.completionReason)
  );
}

function hasTerminalFailure(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
): boolean {
  if (flow.finalStageStatus === 'error') {
    return true;
  }
  if (msg.error || msg.requestFailedRetry) {
    return true;
  }
  if (flow.turnOutcome === 'failed') {
    return true;
  }
  if (flow.turnOutcome === 'partial' && flow.failureKind) {
    return true;
  }
  if (isFailureCompletionReason(flow.completionReason)) {
    return true;
  }
  if (flow.failureKind && flow.turnOutcome !== 'success') {
    return true;
  }

  for (let index = flow.timeline.length - 1; index >= 0; index -= 1) {
    const stage = flow.timeline[index];
    if (!stage || !TERMINAL_STAGE_TYPES.has(stage.type)) {
      continue;
    }
    return stage.type === 'failed' || stage.status === 'error';
  }
  return false;
}

function inferTerminalStatus(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
  failedTerminal: boolean,
): TurnFlowStageStatus | undefined {
  if (failedTerminal) {
    return 'error';
  }
  if (flow.finalStageStatus) {
    return flow.finalStageStatus;
  }
  if (
    flow.interrupted ||
    msg.interrupted ||
    msg.stoppedByUser ||
    flow.completionReason === 'interrupted'
  ) {
    return 'interrupted';
  }
  const hasTerminalStage = flow.timeline.some((stage) =>
    TERMINAL_STAGE_TYPES.has(stage.type),
  );
  if (
    flow.turnFlowComplete === true ||
    (!msg.streaming && (hasTerminalStage || Boolean(flow.completionReason)))
  ) {
    return 'completed';
  }
  return undefined;
}

function inferNonStreamingTerminalHintStatus(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
): TurnFlowStageStatus | undefined {
  if (msg.streaming) {
    return undefined;
  }
  const hasRunningStage = flow.timeline.some(
    (stage) => stage.status === 'running',
  );
  if (!hasRunningStage) {
    return undefined;
  }
  if (msg.error || msg.requestFailedRetry) {
    return 'error';
  }
  if (
    flow.interrupted ||
    msg.interrupted ||
    msg.stoppedByUser ||
    msg.partial ||
    flow.completionReason === 'interrupted'
  ) {
    return 'interrupted';
  }
  if (
    flow.timeline.some(
      (stage) => stage.status === 'error' || stage.type === 'failed',
    )
  ) {
    return 'error';
  }
  if (flow.timeline.some((stage) => stage.status === 'interrupted')) {
    return 'interrupted';
  }
  if (
    flow.timeline.some(
      (stage) =>
        stage.status === 'completed' ||
        stage.status === 'skipped' ||
        stage.type === 'completed',
    ) ||
    Boolean(normalizeOptionalString(msg.content))
  ) {
    return 'completed';
  }
  return undefined;
}

function ensureFailureTerminalStage(
  timeline: TurnFlowStageForDisplay[],
  summary: string | undefined,
) {
  let failedStageIndex = -1;
  for (let index = timeline.length - 1; index >= 0; index -= 1) {
    if (timeline[index]?.type === 'failed') {
      failedStageIndex = index;
      break;
    }
  }

  if (failedStageIndex >= 0) {
    const failedStage = timeline[failedStageIndex];
    if (failedStage) {
      timeline[failedStageIndex] = {
        ...failedStage,
        status: 'error',
        summary: failedStage.summary ?? summary,
        type: 'failed',
      };
      return;
    }
  }

  let terminalStageIndex = -1;
  for (let index = timeline.length - 1; index >= 0; index -= 1) {
    const stage = timeline[index];
    if (stage && TERMINAL_STAGE_TYPES.has(stage.type)) {
      terminalStageIndex = index;
      break;
    }
  }

  if (terminalStageIndex >= 0) {
    const terminalStage = timeline[terminalStageIndex];
    if (terminalStage) {
      timeline[terminalStageIndex] = {
        ...terminalStage,
        status: 'error',
        summary: summary ?? terminalStage.summary,
        type: 'failed',
      };
      return;
    }
  }

  timeline.push({
    id: 'turn-failed-terminal',
    status: 'error',
    summary,
    type: 'failed',
  });
}

function normalizeCanonicalTurnFlowForDisplay(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
): TurnFlowForDisplay {
  const timeline = flow.timeline.map((stage) => toDisplayStage(stage));
  const failedTerminal = hasTerminalFailure(flow, msg);
  const failureSummary = failedTerminal
    ? pickFailureSummary(flow, msg, timeline)
    : undefined;

  if (failedTerminal) {
    for (let index = 0; index < timeline.length; index += 1) {
      const stage = timeline[index];
      if (stage?.type === 'answer_assembly' && stage.status !== 'error') {
        timeline[index] = {
          ...stage,
          status: 'error',
          summary: stage.summary ?? failureSummary,
        };
      }
    }
    ensureFailureTerminalStage(timeline, failureSummary);
  }

  const terminalStatus =
    inferTerminalStatus(flow, msg, failedTerminal) ??
    inferNonStreamingTerminalHintStatus(flow, msg);

  if (terminalStatus && !msg.streaming) {
    for (let index = 0; index < timeline.length; index += 1) {
      const stage = timeline[index];
      if (stage?.status !== 'running') {
        continue;
      }
      timeline[index] = {
        ...stage,
        status: terminalStatus,
      };
    }
  }

  return {
    ...flow,
    timeline,
  };
}

export function getThinkingContentForDisplay(
  msg: ChatMessage,
): string | undefined {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  return flow
    ? normalizeThinkingStageText(resolveThinkingStage(flow))
    : undefined;
}

export function getOptimizingToolsForDisplay(
  msg: ChatMessage,
): undefined | { selected: number; total: number } {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  const selectionStage = flow?.timeline.findLast(
    (stage) => stage.type === 'tool_selection',
  );
  const selected = readMetricNumber(
    selectionStage?.metrics,
    TOOL_SELECTION_SELECTED_METRIC_KEYS,
  );
  const total = readMetricNumber(
    selectionStage?.metrics,
    TOOL_SELECTION_TOTAL_METRIC_KEYS,
  );
  if (selected !== undefined || total !== undefined) {
    return {
      selected: selected ?? 0,
      total: total ?? selected ?? 0,
    };
  }
  return undefined;
}

export function getToolCallsForDisplay(
  msg: ChatMessage,
): ToolCallEvent[] | undefined {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  if (!flow) {
    return undefined;
  }
  const toolCalls = flow.evidence
    .filter((item) => item.kind === 'tool')
    .map((item, index) => ({
      id: item.toolCallId ?? `evidence-tool-${index + 1}`,
      name:
        item.toolName ||
        item.sourceRef ||
        item.title ||
        $t('common.globalAiChat.toolFallbackName', {
          index: index + 1,
        }),
      status: item.status || ('success' as const),
      ...(item.arguments ? { arguments: item.arguments } : {}),
      ...(item.displayName ? { displayName: item.displayName } : {}),
      ...(item.durationMs === undefined ? {} : { durationMs: item.durationMs }),
      ...(item.error ? { error: item.error } : {}),
      ...(item.errorType ? { errorType: item.errorType } : {}),
      ...(item.output ? { output: item.output } : {}),
      ...(item.resultLink || item.url
        ? { resultLink: item.resultLink ?? item.url }
        : {}),
      ...(item.skillName ? { skillName: item.skillName } : {}),
      ...(item.skillType ? { skillType: item.skillType } : {}),
      ...(item.startedAt === undefined ? {} : { startedAt: item.startedAt }),
      ...(item.snippet ? { summary: item.snippet } : {}),
      ...(item.summaryPayload ? { summaryPayload: item.summaryPayload } : {}),
    }));
  const deduped = dedupeToolCallsForDisplay(toolCalls);
  return deduped.length > 0 ? deduped : undefined;
}

function normalizeToolCallText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function getToolCallDisplayKey(toolCall: ToolCallEvent): string {
  const id = normalizeToolCallText(toolCall.id);
  if (id) {
    return `id:${id}`;
  }
  const output = normalizeToolCallText(toolCall.output);
  const summary = normalizeToolCallText(toolCall.summary);
  const args = toolCall.arguments ? JSON.stringify(toolCall.arguments) : '';
  return [
    'shape',
    toolCall.name,
    toolCall.status,
    args,
    output || summary,
  ].join('\u001F');
}

function preferDisplayValue<T>(
  current: T | undefined,
  incoming: T | undefined,
) {
  return current === undefined || current === null ? incoming : current;
}

function mergeToolCallForDisplay(
  current: ToolCallEvent,
  incoming: ToolCallEvent,
): ToolCallEvent {
  return {
    ...incoming,
    ...current,
    arguments: preferDisplayValue(current.arguments, incoming.arguments),
    displayName: preferDisplayValue(current.displayName, incoming.displayName),
    durationMs: preferDisplayValue(current.durationMs, incoming.durationMs),
    error: preferDisplayValue(current.error, incoming.error),
    errorType: preferDisplayValue(current.errorType, incoming.errorType),
    output: preferDisplayValue(current.output, incoming.output),
    resultLink: preferDisplayValue(current.resultLink, incoming.resultLink),
    skillName: preferDisplayValue(current.skillName, incoming.skillName),
    skillType: preferDisplayValue(current.skillType, incoming.skillType),
    startedAt: preferDisplayValue(current.startedAt, incoming.startedAt),
    summary: preferDisplayValue(current.summary, incoming.summary),
    summaryPayload: preferDisplayValue(
      current.summaryPayload,
      incoming.summaryPayload,
    ),
  };
}

function dedupeToolCallsForDisplay(
  toolCalls: ToolCallEvent[],
): ToolCallEvent[] {
  const byKey = new Map<string, ToolCallEvent>();
  for (const toolCall of toolCalls) {
    const key = getToolCallDisplayKey(toolCall);
    const existing = byKey.get(key);
    byKey.set(
      key,
      existing ? mergeToolCallForDisplay(existing, toolCall) : toolCall,
    );
  }
  return [...byKey.values()];
}

const RUNTIME_CONTEXT_EVIDENCE_LABELS = new Set([
  'gpt-5.5',
  'long_term_memory',
  'runtime_model',
  'runtime_model_capability',
  'session_memory',
  'skill_resolver',
]);

function hasUserFacingRetrievalEvidence(
  item: TurnFlowViewModel['evidence'][number],
) {
  const title = normalizeOptionalString(item.title)?.toLocaleLowerCase() ?? '';
  const sourceRef =
    normalizeOptionalString(item.sourceRef)?.toLocaleLowerCase() ?? '';
  if (
    RUNTIME_CONTEXT_EVIDENCE_LABELS.has(title) ||
    RUNTIME_CONTEXT_EVIDENCE_LABELS.has(sourceRef)
  ) {
    return false;
  }
  return Boolean(
    normalizeOptionalString(item.url) ||
    normalizeOptionalString(item.snippet) ||
    normalizeOptionalString(item.badge) ||
    normalizeOptionalString(item.docName) ||
    normalizeOptionalString(item.knowledgeBaseName) ||
    typeof item.score === 'number' ||
    normalizeOptionalString(item.sourceRef),
  );
}

export function getRagSourcesForDisplay(
  msg: ChatMessage,
): RagSource[] | undefined {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  if (!flow) {
    return undefined;
  }
  const ragSources = flow.evidence
    .filter(
      (item) =>
        (item.kind === 'knowledge_base' || item.kind === 'document') &&
        hasUserFacingRetrievalEvidence(item),
    )
    .map((item, index) => ({
      doc_id: index + 1,
      ...(typeof item.docId === 'number' ? { doc_id: item.docId } : {}),
      doc_name:
        item.docName ||
        item.title ||
        item.sourceRef ||
        $t('common.globalAiChat.turnSourceFallback', {
          index: index + 1,
        }),
      ...(typeof item.knowledgeBaseId === 'number'
        ? { knowledge_base_id: item.knowledgeBaseId }
        : {}),
      ...(item.knowledgeBaseName
        ? { knowledge_base_name: item.knowledgeBaseName }
        : {}),
      score:
        typeof item.score === 'number' && Number.isFinite(item.score)
          ? item.score
          : 0,
      snippet: item.snippet || '',
      source_kind:
        item.sourceKind === 'formal_kb' || item.kind === 'knowledge_base'
          ? ('formal_kb' as const)
          : ('ephemeral_doc' as const),
    }));
  return ragSources.length > 0 ? ragSources : undefined;
}

export function getTurnFlowForDisplay(msg: ChatMessage): TurnFlowForDisplay {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  if (!flow) {
    return createEmptyTurnFlowForDisplay(msg);
  }
  return normalizeCanonicalTurnFlowForDisplay(
    createDisplayFlowFromCanonical(msg, flow),
    msg,
  );
}
