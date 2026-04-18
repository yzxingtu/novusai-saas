import type {
  ChatMessage,
  RagSource,
  ToolCallEvent,
  TurnFlowAnswerCard,
  TurnFlowAnswerCardSection,
  TurnFlowErrorSurface,
  TurnFlowEvidenceItem,
  TurnFlowEvidenceKind,
  TurnFlowStage,
  TurnFlowStageStatus,
  TurnFlowStageType,
  TurnFlowViewModel,
} from './types';

import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

import {
  normalizeObjectRecord,
  normalizeObjectRecordList,
  normalizeOptionalString,
  normalizeStringList,
} from './use-ai-chat-message-normalizers';

const TURN_FLOW_STAGE_TYPE_SET = new Set<TurnFlowStageType>([
  'answer_assembly',
  'completed',
  'failed',
  'retrieval',
  'thinking',
  'tool_execution',
  'tool_selection',
]);

const TURN_FLOW_STAGE_STATUS_SET = new Set<TurnFlowStageStatus>([
  'completed',
  'error',
  'interrupted',
  'running',
  'skipped',
]);

const TURN_FLOW_EVIDENCE_KIND_SET = new Set<TurnFlowEvidenceKind>([
  'knowledge_base',
  'memory',
  'page',
  'tool',
  'web',
]);

const FAILURE_REASON_SET = new Set([
  'error',
  'failed',
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'tool_error',
  'tool_round_failed',
]);

const FAILURE_OUTCOME_SET = new Set(['error', 'failed', 'tool_round_failed']);

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

function normalizeBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') {
    return value;
  }
  return undefined;
}

function normalizeMetricsRecord(
  value: unknown,
): Record<string, number | string> | undefined {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  const metrics: Record<string, number | string> = {};
  for (const [key, rawValue] of Object.entries(record)) {
    if (typeof rawValue === 'number' && Number.isFinite(rawValue)) {
      metrics[key] = rawValue;
      continue;
    }
    const normalized = normalizeOptionalString(rawValue);
    if (normalized) {
      metrics[key] = normalized;
    }
  }
  return Object.keys(metrics).length > 0 ? metrics : undefined;
}

function normalizeStageType(value: unknown): TurnFlowStageType {
  const normalized = normalizeOptionalString(value);
  if (
    normalized &&
    TURN_FLOW_STAGE_TYPE_SET.has(normalized as TurnFlowStageType)
  ) {
    return normalized as TurnFlowStageType;
  }
  return 'thinking';
}

function normalizeStageStatus(
  value: unknown,
  fallback: TurnFlowStageStatus = 'completed',
): TurnFlowStageStatus {
  const normalized = normalizeOptionalString(value);
  if (
    normalized &&
    TURN_FLOW_STAGE_STATUS_SET.has(normalized as TurnFlowStageStatus)
  ) {
    return normalized as TurnFlowStageStatus;
  }
  if (normalized === 'failed') {
    return 'error';
  }
  return fallback;
}

function normalizeEvidenceKind(value: unknown): TurnFlowEvidenceKind {
  const normalized = normalizeOptionalString(value);
  if (
    normalized &&
    TURN_FLOW_EVIDENCE_KIND_SET.has(normalized as TurnFlowEvidenceKind)
  ) {
    return normalized as TurnFlowEvidenceKind;
  }
  if (normalized === 'kb') {
    return 'knowledge_base';
  }
  return 'tool';
}

function normalizeStageDetailLines(record: Record<string, unknown>): string[] {
  const detailLines = normalizeStringList(
    record.detail_lines ?? record.detailLines ?? record.details,
  );
  if (detailLines.length > 0) {
    return detailLines;
  }
  const singleDetail = normalizeOptionalString(record.detail);
  if (singleDetail) {
    return [singleDetail];
  }
  return [];
}

function normalizeStage(
  record: Record<string, unknown>,
  index: number,
): TurnFlowStage {
  const id =
    normalizeOptionalString(record.id) ??
    normalizeOptionalString(record.stage_id) ??
    `stage-${index + 1}`;
  const type = normalizeStageType(record.type ?? record.stage_type);
  const startedAtMs = normalizeNumber(
    record.started_at_ms ?? record.startedAtMs,
  );
  const endedAtMs = normalizeNumber(record.ended_at_ms ?? record.endedAtMs);
  const durationMs =
    normalizeNumber(record.duration_ms ?? record.durationMs) ??
    (startedAtMs !== undefined && endedAtMs !== undefined
      ? Math.max(0, endedAtMs - startedAtMs)
      : undefined);
  const summary = normalizeOptionalString(record.summary);
  const title = normalizeOptionalString(record.title);
  const metrics = normalizeMetricsRecord(record.metrics);
  const detailLines = normalizeStageDetailLines(record);
  const toolCallIds = normalizeStringList(
    record.tool_call_ids ?? record.toolCallIds,
  );
  const sourceRefs = normalizeStringList(
    record.source_refs ?? record.sourceRefs,
  );
  return {
    id,
    type,
    status: normalizeStageStatus(record.status),
    ...(title ? { title } : {}),
    ...(summary ? { summary } : {}),
    ...(detailLines.length > 0 ? { detailLines } : {}),
    ...(startedAtMs === undefined ? {} : { startedAtMs }),
    ...(endedAtMs === undefined ? {} : { endedAtMs }),
    ...(durationMs === undefined ? {} : { durationMs }),
    ...(metrics ? { metrics } : {}),
    ...(toolCallIds.length > 0 ? { toolCallIds } : {}),
    ...(sourceRefs.length > 0 ? { sourceRefs } : {}),
  };
}

function normalizeEvidence(
  record: Record<string, unknown>,
  index: number,
): TurnFlowEvidenceItem {
  const id =
    normalizeOptionalString(record.id) ??
    normalizeOptionalString(record.source_ref) ??
    `evidence-${index + 1}`;
  const title = normalizeOptionalString(record.title);
  const url = normalizeOptionalString(record.url);
  const snippet =
    normalizeOptionalString(record.snippet) ??
    normalizeOptionalString(record.summary);
  const badge = normalizeOptionalString(record.badge);
  const sourceRef =
    normalizeOptionalString(record.source_ref) ??
    normalizeOptionalString(record.sourceRef);
  const toolCallId =
    normalizeOptionalString(record.tool_call_id) ??
    normalizeOptionalString(record.toolCallId);
  const score = normalizeNumber(record.score);
  return {
    id,
    kind: normalizeEvidenceKind(record.kind),
    ...(title ? { title } : {}),
    ...(url ? { url } : {}),
    ...(snippet ? { snippet } : {}),
    ...(badge ? { badge } : {}),
    ...(score === undefined ? {} : { score }),
    ...(toolCallId ? { toolCallId } : {}),
    ...(sourceRef ? { sourceRef } : {}),
  };
}

function normalizeAnswerCardSection(
  value: unknown,
  index: number,
): null | TurnFlowAnswerCardSection {
  if (typeof value === 'string') {
    const body = normalizeOptionalString(value);
    if (!body) {
      return null;
    }
    return {
      body,
      id: `section-${index + 1}`,
    };
  }
  const record = normalizeObjectRecord(value);
  if (!record) {
    return null;
  }
  const id = normalizeOptionalString(record.id) ?? `section-${index + 1}`;
  const title = normalizeOptionalString(record.title);
  const body = normalizeOptionalString(record.body ?? record.content);
  const bullets = normalizeStringList(record.bullets);
  if (!title && !body && bullets.length === 0) {
    return null;
  }
  return {
    id,
    ...(title ? { title } : {}),
    ...(body ? { body } : {}),
    ...(bullets.length > 0 ? { bullets } : {}),
  };
}

function normalizeAnswerCard(value: unknown): TurnFlowAnswerCard | undefined {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  const summary = normalizeOptionalString(record.summary);
  const confidenceLabel =
    normalizeOptionalString(record.confidence_label) ??
    normalizeOptionalString(record.confidenceLabel);
  const sourceChipIds = normalizeStringList(
    record.source_chip_ids ?? record.sourceChipIds,
  );
  const followUpSuggestions = normalizeStringList(
    record.follow_up_suggestions ?? record.followUpSuggestions,
  );
  const sectionsRaw = Array.isArray(record.sections) ? record.sections : [];
  const sections = sectionsRaw
    .map((section, index) => normalizeAnswerCardSection(section, index))
    .filter((section): section is TurnFlowAnswerCardSection => !!section);
  if (
    !summary &&
    !confidenceLabel &&
    sourceChipIds.length === 0 &&
    followUpSuggestions.length === 0 &&
    sections.length === 0
  ) {
    return undefined;
  }
  return {
    ...(summary ? { summary } : {}),
    ...(sections.length > 0 ? { sections } : {}),
    ...(sourceChipIds.length > 0 ? { sourceChipIds } : {}),
    ...(confidenceLabel ? { confidenceLabel } : {}),
    ...(followUpSuggestions.length > 0 ? { followUpSuggestions } : {}),
  };
}

function normalizeErrorSurface(
  value: unknown,
): TurnFlowErrorSurface | undefined {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
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

function hasTurnFlowData(value?: TurnFlowViewModel): boolean {
  if (!value) {
    return false;
  }
  return (
    value.timeline.length > 0 ||
    value.evidence.length > 0 ||
    !!value.answerCard ||
    !!value.completionReason ||
    !!value.errorSurface ||
    value.interrupted === true ||
    value.complete === true
  );
}

function cloneStage(stage: TurnFlowStage): TurnFlowStage {
  return {
    ...stage,
    ...(stage.metrics ? { metrics: { ...stage.metrics } } : {}),
    ...(stage.detailLines ? { detailLines: [...stage.detailLines] } : {}),
    ...(stage.sourceRefs ? { sourceRefs: [...stage.sourceRefs] } : {}),
    ...(stage.toolCallIds ? { toolCallIds: [...stage.toolCallIds] } : {}),
  };
}

function cloneEvidence(evidence: TurnFlowEvidenceItem): TurnFlowEvidenceItem {
  return { ...evidence };
}

function cloneAnswerCard(
  answerCard?: TurnFlowAnswerCard,
): TurnFlowAnswerCard | undefined {
  if (!answerCard) {
    return undefined;
  }
  return {
    ...answerCard,
    ...(answerCard.sourceChipIds
      ? { sourceChipIds: [...answerCard.sourceChipIds] }
      : {}),
    ...(answerCard.followUpSuggestions
      ? { followUpSuggestions: [...answerCard.followUpSuggestions] }
      : {}),
    ...(answerCard.sections
      ? {
          sections: answerCard.sections.map((section) => ({
            ...section,
            ...(section.bullets ? { bullets: [...section.bullets] } : {}),
          })),
        }
      : {}),
  };
}

function cloneTurnFlow(flow: TurnFlowViewModel): TurnFlowViewModel {
  return {
    ...flow,
    timeline: flow.timeline.map((stage) => cloneStage(stage)),
    evidence: flow.evidence.map((evidence) => cloneEvidence(evidence)),
    ...(flow.answerCard
      ? { answerCard: cloneAnswerCard(flow.answerCard) }
      : {}),
    ...(flow.errorSurface ? { errorSurface: { ...flow.errorSurface } } : {}),
  };
}

function mergeStage(
  base: TurnFlowStage,
  incoming: TurnFlowStage,
): TurnFlowStage {
  return {
    ...base,
    ...incoming,
    ...(base.metrics || incoming.metrics
      ? { metrics: { ...base.metrics, ...incoming.metrics } }
      : {}),
    ...(base.detailLines || incoming.detailLines
      ? {
          detailLines: (() => {
            if (incoming.detailLines?.length) {
              return [...incoming.detailLines];
            }
            if (base.detailLines) {
              return [...base.detailLines];
            }
            return undefined;
          })(),
        }
      : {}),
    ...(base.sourceRefs || incoming.sourceRefs
      ? {
          sourceRefs: (() => {
            if (incoming.sourceRefs?.length) {
              return [...incoming.sourceRefs];
            }
            if (base.sourceRefs) {
              return [...base.sourceRefs];
            }
            return undefined;
          })(),
        }
      : {}),
    ...(base.toolCallIds || incoming.toolCallIds
      ? {
          toolCallIds: (() => {
            if (incoming.toolCallIds?.length) {
              return [...incoming.toolCallIds];
            }
            if (base.toolCallIds) {
              return [...base.toolCallIds];
            }
            return undefined;
          })(),
        }
      : {}),
  };
}

function upsertStage(flow: TurnFlowViewModel, stage: TurnFlowStage): void {
  const index = flow.timeline.findIndex((item) => item.id === stage.id);
  if (index === -1) {
    flow.timeline.push(stage);
    return;
  }
  const previous = flow.timeline[index];
  if (!previous) {
    flow.timeline.push(stage);
    return;
  }
  flow.timeline[index] = mergeStage(previous, stage);
}

function upsertEvidence(
  flow: TurnFlowViewModel,
  evidence: TurnFlowEvidenceItem,
): void {
  const index = flow.evidence.findIndex((item) => item.id === evidence.id);
  if (index === -1) {
    flow.evidence.push(evidence);
    return;
  }
  const previous = flow.evidence[index];
  if (!previous) {
    flow.evidence.push(evidence);
    return;
  }
  flow.evidence[index] = { ...previous, ...evidence };
}

function toErrorSurface(
  error?: AppErrorInfo,
): TurnFlowErrorSurface | undefined {
  if (!error) {
    return undefined;
  }
  const message = normalizeOptionalString(error.message);
  const debugMessage = normalizeOptionalString(error.debugMessage);
  const traceId = normalizeOptionalString(error.traceId);
  const errorType = normalizeOptionalString(error.code);
  if (!message && !debugMessage && !traceId && !errorType) {
    return undefined;
  }
  return {
    ...(message ? { message } : {}),
    ...(debugMessage ? { debugMessage } : {}),
    ...(traceId ? { traceId } : {}),
    ...(errorType ? { errorType } : {}),
  };
}

function normalizeFailureSignal(value: unknown): string | undefined {
  return normalizeOptionalString(value);
}

function isFailureSignal(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  if (FAILURE_REASON_SET.has(value)) {
    return true;
  }
  return value.includes('error') || value.includes('failed');
}

function extractFailureKind(value: unknown): string | undefined {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  const metadata = normalizeObjectRecord(record.metadata);
  return (
    normalizeFailureSignal(record.failure_kind ?? record.failureKind) ??
    normalizeFailureSignal(metadata?.failure_kind ?? metadata?.failureKind)
  );
}

function resolveMessageFailureKind(message: ChatMessage): string | undefined {
  const messageRecord = message as unknown as Record<string, unknown>;
  return (
    normalizeFailureSignal(
      messageRecord.failure_kind ?? messageRecord.failureKind,
    ) ??
    extractFailureKind(message.turnRecord) ??
    normalizeFailureSignal(message.error?.code)
  );
}

function shouldProjectFailureFromSignals(params: {
  completionReason?: string;
  failureKind?: string;
  terminationReason?: string;
  turnOutcome?: string;
}): boolean {
  const completionReason = normalizeFailureSignal(params.completionReason);
  const terminationReason = normalizeFailureSignal(params.terminationReason);
  const turnOutcome = normalizeFailureSignal(params.turnOutcome);
  const failureKind = normalizeFailureSignal(params.failureKind);
  if (isFailureSignal(completionReason) || isFailureSignal(terminationReason)) {
    return true;
  }
  if (turnOutcome && FAILURE_OUTCOME_SET.has(turnOutcome)) {
    return true;
  }
  if (turnOutcome === 'partial' && failureKind) {
    return true;
  }
  return isFailureSignal(failureKind);
}

function summarize(text: string, maxLength = 120): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}...`;
}

function summarizeThinking(value: string): { summary: string } {
  const detailLines = value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const summary = detailLines.length > 0 ? summarize(detailLines[0] ?? '') : '';
  return {
    summary,
  };
}

function inferSelectionMetrics(
  message: ChatMessage,
): undefined | { selected: number; total: number } {
  if (message.optimizingTools) {
    const selected = normalizeNumber(message.optimizingTools.selected) ?? 0;
    const total = normalizeNumber(message.optimizingTools.total) ?? selected;
    return { selected, total };
  }
  const selectedNames = message.selectedToolNames ?? [];
  if (selectedNames.length > 0) {
    return {
      selected: selectedNames.length,
      total: selectedNames.length,
    };
  }
  return undefined;
}

function inferRetrievalFromContextSources(
  contextSources: TurnContextSourcePayload[] | undefined,
): { hasRetrieval: boolean; sourceRefs: string[] } {
  if (!Array.isArray(contextSources) || contextSources.length === 0) {
    return { hasRetrieval: false, sourceRefs: [] };
  }
  const retrievalKinds = new Set([
    'knowledge',
    'knowledge_base',
    'rag',
    'search',
    'web',
    'web_search',
  ]);
  const sourceRefs: string[] = [];
  let hasRetrieval = false;
  for (const source of contextSources) {
    const kind = normalizeOptionalString(source.kind);
    const name = normalizeOptionalString(source.name);
    if (kind && retrievalKinds.has(kind)) {
      hasRetrieval = true;
    }
    if (name) {
      sourceRefs.push(name);
    }
  }
  return { hasRetrieval, sourceRefs };
}

function buildLegacyEvidenceFromRagSources(
  ragSources: RagSource[] | undefined,
): TurnFlowEvidenceItem[] {
  if (!Array.isArray(ragSources) || ragSources.length === 0) {
    return [];
  }
  return ragSources.map((source, index) => ({
    id: `legacy-rag-${source.doc_id}-${index + 1}`,
    kind:
      source.source_kind === 'formal_kb' ? 'knowledge_base' : 'knowledge_base',
    score:
      typeof source.score === 'number' && Number.isFinite(source.score)
        ? source.score
        : undefined,
    snippet: normalizeOptionalString(source.snippet),
    sourceRef: normalizeOptionalString(source.heading) ?? source.doc_name,
    title: source.doc_name,
  }));
}

function buildLegacyEvidenceFromToolCalls(
  toolCalls: ToolCallEvent[] | undefined,
): TurnFlowEvidenceItem[] {
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
    return [];
  }
  return toolCalls
    .map((toolCall, index): null | TurnFlowEvidenceItem => {
      const title = normalizeOptionalString(
        toolCall.displayName ?? toolCall.name,
      );
      const snippet =
        normalizeOptionalString(toolCall.summary) ??
        normalizeOptionalString(toolCall.output) ??
        normalizeOptionalString(toolCall.error);
      if (!title && !snippet && !toolCall.resultLink) {
        return null;
      }
      return {
        id: toolCall.id ?? `legacy-tool-evidence-${index + 1}`,
        kind: 'tool',
        ...(title ? { title } : {}),
        ...(snippet ? { snippet } : {}),
        ...(toolCall.resultLink ? { url: toolCall.resultLink } : {}),
        ...(toolCall.id ? { toolCallId: toolCall.id } : {}),
      };
    })
    .filter((item): item is TurnFlowEvidenceItem => item !== null);
}

function inferFinalStageStatus(message: ChatMessage): TurnFlowStageStatus {
  const completionReason = normalizeOptionalString(
    message.completionReason ?? message.terminationReason,
  );
  const terminationReason = normalizeOptionalString(message.terminationReason);
  const turnOutcome = normalizeOptionalString(message.turnOutcome);
  const failureKind = resolveMessageFailureKind(message);
  if (
    message.error ||
    shouldProjectFailureFromSignals({
      completionReason,
      failureKind,
      turnOutcome,
      terminationReason,
    })
  ) {
    return 'error';
  }
  if (message.interrupted || completionReason === 'interrupted') {
    return 'interrupted';
  }
  if (message.streaming) {
    return 'running';
  }
  return 'completed';
}

function inferCompletionReason(message: ChatMessage): string | undefined {
  return normalizeOptionalString(
    message.completionReason ?? message.terminationReason,
  );
}

type TurnFlowStageSemanticType =
  | 'answer_assembly'
  | 'retrieval'
  | 'terminal'
  | 'thinking'
  | 'tool_execution'
  | 'tool_selection';

function toSemanticStageType(
  type: TurnFlowStageType,
): TurnFlowStageSemanticType {
  if (type === 'completed' || type === 'failed') {
    return 'terminal';
  }
  return type;
}

function mergeTimelineWithCanonicalPriority(
  legacyTimeline: TurnFlowStage[],
  canonicalTimeline: TurnFlowStage[],
): TurnFlowStage[] {
  if (canonicalTimeline.length === 0) {
    return legacyTimeline.map((stage) => cloneStage(stage));
  }
  const canonicalSemanticTypes = new Set<TurnFlowStageSemanticType>(
    canonicalTimeline.map((stage) => toSemanticStageType(stage.type)),
  );
  return [
    ...canonicalTimeline.map((stage) => cloneStage(stage)),
    ...legacyTimeline
      .filter(
        (stage) => !canonicalSemanticTypes.has(toSemanticStageType(stage.type)),
      )
      .map((stage) => cloneStage(stage)),
  ];
}

function toLegacyRagSourcesFromEvidence(
  evidence: TurnFlowEvidenceItem[],
): RagSource[] {
  return evidence
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
        item.kind === 'knowledge_base' ? 'formal_kb' : 'ephemeral_doc',
    }));
}

function toLegacyToolCallsFromEvidence(
  evidence: TurnFlowEvidenceItem[],
): ToolCallEvent[] {
  return evidence
    .filter((item) => item.kind === 'tool')
    .map((item, index) => ({
      id: item.toolCallId ?? `evidence-tool-${index + 1}`,
      name: item.title || `tool_${index + 1}`,
      status: 'success',
      ...(item.snippet ? { summary: item.snippet } : {}),
      ...(item.url ? { resultLink: item.url } : {}),
    }));
}

function buildLegacyTurnFlowFromMessage(
  message: ChatMessage,
): TurnFlowViewModel | undefined {
  const timeline: TurnFlowStage[] = [];
  const evidence: TurnFlowEvidenceItem[] = [];

  const thinkingContent = normalizeOptionalString(message.thinkingContent);
  if (thinkingContent) {
    const { summary } = summarizeThinking(thinkingContent);
    timeline.push({
      id: 'legacy-thinking',
      status: message.streaming && !message.content ? 'running' : 'completed',
      summary,
      title: 'Thinking',
      type: 'thinking',
    });
  }

  const selectionMetrics = inferSelectionMetrics(message);
  if (
    selectionMetrics ||
    (message.toolCalls?.length ?? 0) > 0 ||
    (message.selectedToolNames?.length ?? 0) > 0
  ) {
    const status =
      selectionMetrics &&
      selectionMetrics.total > 0 &&
      selectionMetrics.selected === 0
        ? 'skipped'
        : 'completed';
    timeline.push({
      id: 'legacy-tool-selection',
      metrics: selectionMetrics
        ? { selected: selectionMetrics.selected, total: selectionMetrics.total }
        : undefined,
      status,
      summary: selectionMetrics
        ? `Selected ${selectionMetrics.selected} of ${selectionMetrics.total} tools`
        : `Selected ${(message.selectedToolNames ?? []).length} tools`,
      title: 'Tool Selection',
      type: 'tool_selection',
    });
  }

  if ((message.toolCalls?.length ?? 0) > 0) {
    const toolCalls = message.toolCalls ?? [];
    const runningCount = toolCalls.filter(
      (toolCall) => toolCall.status === 'running',
    ).length;
    const errorCount = toolCalls.filter(
      (toolCall) => toolCall.status === 'error',
    ).length;
    let status: TurnFlowStageStatus = 'completed';
    if (runningCount > 0) {
      status = 'running';
    } else if (errorCount > 0) {
      status = 'error';
    }
    timeline.push({
      id: 'legacy-tool-execution',
      metrics: {
        errored: errorCount,
        running: runningCount,
        total: toolCalls.length,
      },
      status,
      summary: `${toolCalls.length} tool call(s)`,
      title: 'Tool Execution',
      toolCallIds: toolCalls
        .map((toolCall) => normalizeOptionalString(toolCall.id))
        .filter((id): id is string => !!id),
      type: 'tool_execution',
    });
    evidence.push(...buildLegacyEvidenceFromToolCalls(toolCalls));
  }

  if ((message.ragSources?.length ?? 0) > 0) {
    timeline.push({
      id: 'legacy-retrieval',
      metrics: { sourceCount: message.ragSources?.length ?? 0 },
      status: 'completed',
      summary: `Collected ${message.ragSources?.length ?? 0} source(s)`,
      title: 'Retrieval',
      type: 'retrieval',
    });
    evidence.push(...buildLegacyEvidenceFromRagSources(message.ragSources));
  } else {
    const retrievalInference = inferRetrievalFromContextSources(
      message.contextSources,
    );
    if (retrievalInference.hasRetrieval) {
      timeline.push({
        id: 'legacy-retrieval',
        sourceRefs:
          retrievalInference.sourceRefs.length > 0
            ? retrievalInference.sourceRefs
            : undefined,
        status: 'completed',
        summary: 'Retrieved context sources',
        title: 'Retrieval',
        type: 'retrieval',
      });
    }
  }

  if (normalizeOptionalString(message.content) || message.error) {
    timeline.push({
      id: 'legacy-answer-assembly',
      status: message.streaming ? 'running' : inferFinalStageStatus(message),
      summary: message.error
        ? (normalizeOptionalString(message.error.message) ?? 'Response failed')
        : summarize(message.content),
      title: 'Answer Assembly',
      type: 'answer_assembly',
    });
  }

  const finalStatus = inferFinalStageStatus(message);
  const completionReason = inferCompletionReason(message);
  if (
    completionReason ||
    finalStatus !== 'running' ||
    message.error ||
    message.interrupted
  ) {
    timeline.push({
      id: 'legacy-final',
      status: finalStatus,
      summary: completionReason,
      title: finalStatus === 'error' ? 'Failed' : 'Completed',
      type: finalStatus === 'error' ? 'failed' : 'completed',
    });
  }

  const answerCard = normalizeAnswerCard(
    normalizeObjectRecord(message.turnFlow?.answerCard) ?? null,
  );
  const errorSurface = toErrorSurface(message.error);
  const legacyFlow: TurnFlowViewModel = {
    answerCard,
    complete: !message.streaming,
    completionReason,
    evidence,
    finalStageStatus: finalStatus,
    interrupted: message.interrupted === true || finalStatus === 'interrupted',
    timeline,
    ...(errorSurface ? { errorSurface } : {}),
  };
  return hasTurnFlowData(legacyFlow) ? legacyFlow : undefined;
}

export function createEmptyTurnFlow(): TurnFlowViewModel {
  return {
    evidence: [],
    timeline: [],
  };
}

export function normalizeTurnFlowViewModel(
  value: unknown,
): TurnFlowViewModel | undefined {
  if (!value) {
    return undefined;
  }
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  const timelineRaw = Array.isArray(record.timeline)
    ? record.timeline
    : (() => {
        if (Array.isArray(record.stages)) {
          return record.stages;
        }
        return [];
      })();
  const evidenceRaw = Array.isArray(record.evidence)
    ? record.evidence
    : (() => {
        if (Array.isArray(record.sources)) {
          return record.sources;
        }
        return [];
      })();
  const timeline = normalizeObjectRecordList(timelineRaw).map((item, index) =>
    normalizeStage(item, index),
  );
  const evidence = normalizeObjectRecordList(evidenceRaw).map((item, index) =>
    normalizeEvidence(item, index),
  );
  const answerCard = normalizeAnswerCard(
    record.answer_card ?? record.answerCard,
  );
  const completionReason =
    normalizeOptionalString(record.completion_reason) ??
    normalizeOptionalString(record.completionReason);
  const hasExplicitFinalStageStatus =
    record.final_stage_status !== undefined ||
    record.finalStageStatus !== undefined;
  const finalStageStatus = hasExplicitFinalStageStatus
    ? normalizeStageStatus(
        record.final_stage_status ?? record.finalStageStatus,
        'completed',
      )
    : undefined;
  const interrupted =
    normalizeBoolean(record.interrupted) ?? completionReason === 'interrupted';
  const complete = normalizeBoolean(
    record.turn_flow_complete ?? record.complete,
  );
  const traceId =
    normalizeOptionalString(record.trace_id) ??
    normalizeOptionalString(record.traceId);
  const errorSurface = normalizeErrorSurface(
    record.error_surface ?? record.errorSurface,
  );
  const normalized: TurnFlowViewModel = {
    evidence,
    timeline,
    ...(answerCard ? { answerCard } : {}),
    ...(completionReason ? { completionReason } : {}),
    ...(complete === undefined ? {} : { complete }),
    ...(traceId ? { traceId } : {}),
    ...(errorSurface ? { errorSurface } : {}),
    ...(interrupted ? { interrupted } : {}),
    ...(finalStageStatus === undefined ? {} : { finalStageStatus }),
  };
  return hasTurnFlowData(normalized) ? normalized : undefined;
}

export function mergeTurnFlow(
  base?: TurnFlowViewModel,
  incoming?: TurnFlowViewModel,
): TurnFlowViewModel | undefined {
  if (!base && !incoming) {
    return undefined;
  }
  if (!base) {
    return incoming ? cloneTurnFlow(incoming) : undefined;
  }
  if (!incoming) {
    return cloneTurnFlow(base);
  }
  const merged = cloneTurnFlow(base);
  for (const stage of incoming.timeline) {
    upsertStage(merged, cloneStage(stage));
  }
  for (const evidence of incoming.evidence) {
    upsertEvidence(merged, cloneEvidence(evidence));
  }
  if (incoming.answerCard) {
    merged.answerCard = cloneAnswerCard(incoming.answerCard);
  }
  if (incoming.completionReason) {
    merged.completionReason = incoming.completionReason;
  }
  if (incoming.complete !== undefined) {
    merged.complete = incoming.complete;
  }
  if (incoming.interrupted !== undefined) {
    merged.interrupted = incoming.interrupted;
  }
  if (incoming.finalStageStatus) {
    merged.finalStageStatus = incoming.finalStageStatus;
  }
  if (incoming.traceId) {
    merged.traceId = incoming.traceId;
  }
  if (incoming.errorSurface) {
    merged.errorSurface = {
      ...merged.errorSurface,
      ...incoming.errorSurface,
    };
  }
  return merged;
}

export function applyLegacyFieldsFromTurnFlow(message: ChatMessage): void {
  const flow = normalizeTurnFlowViewModel(message.turnFlow);
  if (!flow) {
    return;
  }
  const thinkingStage = flow.timeline.find(
    (stage) => stage.type === 'thinking',
  );
  if (!message.thinkingContent && thinkingStage) {
    const summary = normalizeOptionalString(thinkingStage.summary);
    if (summary) {
      message.thinkingContent = summarize(summary, 240);
    }
  }

  if (!message.optimizingTools) {
    const selectionStage = flow.timeline.find(
      (stage) => stage.type === 'tool_selection',
    );
    const metrics = selectionStage?.metrics;
    const selected = normalizeNumber(metrics?.selected);
    const total = normalizeNumber(metrics?.total);
    if (selected !== undefined || total !== undefined) {
      message.optimizingTools = {
        selected: selected ?? 0,
        total: total ?? selected ?? 0,
      };
    }
  }

  if (!message.ragSources || message.ragSources.length === 0) {
    const legacyRagSources = toLegacyRagSourcesFromEvidence(flow.evidence);
    if (legacyRagSources.length > 0) {
      message.ragSources = legacyRagSources;
    }
  }

  if (!message.toolCalls || message.toolCalls.length === 0) {
    const legacyToolCalls = toLegacyToolCallsFromEvidence(flow.evidence);
    if (legacyToolCalls.length > 0) {
      message.toolCalls = legacyToolCalls;
    }
  }
}

function shouldFinalizeTimeline(flow: TurnFlowViewModel): boolean {
  if (flow.complete === true) {
    return true;
  }
  if (flow.finalStageStatus && flow.finalStageStatus !== 'running') {
    return true;
  }
  return flow.timeline.some(
    (stage) => stage.type === 'completed' || stage.type === 'failed',
  );
}

export function reconcileTurnFlowWithLegacy(message: ChatMessage): void {
  const normalizedTurnFlow = normalizeTurnFlowViewModel(message.turnFlow);
  const legacyTurnFlow = buildLegacyTurnFlowFromMessage(message);
  const merged = mergeTurnFlow(legacyTurnFlow, normalizedTurnFlow);
  if (!merged) {
    return;
  }
  merged.timeline = mergeTimelineWithCanonicalPriority(
    legacyTurnFlow?.timeline ?? [],
    normalizedTurnFlow?.timeline ?? [],
  );
  if (shouldFinalizeTimeline(merged)) {
    const finalStatus =
      merged.finalStageStatus && merged.finalStageStatus !== 'running'
        ? merged.finalStageStatus
        : inferFinalStageStatus(message);
    merged.finalStageStatus = finalStatus;
    if (normalizedTurnFlow?.complete !== undefined) {
      merged.complete = normalizedTurnFlow.complete;
    } else if (merged.complete === undefined) {
      merged.complete = true;
    }
    finalizeRunningStages(merged, finalStatus);
    ensureTerminalStage(merged);
  }
  message.turnFlow = merged;
  applyLegacyFieldsFromTurnFlow(message);
}

function buildStageFromCanonicalEvent(
  event: Record<string, unknown>,
): TurnFlowStage | undefined {
  const stageRecord =
    normalizeObjectRecord(event.stage) ??
    normalizeObjectRecord(event.stage_payload) ??
    normalizeObjectRecord(event.data);
  const candidate = {
    ...event,
    ...stageRecord,
  };
  const normalizedCandidate = normalizeObjectRecord(candidate);
  if (!normalizedCandidate) {
    return undefined;
  }
  return normalizeStage(normalizedCandidate, 0);
}

function buildEvidenceFromCanonicalEvent(
  event: Record<string, unknown>,
): TurnFlowEvidenceItem | undefined {
  const evidenceRecord =
    normalizeObjectRecord(event.evidence) ??
    normalizeObjectRecord(event.item) ??
    normalizeObjectRecord(event.data);
  const candidate = {
    ...event,
    ...evidenceRecord,
  };
  const normalizedCandidate = normalizeObjectRecord(candidate);
  if (!normalizedCandidate) {
    return undefined;
  }
  return normalizeEvidence(normalizedCandidate, 0);
}

function stageStatusFromDone(
  event: Record<string, unknown>,
): TurnFlowStageStatus {
  const turnRecord = normalizeObjectRecord(
    event.turn_record ?? event.turnRecord,
  );
  const completionReason = normalizeFailureSignal(
    event.completion_reason ?? event.completionReason,
  );
  const terminationReason = normalizeFailureSignal(
    event.termination_reason ??
      event.terminationReason ??
      turnRecord?.termination_reason ??
      turnRecord?.terminationReason,
  );
  const turnOutcome = normalizeFailureSignal(
    event.turn_outcome ??
      event.turnOutcome ??
      turnRecord?.turn_outcome ??
      turnRecord?.turnOutcome,
  );
  const failureKind =
    normalizeFailureSignal(event.failure_kind ?? event.failureKind) ??
    extractFailureKind(turnRecord);
  if (
    shouldProjectFailureFromSignals({
      completionReason,
      failureKind,
      turnOutcome,
      terminationReason,
    })
  ) {
    return 'error';
  }
  const status = normalizeOptionalString(
    event.final_stage_status ?? event.finalStatus,
  );
  if (status === 'failed') {
    return 'error';
  }
  if (status && TURN_FLOW_STAGE_STATUS_SET.has(status as TurnFlowStageStatus)) {
    return status as TurnFlowStageStatus;
  }
  if (
    terminationReason === 'interrupted' ||
    completionReason === 'interrupted'
  ) {
    return 'interrupted';
  }
  if (completionReason === 'error') {
    return 'error';
  }
  return 'completed';
}

function finalizeRunningStages(
  flow: TurnFlowViewModel,
  finalStatus: TurnFlowStageStatus,
): void {
  for (const stage of flow.timeline) {
    if (stage.status !== 'running') {
      continue;
    }
    stage.status = finalStatus;
  }
}

function ensureTerminalStage(flow: TurnFlowViewModel): void {
  if (
    flow.timeline.some(
      (stage) => stage.type === 'completed' || stage.type === 'failed',
    )
  ) {
    return;
  }
  const finalStatus = flow.finalStageStatus ?? 'completed';
  flow.timeline.push({
    id: 'turn-final',
    status: finalStatus,
    summary: flow.completionReason,
    title: finalStatus === 'error' ? 'Failed' : 'Completed',
    type: finalStatus === 'error' ? 'failed' : 'completed',
  });
}

export function applyCanonicalTurnStageEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const stage = buildStageFromCanonicalEvent(event);
  if (!stage) {
    return;
  }
  const flow = mergeTurnFlow(
    normalizeTurnFlowViewModel(message.turnFlow),
    createEmptyTurnFlow(),
  );
  if (!flow) {
    return;
  }
  upsertStage(flow, stage);
  message.turnFlow = flow;
  applyLegacyFieldsFromTurnFlow(message);
}

export function applyCanonicalTurnEvidenceEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const evidence = buildEvidenceFromCanonicalEvent(event);
  if (!evidence) {
    return;
  }
  const flow = mergeTurnFlow(
    normalizeTurnFlowViewModel(message.turnFlow),
    createEmptyTurnFlow(),
  );
  if (!flow) {
    return;
  }
  upsertEvidence(flow, evidence);
  message.turnFlow = flow;
  applyLegacyFieldsFromTurnFlow(message);
}

export function applyCanonicalTurnAnswerCardEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const answerCard = normalizeAnswerCard(
    event.answer_card ?? event.answerCard ?? event.data,
  );
  if (!answerCard) {
    return;
  }
  const flow = mergeTurnFlow(
    normalizeTurnFlowViewModel(message.turnFlow),
    createEmptyTurnFlow(),
  );
  if (!flow) {
    return;
  }
  flow.answerCard = answerCard;
  message.turnFlow = flow;
}

export function applyCanonicalDoneEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const incomingTurnFlow = normalizeTurnFlowViewModel(
    event.turn_flow ?? event.turnFlow,
  );
  let flow = mergeTurnFlow(
    normalizeTurnFlowViewModel(message.turnFlow),
    incomingTurnFlow,
  );
  if (!flow) {
    flow = buildLegacyTurnFlowFromMessage(message) ?? createEmptyTurnFlow();
  }

  const completionReason =
    normalizeOptionalString(event.completion_reason) ??
    normalizeOptionalString(event.completionReason) ??
    normalizeOptionalString(event.termination_reason) ??
    inferCompletionReason(message);
  if (completionReason) {
    flow.completionReason = completionReason;
  }

  const finalStageStatus = stageStatusFromDone(event);
  flow.finalStageStatus = finalStageStatus;
  flow.complete = normalizeBoolean(event.turn_flow_complete) ?? true;
  flow.interrupted =
    normalizeBoolean(event.interrupted) ??
    (completionReason === 'interrupted' ||
      finalStageStatus === 'interrupted' ||
      message.interrupted === true);
  const traceId =
    normalizeOptionalString(event.trace_id) ??
    normalizeOptionalString(event.traceId);
  if (traceId) {
    flow.traceId = traceId;
  }
  if (!flow.errorSurface) {
    flow.errorSurface = toErrorSurface(message.error);
  }
  if (!message.completionReason && flow.completionReason) {
    message.completionReason = flow.completionReason;
  }
  if (finalStageStatus === 'error') {
    message.turnOutcome = message.turnOutcome || 'failed';
    message.requestFailedRetry = true;
    message.terminationReason =
      message.terminationReason || flow.completionReason || 'error';
  } else if (finalStageStatus === 'interrupted') {
    message.interrupted = true;
    message.partial = true;
    message.turnOutcome = message.turnOutcome || 'partial';
    message.terminationReason =
      message.terminationReason || flow.completionReason || 'interrupted';
  }

  finalizeRunningStages(flow, finalStageStatus);
  ensureTerminalStage(flow);
  message.turnFlow = flow;
  applyLegacyFieldsFromTurnFlow(message);
}

export function settleTurnFlowAfterLifecycleFinalize(
  message: ChatMessage,
): void {
  let flow =
    normalizeTurnFlowViewModel(message.turnFlow) ??
    buildLegacyTurnFlowFromMessage(message);
  if (!flow) {
    flow = createEmptyTurnFlow();
  }
  const completionReason = inferCompletionReason(message);
  if (completionReason) {
    flow.completionReason = completionReason;
  }
  const finalStageStatus = inferFinalStageStatus(message);
  flow.finalStageStatus = finalStageStatus;
  flow.complete = true;
  flow.interrupted =
    message.interrupted === true || finalStageStatus === 'interrupted';
  if (!flow.errorSurface) {
    flow.errorSurface = toErrorSurface(message.error);
  }
  finalizeRunningStages(flow, finalStageStatus);
  ensureTerminalStage(flow);
  message.turnFlow = flow;
  reconcileTurnFlowWithLegacy(message);
}

export function buildTurnFlowFromDiagnosticsPayload(payload: {
  completionReason?: string;
  contextSources?: TurnContextSourcePayload[];
  error?: AppErrorInfo;
  ragSources?: RagSource[];
  selectedToolNames?: string[];
  terminationReason?: string;
  toolCalls?: ToolCallEvent[];
  turnOutcome?: string;
  turnRecord?: null | TurnRecordPayload;
}): TurnFlowViewModel | undefined {
  const syntheticMessage: ChatMessage = {
    clientKey: 'synthetic-turn-flow',
    content: '',
    role: 'assistant',
    ...(payload.completionReason
      ? { completionReason: payload.completionReason }
      : {}),
    ...(payload.contextSources
      ? { contextSources: payload.contextSources }
      : {}),
    ...(payload.error ? { error: payload.error } : {}),
    ...(payload.ragSources ? { ragSources: payload.ragSources } : {}),
    ...(payload.selectedToolNames
      ? { selectedToolNames: payload.selectedToolNames }
      : {}),
    ...(payload.terminationReason
      ? { terminationReason: payload.terminationReason }
      : {}),
    ...(payload.toolCalls ? { toolCalls: payload.toolCalls } : {}),
    ...(payload.turnOutcome ? { turnOutcome: payload.turnOutcome } : {}),
    ...(payload.turnRecord ? { turnRecord: payload.turnRecord } : {}),
  };
  return buildLegacyTurnFlowFromMessage(syntheticMessage);
}
