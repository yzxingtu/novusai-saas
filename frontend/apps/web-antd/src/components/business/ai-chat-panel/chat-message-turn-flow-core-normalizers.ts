import type {
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

import {
  normalizeObjectRecord,
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
  'document',
  'knowledge_base',
  'memory',
  'tool',
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

function normalizeEvidenceKind(
  value: unknown,
): TurnFlowEvidenceKind | undefined {
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
  return undefined;
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
): TurnFlowEvidenceItem | undefined {
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
  const sourceKind =
    normalizeOptionalString(record.source_kind) ??
    normalizeOptionalString(record.sourceKind);
  const docId = normalizeNumber(
    record.doc_id ?? record.docId ?? record.document_id,
  );
  const docName =
    normalizeOptionalString(record.doc_name) ??
    normalizeOptionalString(record.docName) ??
    normalizeOptionalString(record.document_name);
  const chunkId = normalizeNumber(record.chunk_id ?? record.chunkId);
  const knowledgeBaseId = normalizeNumber(
    record.knowledge_base_id ?? record.knowledgeBaseId,
  );
  const knowledgeBaseName =
    normalizeOptionalString(record.knowledge_base_name) ??
    normalizeOptionalString(record.knowledgeBaseName);
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
  const kind = normalizeEvidenceKind(record.kind);
  if (!kind) {
    return undefined;
  }
  return {
    id,
    kind,
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
    ...(sourceKind ? { sourceKind } : {}),
    ...(docId === undefined ? {} : { docId }),
    ...(docName ? { docName } : {}),
    ...(chunkId === undefined ? {} : { chunkId }),
    ...(knowledgeBaseId === undefined ? {} : { knowledgeBaseId }),
    ...(knowledgeBaseName ? { knowledgeBaseName } : {}),
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

export function hasTurnFlowData(value?: TurnFlowViewModel): boolean {
  if (!value) {
    return false;
  }
  return (
    value.timeline.length > 0 ||
    value.evidence.length > 0 ||
    !!value.answerCard ||
    !!value.errorSurface
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
    (item) => item.kind === 'knowledge_base' || item.kind === 'document',
  );
}

export function hasCanonicalToolSelection(flow: TurnFlowViewModel): boolean {
  return flow.timeline.some((stage) => stage.type === 'tool_selection');
}
