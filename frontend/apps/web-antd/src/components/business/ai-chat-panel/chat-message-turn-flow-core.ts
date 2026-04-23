import type {
  ChatMessage,
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

import { $t } from '#/locales';

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

export function normalizeNumber(value: unknown): number | undefined {
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

export function normalizeBoolean(value: unknown): boolean | undefined {
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

export function normalizeStageStatus(
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

export function normalizeStage(
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

export function normalizeEvidence(
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

export function normalizeAnswerCard(
  value: unknown,
): TurnFlowAnswerCard | undefined {
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

export function normalizeErrorSurface(
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

export function cloneStage(stage: TurnFlowStage): TurnFlowStage {
  return {
    ...stage,
    ...(stage.metrics ? { metrics: { ...stage.metrics } } : {}),
    ...(stage.detailLines ? { detailLines: [...stage.detailLines] } : {}),
    ...(stage.sourceRefs ? { sourceRefs: [...stage.sourceRefs] } : {}),
    ...(stage.toolCallIds ? { toolCallIds: [...stage.toolCallIds] } : {}),
  };
}

export function cloneEvidence(
  evidence: TurnFlowEvidenceItem,
): TurnFlowEvidenceItem {
  return {
    ...evidence,
    ...(evidence.arguments ? { arguments: { ...evidence.arguments } } : {}),
    ...(evidence.summaryPayload
      ? { summaryPayload: { ...evidence.summaryPayload } }
      : {}),
  };
}

export function mergeEvidence(
  base: TurnFlowEvidenceItem,
  incoming: TurnFlowEvidenceItem,
): TurnFlowEvidenceItem {
  return {
    ...base,
    ...incoming,
    ...(base.arguments || incoming.arguments
      ? {
          arguments: (() => {
            if (incoming.arguments) {
              return { ...incoming.arguments };
            }
            if (base.arguments) {
              return { ...base.arguments };
            }
            return undefined;
          })(),
        }
      : {}),
    ...(base.summaryPayload || incoming.summaryPayload
      ? {
          summaryPayload: (() => {
            if (incoming.summaryPayload) {
              return { ...incoming.summaryPayload };
            }
            if (base.summaryPayload) {
              return { ...base.summaryPayload };
            }
            return undefined;
          })(),
        }
      : {}),
  };
}

export function cloneAnswerCard(
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

export function cloneTurnFlow(flow: TurnFlowViewModel): TurnFlowViewModel {
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

export function mergeStage(
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

export function upsertStage(
  flow: TurnFlowViewModel,
  stage: TurnFlowStage,
): void {
  const index = flow.timeline.findIndex((item) => item.id === stage.id);
  if (index === -1) {
    flow.timeline.push(cloneStage(stage));
    return;
  }
  const previous = flow.timeline[index];
  if (!previous) {
    flow.timeline.push(cloneStage(stage));
    return;
  }
  flow.timeline[index] = mergeStage(previous, stage);
}

export function upsertEvidence(
  flow: TurnFlowViewModel,
  evidence: TurnFlowEvidenceItem,
): void {
  const index = flow.evidence.findIndex((item) => item.id === evidence.id);
  if (index === -1) {
    flow.evidence.push(cloneEvidence(evidence));
    return;
  }
  const previous = flow.evidence[index];
  if (!previous) {
    flow.evidence.push(cloneEvidence(evidence));
    return;
  }
  flow.evidence[index] = mergeEvidence(previous, evidence);
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

export function upsertToolEvidence(
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
  flow.evidence[index] = mergeEvidence(previous, {
    ...evidence,
    ...(evidence.toolCallId
      ? {
          id: evidence.toolCallId,
          toolCallId: evidence.toolCallId,
        }
      : {}),
  });
}

export function buildToolEvidencePayload({
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
    ...(argumentsValue ? { arguments: { ...argumentsValue } } : {}),
    ...(durationMs === undefined ? {} : { durationMs }),
    ...(error ? { error } : {}),
    ...(errorType ? { errorType } : {}),
    ...(output ? { output } : {}),
    ...(resultLink ? { resultLink, url: resultLink } : {}),
    ...(skillName ? { skillName } : {}),
    ...(skillType ? { skillType } : {}),
    ...(startedAt === undefined ? {} : { startedAt }),
    ...(summary ? { snippet: summary } : {}),
    ...(summaryPayload ? { summaryPayload: { ...summaryPayload } } : {}),
  };
}

export function syncToolExecutionStage(flow: TurnFlowViewModel): void {
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

export function collectRunningToolExecutionRefs(
  flow?: TurnFlowViewModel,
): Array<{ id?: string; name?: string }> {
  if (!flow) {
    return [];
  }
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
    title:
      finalStatus === 'error'
        ? $t('common.globalAiChat.turnStageType.failed')
        : $t('common.globalAiChat.turnStageType.completed'),
    type: finalStatus === 'error' ? 'failed' : 'completed',
  });
}

export function settleTurnFlowFinalState(
  flow: TurnFlowViewModel,
  finalStatus: TurnFlowStageStatus,
): void {
  if (finalStatus === 'error' || finalStatus === 'interrupted') {
    setRunningToolEvidenceStatus(flow, 'error');
  } else {
    syncToolExecutionStage(flow);
  }
  finalizeRunningStages(flow, finalStatus);
  ensureTerminalStage(flow);
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
  const timelineRaw = (() => {
    if (Array.isArray(record.timeline)) {
      return record.timeline;
    }
    if (Array.isArray(record.stages)) {
      return record.stages;
    }
    return [];
  })();
  const evidenceRaw = (() => {
    if (Array.isArray(record.evidence)) {
      return record.evidence;
    }
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
    const stageIndex = merged.timeline.findIndex(
      (item) => item.id === stage.id,
    );
    if (stageIndex === -1) {
      merged.timeline.push(cloneStage(stage));
      continue;
    }
    const previous = merged.timeline[stageIndex];
    if (!previous) {
      merged.timeline.push(cloneStage(stage));
      continue;
    }
    merged.timeline[stageIndex] = mergeStage(previous, stage);
  }
  for (const evidence of incoming.evidence) {
    const evidenceIndex = merged.evidence.findIndex(
      (item) => item.id === evidence.id,
    );
    if (evidenceIndex === -1) {
      merged.evidence.push(cloneEvidence(evidence));
      continue;
    }
    const previous = merged.evidence[evidenceIndex];
    if (!previous) {
      merged.evidence.push(cloneEvidence(evidence));
      continue;
    }
    merged.evidence[evidenceIndex] = mergeEvidence(previous, evidence);
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

export function getOrCreateCanonicalTurnFlow(
  message: ChatMessage,
): TurnFlowViewModel {
  return (
    mergeTurnFlow(
      normalizeTurnFlowViewModel(message.turnFlow),
      createEmptyTurnFlow(),
    ) ?? createEmptyTurnFlow()
  );
}

export function normalizeThinkingStageText(
  stage?: TurnFlowStage,
): string | undefined {
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

export function resolveThinkingStage(
  flow: TurnFlowViewModel,
): TurnFlowStage | undefined {
  return flow.timeline.findLast((stage) => stage.type === 'thinking');
}

export function hasCanonicalThinkingContent(flow: TurnFlowViewModel): boolean {
  return !!normalizeThinkingStageText(resolveThinkingStage(flow));
}

export function hasCanonicalRagEvidence(flow: TurnFlowViewModel): boolean {
  return flow.evidence.some(
    (item) => item.kind === 'knowledge_base' || item.kind === 'web',
  );
}

export function hasCanonicalToolSelection(flow: TurnFlowViewModel): boolean {
  return flow.timeline.some((stage) => stage.type === 'tool_selection');
}
