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
  const resultLink =
    normalizeOptionalString(record.result_link) ??
    normalizeOptionalString(record.resultLink);
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
  const toolName =
    normalizeOptionalString(record.tool_name) ??
    normalizeOptionalString(record.toolName);
  const displayName =
    normalizeOptionalString(record.display_name) ??
    normalizeOptionalString(record.displayName);
  const status = (() => {
    const normalized = normalizeOptionalString(record.status);
    if (
      normalized === 'running' ||
      normalized === 'success' ||
      normalized === 'error'
    ) {
      return normalized;
    }
    return undefined;
  })();
  const score = normalizeNumber(record.score);
  const argumentsValue = normalizeObjectRecord(record.arguments) ?? undefined;
  const error = normalizeOptionalString(record.error);
  const errorType = normalizeOptionalString(
    record.error_type ?? record.errorType,
  );
  const output = normalizeOptionalString(record.output);
  const skillName = normalizeOptionalString(
    record.skill_name ?? record.skillName,
  );
  const skillType = normalizeOptionalString(
    record.skill_type ?? record.skillType,
  );
  const summaryPayload =
    normalizeObjectRecord(record.summary_payload ?? record.summaryPayload) ??
    undefined;
  const durationMs = normalizeNumber(record.duration_ms ?? record.durationMs);
  const startedAt = normalizeNumber(record.started_at ?? record.startedAt);
  return {
    id,
    kind: normalizeEvidenceKind(record.kind),
    ...(title ? { title } : {}),
    ...(url ? { url } : {}),
    ...(resultLink ? { resultLink } : {}),
    ...(snippet ? { snippet } : {}),
    ...(badge ? { badge } : {}),
    ...(score === undefined ? {} : { score }),
    ...(displayName ? { displayName } : {}),
    ...(toolName ? { toolName } : {}),
    ...(status ? { status } : {}),
    ...(argumentsValue ? { arguments: argumentsValue } : {}),
    ...(error ? { error } : {}),
    ...(errorType ? { errorType } : {}),
    ...(output ? { output } : {}),
    ...(skillName ? { skillName } : {}),
    ...(skillType ? { skillType } : {}),
    ...(summaryPayload ? { summaryPayload } : {}),
    ...(durationMs === undefined ? {} : { durationMs }),
    ...(startedAt === undefined ? {} : { startedAt }),
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

function findMatchingToolEvidenceIndex(
  flow: TurnFlowViewModel,
  evidence: TurnFlowEvidenceItem,
): number {
  const toolCallId = evidence.toolCallId;
  for (let index = flow.evidence.length - 1; index >= 0; index -= 1) {
    const item = flow.evidence[index];
    if (!item || item.kind !== 'tool') {
      continue;
    }
    if (
      toolCallId &&
      item.toolCallId === toolCallId &&
      item.status === 'running'
    ) {
      return index;
    }
  }
  for (let index = flow.evidence.length - 1; index >= 0; index -= 1) {
    const item = flow.evidence[index];
    if (!item || item.kind !== 'tool') {
      continue;
    }
    if (toolCallId && item.toolCallId === toolCallId) {
      return index;
    }
  }
  return -1;
}

function upsertToolEvidence(
  flow: TurnFlowViewModel,
  evidence: TurnFlowEvidenceItem,
): void {
  const index = findMatchingToolEvidenceIndex(flow, evidence);
  if (index === -1) {
    upsertEvidence(flow, evidence);
    return;
  }
  const previous = flow.evidence[index];
  if (!previous) {
    upsertEvidence(flow, evidence);
    return;
  }
  flow.evidence[index] = {
    ...previous,
    ...evidence,
    ...(evidence.toolCallId
      ? {
          id: evidence.toolCallId,
          toolCallId: evidence.toolCallId,
        }
      : {}),
  };
}

function syncToolExecutionStage(flow: TurnFlowViewModel): void {
  const toolEvidence = flow.evidence.filter((item) => item.kind === 'tool');
  if (toolEvidence.length === 0) {
    return;
  }
  const existingStage = flow.timeline.findLast(
    (stage) => stage.type === 'tool_execution',
  );

  const running = toolEvidence.filter(
    (item) => item.status === 'running',
  ).length;
  const failed = toolEvidence.filter((item) => item.status === 'error').length;
  const completed = toolEvidence.filter(
    (item) => item.status === 'success',
  ).length;
  const total = toolEvidence.length;
  const toolCallIds = toolEvidence
    .map((item) => item.toolCallId)
    .filter((item): item is string => !!item);

  let status: TurnFlowStageStatus = 'completed';
  if (running > 0) {
    status = 'running';
  } else if (failed > 0) {
    status = 'error';
  }

  upsertStage(flow, {
    id: existingStage?.id ?? 'turn-tool-execution',
    metrics: {
      ...existingStage?.metrics,
      completed_tool_calls: completed,
      failed_tool_calls: failed,
      running,
      total,
    },
    status,
    toolCallIds,
    type: 'tool_execution',
  });
}

function applyToolCallsToTurnFlow(
  message: ChatMessage,
  toolCalls: ToolCallEvent[] | undefined,
): void {
  if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  for (const toolCall of toolCalls) {
    if (!toolCall?.name) {
      continue;
    }
    upsertToolEvidence(
      flow,
      buildToolEvidencePayload({
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
        toolCallId: normalizeOptionalString(toolCall.id),
        toolName: toolCall.name,
      }),
    );
  }
  syncToolExecutionStage(flow);
  message.turnFlow = flow;
}

function collectRunningToolEvidenceRefs(
  flow: TurnFlowViewModel,
): Array<{ id?: string; name?: string }> {
  return flow.evidence
    .filter((item) => item.kind === 'tool' && item.status === 'running')
    .map((item) => ({
      id: item.toolCallId ?? item.id,
      name: item.toolName ?? item.displayName ?? item.title,
    }));
}

function setRunningToolEvidenceStatus(
  flow: TurnFlowViewModel,
  status: 'error' | 'success',
): void {
  let mutated = false;
  for (const item of flow.evidence) {
    if (item.kind !== 'tool' || item.status !== 'running') {
      continue;
    }
    item.status = status;
    mutated = true;
  }
  if (mutated) {
    syncToolExecutionStage(flow);
  }
}

function buildToolEvidencePayload({
  argumentsValue,
  displayName,
  durationMs,
  error,
  errorType,
  output,
  resultLink,
  skillName,
  skillType,
  startedAt,
  status,
  summary,
  summaryPayload,
  toolCallId,
  toolName,
}: {
  argumentsValue?: Record<string, unknown>;
  displayName?: string;
  durationMs?: number;
  error?: string;
  errorType?: string;
  output?: string;
  resultLink?: string;
  skillName?: string;
  skillType?: string;
  startedAt?: number;
  status: 'error' | 'running' | 'success';
  summary?: string;
  summaryPayload?: Record<string, unknown>;
  toolCallId?: string;
  toolName: string;
}): TurnFlowEvidenceItem {
  return {
    id: toolCallId ?? `tool-${toolName}`,
    kind: 'tool',
    ...(displayName
      ? { displayName, title: displayName }
      : { title: toolName }),
    ...(toolCallId ? { toolCallId } : {}),
    ...(toolName ? { toolName, sourceRef: toolName } : {}),
    ...(status ? { status } : {}),
    ...(argumentsValue ? { arguments: argumentsValue } : {}),
    ...(durationMs === undefined ? {} : { durationMs }),
    ...(error ? { error } : {}),
    ...(errorType ? { errorType } : {}),
    ...(output ? { output } : {}),
    ...(resultLink ? { resultLink, url: resultLink } : {}),
    ...(skillName ? { skillName } : {}),
    ...(skillType ? { skillType } : {}),
    ...(startedAt === undefined ? {} : { startedAt }),
    ...(summary ? { snippet: summary } : {}),
    ...(summaryPayload ? { summaryPayload } : {}),
  };
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

function getOrCreateCanonicalTurnFlow(message: ChatMessage): TurnFlowViewModel {
  return (
    mergeTurnFlow(
      normalizeTurnFlowViewModel(message.turnFlow),
      createEmptyTurnFlow(),
    ) ?? createEmptyTurnFlow()
  );
}

function normalizeThinkingStageText(stage?: TurnFlowStage): string | undefined {
  if (!stage) {
    return undefined;
  }
  const detailText = (stage.detailLines ?? [])
    .map((line) => normalizeOptionalString(line))
    .filter((line): line is string => !!line)
    .join('\n\n');
  if (detailText) {
    return detailText;
  }
  return normalizeOptionalString(stage.summary);
}

function resolveThinkingStage(
  flow: TurnFlowViewModel,
): TurnFlowStage | undefined {
  return flow.timeline.findLast((stage) => stage.type === 'thinking');
}

function hasCanonicalThinkingContent(flow: TurnFlowViewModel): boolean {
  return !!normalizeThinkingStageText(resolveThinkingStage(flow));
}

function hasCanonicalRagEvidence(flow: TurnFlowViewModel): boolean {
  return flow.evidence.some(
    (item) => item.kind === 'knowledge_base' || item.kind === 'web',
  );
}

export function appendThinkingDeltaToTurnFlow(
  message: ChatMessage,
  delta: string | undefined,
): void {
  const normalizedDelta = normalizeOptionalString(delta);
  if (!normalizedDelta) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  const existingStage = resolveThinkingStage(flow);
  const nextText = `${normalizeThinkingStageText(existingStage) ?? ''}${normalizedDelta}`;
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
  appendThinkingDeltaToTurnFlow(message, message.content);
  message.content = '';
}

export function applyOptimizingToolsToTurnFlow(
  message: ChatMessage,
  selection: { selected?: number; total?: number },
): void {
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
  } else if (message.streaming) {
    selectionStatus = 'running';
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

export function canonicalizeAssistantLegacyFieldsIntoTurnFlow(
  message: ChatMessage,
): void {
  const flow = normalizeTurnFlowViewModel(message.turnFlow);
  if (!flow) {
    return;
  }

  const legacyThinking = normalizeOptionalString(message.thinkingContent);
  if (legacyThinking && !hasCanonicalThinkingContent(flow)) {
    appendThinkingDeltaToTurnFlow(message, legacyThinking);
  }

  if (message.toolCalls?.length) {
    applyToolCallsToTurnFlow(message, message.toolCalls);
  }

  const nextFlow = normalizeTurnFlowViewModel(message.turnFlow);
  if (
    message.ragSources?.length &&
    nextFlow &&
    !hasCanonicalRagEvidence(nextFlow)
  ) {
    applyRagSourcesToTurnFlow(message, message.ragSources);
  }

  delete message.thinkingContent;
  delete message.toolCalls;
  delete message.ragSources;
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
    flow = createEmptyTurnFlow();
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

  if (finalStageStatus === 'error' || finalStageStatus === 'interrupted') {
    setRunningToolEvidenceStatus(flow, 'error');
  } else {
    syncToolExecutionStage(flow);
  }
  finalizeRunningStages(flow, finalStageStatus);
  ensureTerminalStage(flow);
  message.turnFlow = flow;
}

export function getRunningToolExecutionRefs(
  message: ChatMessage,
): Array<{ id?: string; name?: string }> {
  const flow = normalizeTurnFlowViewModel(message.turnFlow);
  if (flow) {
    return collectRunningToolEvidenceRefs(flow);
  }
  return (message.toolCalls ?? [])
    .filter((toolCall) => toolCall.status === 'running')
    .map((toolCall) => ({
      id: toolCall.id,
      name: toolCall.name,
    }));
}

export function settleTurnFlowAfterLifecycleFinalize(
  message: ChatMessage,
): void {
  const flow =
    normalizeTurnFlowViewModel(message.turnFlow) ?? createEmptyTurnFlow();
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
  if (finalStageStatus === 'error' || finalStageStatus === 'interrupted') {
    setRunningToolEvidenceStatus(flow, 'error');
  } else {
    syncToolExecutionStage(flow);
  }
  finalizeRunningStages(flow, finalStageStatus);
  ensureTerminalStage(flow);
  message.turnFlow = flow;
}
