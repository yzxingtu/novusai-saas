import type {
  ChatMessage,
  RagSource,
  ToolCallEvent,
  TurnAnswerCard,
  TurnAnswerCardSection,
  TurnEvidenceItem,
  TurnFlowErrorSurface,
  TurnFlowStage,
  TurnFlowStageStatus,
  TurnFlowStageType,
  TurnFlowViewModel,
} from './types';

import { normalizeTurnFlowViewModel } from './use-ai-chat-turn-flow';

type LegacyStageSource =
  | 'legacy-retrieval'
  | 'legacy-thinking'
  | 'legacy-tool-execution'
  | 'legacy-tool-selection';

export interface TurnFlowStageForDisplay extends TurnFlowStage {
  legacySource?: LegacyStageSource;
}

export interface TurnFlowForDisplay extends TurnFlowViewModel {
  answerCard?: TurnAnswerCard;
  evidence: TurnEvidenceItem[];
  failureKind?: string;
  finalStageStatus?: TurnFlowStageStatus;
  turnFlowComplete?: boolean;
  turnOutcome?: string;
  timeline: TurnFlowStageForDisplay[];
}

const TURN_STAGE_TYPES = new Set<TurnFlowStageType>([
  'answer_assembly',
  'completed',
  'failed',
  'retrieval',
  'thinking',
  'tool_execution',
  'tool_selection',
]);

const TURN_STAGE_STATUSES = new Set<TurnFlowStageStatus>([
  'completed',
  'error',
  'interrupted',
  'running',
  'skipped',
]);

const FAILURE_COMPLETION_REASONS = new Set([
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'tool_error',
  'tool_round_failed',
]);

const TERMINAL_STAGE_TYPES = new Set<TurnFlowStageType>([
  'completed',
  'failed',
]);

function normalizeOptionalString(value: unknown) {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function normalizeStringArray(value: unknown) {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const normalized = value
    .map((item) => normalizeOptionalString(item))
    .filter((item): item is string => item !== undefined);
  return normalized.length > 0 ? normalized : undefined;
}

function normalizeNumber(value: unknown) {
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

function normalizeBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') {
    return value;
  }
  return undefined;
}

function readMetricNumber(
  source: Record<string, unknown>,
  keys: string[],
): number | undefined {
  for (const key of keys) {
    const normalized = normalizeNumber(source[key]);
    if (normalized !== undefined) {
      return normalized;
    }
  }
  return undefined;
}

function readMetricText(
  source: Record<string, unknown>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const normalized = normalizeOptionalString(source[key]);
    if (normalized) {
      return normalized;
    }
  }
  return undefined;
}

function readMetricTextList(
  source: Record<string, unknown>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const normalizedList = normalizeStringArray(source[key]);
    if (normalizedList?.length) {
      return normalizedList.join(' -> ');
    }
  }
  return undefined;
}

function normalizeMetrics(value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined;
  }
  const source = value as Record<string, unknown>;
  const metrics: Record<string, number | string> = {};
  for (const [key, raw] of Object.entries(source)) {
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      metrics[key] = raw;
      continue;
    }
    const normalized = normalizeOptionalString(raw);
    if (normalized) {
      metrics[key] = normalized;
    }
  }

  const selected = readMetricNumber(source, [
    'selected',
    'candidate_tools_count',
    'candidateToolsCount',
    'selected_count',
    'selectedCount',
  ]);
  if (selected !== undefined && metrics.selected === undefined) {
    metrics.selected = selected;
  }

  const total = readMetricNumber(source, [
    'total',
    'all_tools_count',
    'allToolsCount',
    'total_tools_count',
    'totalToolsCount',
  ]);
  if (total !== undefined && metrics.total === undefined) {
    metrics.total = total;
  }

  const sourceCount = readMetricNumber(source, [
    'count',
    'source_count',
    'sourceCount',
    'result_count',
    'resultCount',
    'evidence_count',
    'evidenceCount',
  ]);
  if (sourceCount !== undefined && metrics.count === undefined) {
    metrics.count = sourceCount;
  }

  const running = readMetricNumber(source, [
    'running',
    'running_tool_calls',
    'runningToolCalls',
    'in_progress_tool_calls',
    'inProgressToolCalls',
  ]);
  if (running !== undefined && metrics.running === undefined) {
    metrics.running = running;
  }

  const failed = readMetricNumber(source, [
    'failed',
    'failed_tool_calls',
    'failedToolCalls',
    'error_count',
    'errored',
  ]);
  if (failed !== undefined && metrics.failed === undefined) {
    metrics.failed = failed;
  }

  const success = readMetricNumber(source, [
    'success',
    'completed_tool_calls',
    'completedToolCalls',
    'succeeded',
    'successful_tool_calls',
    'successfulToolCalls',
  ]);
  if (success !== undefined && metrics.success === undefined) {
    metrics.success = success;
  }

  if (metrics.total === undefined) {
    const normalizedTotal = normalizeNumber(metrics.tool_rounds);
    if (normalizedTotal !== undefined) {
      metrics.total = normalizedTotal;
    } else if (
      normalizeNumber(metrics.success) !== undefined ||
      normalizeNumber(metrics.failed) !== undefined ||
      normalizeNumber(metrics.running) !== undefined
    ) {
      metrics.total =
        (normalizeNumber(metrics.success) ?? 0) +
        (normalizeNumber(metrics.failed) ?? 0) +
        (normalizeNumber(metrics.running) ?? 0);
    } else if (sourceCount !== undefined) {
      metrics.total = sourceCount;
    }
  }

  const provider = readMetricText(source, [
    'provider',
    'selected_backend',
    'selectedBackend',
    'provider_name',
    'providerName',
  ]);
  if (provider && metrics.provider === undefined) {
    metrics.provider = provider;
  }

  const providerChain = readMetricTextList(source, [
    'provider_chain',
    'providerChain',
  ]);
  if (providerChain && metrics.provider_chain === undefined) {
    metrics.provider_chain = providerChain;
  }

  return Object.keys(metrics).length > 0 ? metrics : undefined;
}

function normalizeStageType(value: unknown): TurnFlowStageType {
  const normalized = normalizeOptionalString(value);
  if (normalized && TURN_STAGE_TYPES.has(normalized as TurnFlowStageType)) {
    return normalized as TurnFlowStageType;
  }
  return 'thinking';
}

function normalizeStageStatus(value: unknown): TurnFlowStageStatus {
  const normalized = normalizeOptionalString(value);
  if (normalized === 'failed') {
    return 'error';
  }
  if (
    normalized &&
    TURN_STAGE_STATUSES.has(normalized as TurnFlowStageStatus)
  ) {
    return normalized as TurnFlowStageStatus;
  }
  return 'completed';
}

function normalizeFinalStageStatus(
  value: unknown,
): TurnFlowStageStatus | undefined {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    return undefined;
  }
  if (normalized === 'failed') {
    return 'error';
  }
  if (TURN_STAGE_STATUSES.has(normalized as TurnFlowStageStatus)) {
    return normalized as TurnFlowStageStatus;
  }
  return undefined;
}

function coerceStage(
  raw: unknown,
  index: number,
): null | TurnFlowStageForDisplay {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const stage = raw as Record<string, unknown>;
  const detailLines = Array.isArray(stage.detail_lines)
    ? stage.detail_lines
    : stage.detailLines;
  const type = normalizeStageType(stage.type);
  let summary = normalizeOptionalString(stage.summary);
  let normalizedDetailLines = normalizeStringArray(detailLines);
  const startedAtMs =
    normalizeNumber(stage.started_at_ms) ?? normalizeNumber(stage.startedAtMs);
  const endedAtMs =
    normalizeNumber(stage.ended_at_ms) ?? normalizeNumber(stage.endedAtMs);
  const durationMs =
    normalizeNumber(stage.duration_ms) ?? normalizeNumber(stage.durationMs);
  if (type === 'thinking') {
    const firstDetailLine = normalizedDetailLines?.[0];
    if (!summary && firstDetailLine) {
      summary = stripMarkdownSummary(firstDetailLine);
    }
    normalizedDetailLines = undefined;
  }
  const id = normalizeOptionalString(stage.id) ?? `turn-stage-${index}`;
  return {
    id,
    type,
    status: normalizeStageStatus(stage.status),
    title: normalizeOptionalString(stage.title),
    summary,
    detailLines: normalizedDetailLines,
    startedAtMs,
    endedAtMs,
    durationMs,
    metrics: normalizeMetrics(stage.metrics),
    toolCallIds: normalizeStringArray(stage.tool_call_ids ?? stage.toolCallIds),
    sourceRefs: normalizeStringArray(stage.source_refs ?? stage.sourceRefs),
  };
}

function normalizeEvidenceKind(value: unknown): TurnEvidenceItem['kind'] {
  const normalized = normalizeOptionalString(value);
  if (
    normalized === 'web' ||
    normalized === 'knowledge_base' ||
    normalized === 'tool' ||
    normalized === 'page' ||
    normalized === 'memory'
  ) {
    return normalized;
  }
  return 'tool';
}

function coerceEvidence(raw: unknown, index: number): null | TurnEvidenceItem {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const evidence = raw as Record<string, unknown>;
  const id = normalizeOptionalString(evidence.id) ?? `turn-evidence-${index}`;
  const title =
    normalizeOptionalString(evidence.title) ??
    normalizeOptionalString(evidence.url) ??
    `Evidence ${index + 1}`;
  return {
    id,
    kind: normalizeEvidenceKind(evidence.kind),
    title,
    url: normalizeOptionalString(evidence.url),
    snippet: normalizeOptionalString(evidence.snippet),
    badge: normalizeOptionalString(evidence.badge),
    score: typeof evidence.score === 'number' ? evidence.score : undefined,
    toolCallId: normalizeOptionalString(
      evidence.tool_call_id ?? evidence.toolCallId,
    ),
    sourceRef: normalizeOptionalString(
      evidence.source_ref ?? evidence.sourceRef,
    ),
  };
}

function coerceAnswerCard(raw: unknown): TurnAnswerCard | undefined {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return undefined;
  }
  const card = raw as Record<string, unknown>;
  const sectionsRaw = Array.isArray(card.sections) ? card.sections : [];
  const sections = sectionsRaw
    .map((section): null | TurnAnswerCardSection => {
      if (!section || typeof section !== 'object' || Array.isArray(section)) {
        return null;
      }
      const sectionRecord = section as Record<string, unknown>;
      const title = normalizeOptionalString(sectionRecord.title);
      const content = normalizeOptionalString(sectionRecord.content);
      const body = normalizeOptionalString(sectionRecord.body) ?? content;
      const id =
        normalizeOptionalString(sectionRecord.id) ??
        `turn-answer-card-section-${sectionsRaw.indexOf(section) + 1}`;
      if (!title || !body) {
        return null;
      }
      return {
        body,
        content: body,
        id,
        title,
      };
    })
    .filter((section): section is TurnAnswerCardSection => section !== null);
  const summary = normalizeOptionalString(card.summary);
  const sourceChipIds = normalizeStringArray(
    card.source_chip_ids ?? card.sourceChipIds,
  );
  const confidenceLabel = normalizeOptionalString(
    card.confidence_label ?? card.confidenceLabel,
  );
  const followUpSuggestions = normalizeStringArray(
    card.follow_up_suggestions ?? card.followUpSuggestions,
  );
  if (
    !summary &&
    sections.length === 0 &&
    !sourceChipIds &&
    !confidenceLabel &&
    !followUpSuggestions
  ) {
    return undefined;
  }
  return {
    summary,
    sections,
    sourceChipIds,
    confidenceLabel,
    followUpSuggestions,
  };
}

function normalizeErrorSurface(
  value: unknown,
): TurnFlowErrorSurface | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined;
  }
  const record = value as Record<string, unknown>;
  const message = normalizeOptionalString(record.message);
  const summary = normalizeOptionalString(record.summary);
  const detail = normalizeOptionalString(record.detail);
  const error = normalizeOptionalString(record.error);
  const reason = normalizeOptionalString(record.reason);
  const debugMessage =
    normalizeOptionalString(record.debug_message) ??
    normalizeOptionalString(record.debugMessage);
  const traceId =
    normalizeOptionalString(record.trace_id) ??
    normalizeOptionalString(record.traceId);
  const errorType =
    normalizeOptionalString(record.error_type) ??
    normalizeOptionalString(record.errorType);
  if (
    !message &&
    !summary &&
    !detail &&
    !error &&
    !reason &&
    !debugMessage &&
    !traceId &&
    !errorType
  ) {
    return undefined;
  }
  return {
    ...(message ? { message } : {}),
    ...(summary ? { summary } : {}),
    ...(detail ? { detail } : {}),
    ...(error ? { error } : {}),
    ...(reason ? { reason } : {}),
    ...(debugMessage ? { debugMessage } : {}),
    ...(traceId ? { traceId } : {}),
    ...(errorType ? { errorType } : {}),
  };
}

function extractErrorSurfaceMessage(
  surface: TurnFlowErrorSurface | undefined,
): string | undefined {
  if (!surface) {
    return undefined;
  }
  return (
    normalizeOptionalString(surface.message) ??
    normalizeOptionalString(surface.summary) ??
    normalizeOptionalString(surface.detail) ??
    normalizeOptionalString(surface.error) ??
    normalizeOptionalString(surface.reason)
  );
}

function isFailureCompletionReason(reason: string | undefined) {
  if (!reason) {
    return false;
  }
  return FAILURE_COMPLETION_REASONS.has(reason.toLowerCase());
}

function normalizeRawTurnFlow(raw: unknown): null | TurnFlowForDisplay {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const flow = raw as Record<string, unknown>;
  const timelineSource = Array.isArray(flow.timeline) ? flow.timeline : [];
  const timeline = timelineSource
    .map((stage, index) => coerceStage(stage, index))
    .filter((stage): stage is TurnFlowStageForDisplay => stage !== null);
  const evidenceSource = Array.isArray(flow.evidence) ? flow.evidence : [];
  const evidence = evidenceSource
    .map((item, index) => coerceEvidence(item, index))
    .filter((item): item is TurnEvidenceItem => item !== null);
  const answerCard = coerceAnswerCard(flow.answer_card ?? flow.answerCard);
  const errorSurface = normalizeErrorSurface(
    flow.error_surface ?? flow.errorSurface,
  );
  const turnFlowComplete =
    normalizeBoolean(flow.turn_flow_complete) ??
    normalizeBoolean(flow.turnFlowComplete);
  return {
    timeline,
    evidence,
    answerCard,
    completionReason: normalizeOptionalString(
      flow.completion_reason ?? flow.completionReason,
    ),
    failureKind: normalizeOptionalString(flow.failure_kind ?? flow.failureKind),
    finalStageStatus: normalizeFinalStageStatus(
      flow.final_stage_status ?? flow.finalStageStatus,
    ),
    interrupted:
      typeof flow.interrupted === 'boolean' ? flow.interrupted : undefined,
    errorSurface,
    turnFlowComplete,
    turnOutcome: normalizeOptionalString(flow.turn_outcome ?? flow.turnOutcome),
  };
}

function stripMarkdownSummary(content: string, maxLength = 120) {
  const plain = content
    .replaceAll(/[`*_>#-]/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim();
  if (!plain) {
    return undefined;
  }
  if (plain.length <= maxLength) {
    return plain;
  }
  return `${plain.slice(0, maxLength - 1)}…`;
}

function cloneStage(stage: TurnFlowStageForDisplay): TurnFlowStageForDisplay {
  return {
    ...stage,
    detailLines: stage.detailLines ? [...stage.detailLines] : undefined,
    metrics: stage.metrics ? { ...stage.metrics } : undefined,
    sourceRefs: stage.sourceRefs ? [...stage.sourceRefs] : undefined,
    toolCallIds: stage.toolCallIds ? [...stage.toolCallIds] : undefined,
  };
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
    extractErrorSurfaceMessage(flow.errorSurface) ??
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
    const stage = timeline[terminalStageIndex];
    if (stage) {
      timeline[terminalStageIndex] = {
        ...stage,
        status: 'error',
        summary: summary ?? stage.summary,
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

function supplementSkippedSelectionStage(
  timeline: TurnFlowStageForDisplay[],
  msg: ChatMessage,
) {
  if (timeline.some((stage) => stage.type === 'tool_selection')) {
    return;
  }
  if (!msg.optimizingTools) {
    return;
  }
  const selected = Number(msg.optimizingTools.selected ?? 0);
  const total = Number(msg.optimizingTools.total ?? 0);
  if (
    !Number.isFinite(selected) ||
    !Number.isFinite(total) ||
    selected > 0 ||
    total <= 0
  ) {
    return;
  }
  const stage: TurnFlowStageForDisplay = {
    id: 'legacy-tool-selection-skipped',
    legacySource: 'legacy-tool-selection',
    metrics: {
      selected,
      total,
    },
    status: 'skipped',
    type: 'tool_selection',
  };

  const insertionIndex = timeline.findIndex(
    (item) =>
      item.type === 'tool_execution' ||
      item.type === 'retrieval' ||
      item.type === 'answer_assembly' ||
      TERMINAL_STAGE_TYPES.has(item.type),
  );
  if (insertionIndex === -1) {
    timeline.push(stage);
    return;
  }
  timeline.splice(insertionIndex, 0, stage);
}

function normalizeCanonicalTurnFlow(
  flow: TurnFlowForDisplay,
  msg: ChatMessage,
): TurnFlowForDisplay {
  const timeline = flow.timeline.map((stage) => cloneStage(stage));
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

  supplementSkippedSelectionStage(timeline, msg);

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

function toDisplayRagSourcesFromCanonicalFlow(
  msg: ChatMessage,
): RagSource[] | undefined {
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  if (!flow) {
    return undefined;
  }
  const ragSources = flow.evidence
    .filter((item) => item.kind === 'knowledge_base' || item.kind === 'web')
    .map((item, index) => ({
      doc_id: index + 1,
      doc_name: item.title || item.sourceRef || `Source ${index + 1}`,
      score:
        typeof item.score === 'number' && Number.isFinite(item.score)
          ? item.score
          : 0,
      snippet: item.snippet || '',
      source_kind:
        item.kind === 'knowledge_base'
          ? ('formal_kb' as const)
          : ('ephemeral_doc' as const),
    }));
  return ragSources.length > 0 ? ragSources : undefined;
}

function toDisplayToolCallsFromCanonicalFlow(
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
      name: item.title || `tool_${index + 1}`,
      status: 'success' as const,
      ...(item.snippet ? { summary: item.snippet } : {}),
      ...(item.url ? { resultLink: item.url } : {}),
    }));
  return toolCalls.length > 0 ? toolCalls : undefined;
}

export function getThinkingContentForDisplay(
  msg: ChatMessage,
): string | undefined {
  const directThinking = normalizeOptionalString(msg.thinkingContent);
  if (directThinking) {
    return directThinking;
  }
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  const thinkingStage = flow?.timeline.findLast(
    (stage) => stage.type === 'thinking',
  );
  if (!thinkingStage) {
    return undefined;
  }
  const detailText = (thinkingStage.detailLines ?? [])
    .map((line) => normalizeOptionalString(line))
    .filter((line): line is string => !!line)
    .join('\n\n');
  if (detailText) {
    return detailText;
  }
  return normalizeOptionalString(thinkingStage.summary);
}

export function getOptimizingToolsForDisplay(
  msg: ChatMessage,
): ChatMessage['optimizingTools'] | undefined {
  if (msg.optimizingTools) {
    return msg.optimizingTools;
  }
  const flow = normalizeTurnFlowViewModel(msg.turnFlow);
  const selectionStage = flow?.timeline.findLast(
    (stage) => stage.type === 'tool_selection',
  );
  const selected = normalizeNumber(selectionStage?.metrics?.selected);
  const total = normalizeNumber(selectionStage?.metrics?.total);
  if (selected === undefined && total === undefined) {
    return undefined;
  }
  return {
    selected: selected ?? 0,
    total: total ?? selected ?? 0,
  };
}

export function getToolCallsForDisplay(
  msg: ChatMessage,
): ToolCallEvent[] | undefined {
  if (msg.toolCalls?.length) {
    return msg.toolCalls;
  }
  return toDisplayToolCallsFromCanonicalFlow(msg);
}

export function getRagSourcesForDisplay(
  msg: ChatMessage,
): RagSource[] | undefined {
  if (msg.ragSources?.length) {
    return msg.ragSources;
  }
  return toDisplayRagSourcesFromCanonicalFlow(msg);
}

export function getTurnFlowForDisplay(msg: ChatMessage): TurnFlowForDisplay {
  const rawTurnFlow = normalizeRawTurnFlow(msg.turnFlow);
  if (rawTurnFlow) {
    return normalizeCanonicalTurnFlow(rawTurnFlow, msg);
  }
  return createEmptyTurnFlowForDisplay(msg);
}
