import type {
  ChatMessage,
  TurnFlowErrorSurface,
  TurnFlowEvidenceItem,
  TurnFlowStage,
  TurnFlowStageStatus,
  TurnFlowViewModel,
} from './types';

import type { AppErrorInfo } from '#/utils/request';

import {
  collectRunningToolExecutionRefs,
  getOrCreateCanonicalTurnFlow,
  mergeTurnFlow,
  normalizeAnswerCard,
  normalizeBoolean,
  normalizeEvidence,
  normalizeStage,
  normalizeTurnFlowViewModel,
  settleTurnFlowFinalState,
  syncToolExecutionStage,
  upsertEvidence,
  upsertStage,
  upsertToolEvidence,
} from './chat-message-turn-flow-core';
import {
  normalizeObjectRecord,
  normalizeObjectRecordList,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';

export {
  buildToolEvidencePayload,
  createEmptyTurnFlow,
  getOrCreateCanonicalTurnFlow,
  hasCanonicalRagEvidence,
  hasCanonicalThinkingContent,
  hasCanonicalToolSelection,
  mergeTurnFlow,
  normalizeThinkingStageText,
  normalizeTurnFlowViewModel,
  resolveThinkingStage,
  syncToolExecutionStage,
  upsertEvidence,
  upsertStage,
  upsertToolEvidence,
} from './chat-message-turn-flow-core';

const FAILURE_REASON_SET = new Set([
  'error',
  'failed',
  'no_answer_quality_evidence',
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'tool_error',
  'tool_round_failed',
  'untrusted_final_output_source',
]);

const FAILURE_OUTCOME_SET = new Set(['error', 'failed', 'tool_round_failed']);
const TURN_FLOW_FINAL_STAGE_STATUS_SET = new Set<TurnFlowStageStatus>([
  'completed',
  'error',
  'interrupted',
  'running',
  'skipped',
]);
const TURN_FLOW_NON_VISIBLE_SUMMARY_SET = new Set([
  'No trusted assistant final answer.',
  'The assistant could not finish this turn. Please retry.',
  '已完成',
  '已完成答案整理',
  '已完成证据整理',
  '本轮过程',
  '结果整理',
  '这次处理没有成功生成最终答复，请再试一次。',
]);

const CANONICAL_STAGE_KEYS = [
  'detail_lines',
  'duration_ms',
  'ended_at_ms',
  'id',
  'metrics',
  'source_refs',
  'stage_id',
  'stage_type',
  'started_at_ms',
  'status',
  'summary',
  'title',
  'tool_call_ids',
  'type',
] as const;

const CANONICAL_EVIDENCE_KEYS = [
  'arguments',
  'badge',
  'chunk_id',
  'display_name',
  'doc_id',
  'doc_name',
  'document_id',
  'document_name',
  'duration_ms',
  'error',
  'error_type',
  'id',
  'kind',
  'knowledge_base_id',
  'knowledge_base_name',
  'output',
  'result_link',
  'score',
  'skill_name',
  'skill_type',
  'source_kind',
  'snippet',
  'source_ref',
  'started_at',
  'status',
  'summary',
  'summary_payload',
  'title',
  'tool_call_id',
  'tool_name',
  'url',
] as const;

function pickCanonicalFields(
  record: Record<string, unknown>,
  keys: readonly string[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of keys) {
    if (record[key] !== undefined) {
      out[key] = record[key];
    }
  }
  return out;
}

function canonicalStageRecord(value: unknown): null | Record<string, unknown> {
  const record = normalizeObjectRecord(value);
  return record ? pickCanonicalFields(record, CANONICAL_STAGE_KEYS) : null;
}

function canonicalEvidenceRecord(
  value: unknown,
): null | Record<string, unknown> {
  const record = normalizeObjectRecord(value);
  return record ? pickCanonicalFields(record, CANONICAL_EVIDENCE_KEYS) : null;
}

function canonicalAnswerCardPayload(value: unknown): unknown {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  return pickCanonicalFields(record, [
    'confidence_label',
    'follow_up_suggestions',
    'sections',
    'source_chip_ids',
    'summary',
  ]);
}

function canonicalErrorSurfacePayload(value: unknown): unknown {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  return pickCanonicalFields(record, [
    'debug_message',
    'detail',
    'error',
    'error_type',
    'message',
    'reason',
    'summary',
    'trace_id',
  ]);
}

function canonicalTurnFlowPayload(
  value: unknown,
): null | Record<string, unknown> {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return null;
  }
  const out = pickCanonicalFields(record, [
    'completion_reason',
    'failure_kind',
    'final_stage_status',
    'interrupted',
    'trace_id',
    'turn_flow_complete',
    'turn_outcome',
  ]);
  let hasCanonicalPayload = false;
  const timeline = normalizeObjectRecordList(record.timeline)
    .map((item) => canonicalStageRecord(item))
    .filter((item): item is Record<string, unknown> => !!item);
  if (timeline.length > 0) {
    hasCanonicalPayload = true;
    out.timeline = timeline;
  }
  const evidence = normalizeObjectRecordList(record.evidence)
    .map((item) => canonicalEvidenceRecord(item))
    .filter((item): item is Record<string, unknown> => !!item);
  if (evidence.length > 0) {
    hasCanonicalPayload = true;
    out.evidence = evidence;
  }
  const answerCard = canonicalAnswerCardPayload(record.answer_card);
  if (answerCard) {
    hasCanonicalPayload = true;
    out.answer_card = answerCard;
  }
  const errorSurface = canonicalErrorSurfacePayload(record.error_surface);
  if (errorSurface) {
    hasCanonicalPayload = true;
    out.error_surface = errorSurface;
  }
  if (!hasCanonicalPayload) {
    return null;
  }
  return out;
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

function extractCanonicalFailureKind(value: unknown): string | undefined {
  const record = normalizeObjectRecord(value);
  if (!record) {
    return undefined;
  }
  const metadata = normalizeObjectRecord(record.metadata);
  return (
    normalizeFailureSignal(record.failure_kind) ??
    normalizeFailureSignal(metadata?.failure_kind)
  );
}

function resolveMessageFailureKind(message: ChatMessage): string | undefined {
  const messageRecord = message as unknown as Record<string, unknown>;
  return (
    normalizeFailureSignal(
      messageRecord.failure_kind ?? messageRecord.failureKind,
    ) ??
    extractFailureKind(message.turnFlow) ??
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

function buildStageFromCanonicalEvent(
  event: Record<string, unknown>,
): TurnFlowStage | undefined {
  const stageRecord = normalizeObjectRecord(event.stage_payload) ?? null;
  const candidate = {
    ...event,
    ...stageRecord,
  };
  const normalizedCandidate = canonicalStageRecord(candidate);
  if (!normalizedCandidate) {
    return undefined;
  }
  return normalizeStage(normalizedCandidate, 0);
}

function buildEvidenceFromCanonicalEvent(
  event: Record<string, unknown>,
): TurnFlowEvidenceItem | undefined {
  const evidenceRecord = normalizeObjectRecord(event.evidence) ?? null;
  const candidate = {
    ...event,
    ...evidenceRecord,
  };
  const normalizedCandidate = canonicalEvidenceRecord(candidate);
  if (!normalizedCandidate) {
    return undefined;
  }
  return normalizeEvidence(normalizedCandidate, 0);
}

function nestedTurnFlowFromDone(
  event: Record<string, unknown>,
  turnRecord?: null | Record<string, unknown>,
): TurnFlowViewModel | undefined {
  const turnRecordMetadata = normalizeObjectRecord(turnRecord?.metadata);
  return normalizeTurnFlowViewModel(
    canonicalTurnFlowPayload(
      event.turn_flow ?? turnRecord?.turn_flow ?? turnRecordMetadata?.turn_flow,
    ),
  );
}

function failureKindFromFlow(flow?: TurnFlowViewModel): string | undefined {
  if (!flow) {
    return undefined;
  }
  const errorSurface = normalizeObjectRecord(flow.errorSurface);
  const completionReason = normalizeFailureSignal(flow.completionReason);
  return (
    (isFailureSignal(completionReason) ? completionReason : undefined) ??
    normalizeFailureSignal(flow.failureKind) ??
    normalizeFailureSignal(errorSurface?.failure_kind) ??
    normalizeFailureSignal(errorSurface?.failureKind) ??
    normalizeFailureSignal(errorSurface?.error_type) ??
    normalizeFailureSignal(errorSurface?.errorType) ??
    undefined
  );
}

function stageStatusFromDone(
  event: Record<string, unknown>,
  mergedFlow?: TurnFlowViewModel,
): TurnFlowStageStatus {
  const turnRecord = normalizeObjectRecord(event.turn_record);
  const nestedFlow = mergedFlow ?? nestedTurnFlowFromDone(event, turnRecord);
  const completionReason = normalizeFailureSignal(
    event.completion_reason ?? nestedFlow?.completionReason,
  );
  const terminationReason = normalizeFailureSignal(
    event.termination_reason ??
      turnRecord?.termination_reason ??
      nestedFlow?.completionReason,
  );
  const turnOutcome = normalizeFailureSignal(
    event.turn_outcome ?? turnRecord?.turn_outcome ?? nestedFlow?.turnOutcome,
  );
  const failureKind =
    normalizeFailureSignal(event.failure_kind) ??
    extractCanonicalFailureKind(turnRecord) ??
    failureKindFromFlow(nestedFlow);
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
  const status = normalizeOptionalString(event.final_stage_status);
  const nestedStatus = normalizeOptionalString(nestedFlow?.finalStageStatus);
  if (status === 'failed') {
    return 'error';
  }
  if (
    status &&
    status !== 'completed' &&
    TURN_FLOW_FINAL_STAGE_STATUS_SET.has(status as TurnFlowStageStatus)
  ) {
    return status as TurnFlowStageStatus;
  }
  if (nestedStatus === 'failed') {
    return 'error';
  }
  if (
    nestedStatus &&
    nestedStatus !== 'completed' &&
    TURN_FLOW_FINAL_STAGE_STATUS_SET.has(nestedStatus as TurnFlowStageStatus)
  ) {
    return nestedStatus as TurnFlowStageStatus;
  }
  if (
    status &&
    TURN_FLOW_FINAL_STAGE_STATUS_SET.has(status as TurnFlowStageStatus)
  ) {
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

function normalizeTurnFlowPrimaryTextCandidate(
  value: unknown,
): string | undefined {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    return undefined;
  }
  if (TURN_FLOW_NON_VISIBLE_SUMMARY_SET.has(normalized)) {
    return undefined;
  }
  return normalized;
}

function resolveTurnFlowPrimaryText(
  flow: ReturnType<typeof getOrCreateCanonicalTurnFlow>,
): string | undefined {
  const answerCardSummary = normalizeTurnFlowPrimaryTextCandidate(
    flow.answerCard?.summary,
  );
  if (answerCardSummary) {
    return answerCardSummary;
  }

  for (const section of flow.answerCard?.sections ?? []) {
    const sectionBody = normalizeTurnFlowPrimaryTextCandidate(
      section.body ?? section.content,
    );
    if (sectionBody) {
      return sectionBody;
    }
  }

  return (
    normalizeTurnFlowPrimaryTextCandidate(flow.errorSurface?.message) ??
    normalizeTurnFlowPrimaryTextCandidate(flow.errorSurface?.summary) ??
    normalizeTurnFlowPrimaryTextCandidate(flow.errorSurface?.detail) ??
    normalizeTurnFlowPrimaryTextCandidate(flow.errorSurface?.error) ??
    normalizeTurnFlowPrimaryTextCandidate(flow.errorSurface?.reason)
  );
}

function syncMessageContentFromTurnFlow(
  message: ChatMessage,
  flow: ReturnType<typeof getOrCreateCanonicalTurnFlow>,
): void {
  if (normalizeOptionalString(message.content)) {
    return;
  }
  const candidate = resolveTurnFlowPrimaryText(flow);
  if (candidate) {
    message.content = candidate;
  }
}

export function applyCanonicalTurnStageEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const stage = buildStageFromCanonicalEvent(event);
  if (!stage) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
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
  const flow = getOrCreateCanonicalTurnFlow(message);
  if (evidence.kind === 'tool') {
    upsertToolEvidence(flow, evidence);
    syncToolExecutionStage(flow);
  } else {
    upsertEvidence(flow, evidence);
  }
  message.turnFlow = flow;
}

export function applyCanonicalTurnAnswerCardEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const answerCard = normalizeAnswerCard(
    canonicalAnswerCardPayload(event.answer_card),
  );
  if (!answerCard) {
    return;
  }
  const flow = getOrCreateCanonicalTurnFlow(message);
  flow.answerCard = answerCard;
  message.turnFlow = flow;
}

export function applyCanonicalDoneEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const turnRecord = normalizeObjectRecord(event.turn_record);
  const incomingTurnFlow = nestedTurnFlowFromDone(event, turnRecord);
  const existingFlow = normalizeTurnFlowViewModel(message.turnFlow);
  if (!incomingTurnFlow && !existingFlow) {
    const completionReason =
      normalizeOptionalString(event.completion_reason) ??
      normalizeOptionalString(event.termination_reason) ??
      inferCompletionReason(message);
    if (completionReason && !message.completionReason) {
      message.completionReason = completionReason;
    }
    const turnOutcome = normalizeFailureSignal(
      event.turn_outcome ?? turnRecord?.turn_outcome,
    );
    if (turnOutcome) {
      message.turnOutcome = message.turnOutcome || turnOutcome;
    }
    const finalStageStatus = stageStatusFromDone(event);
    if (finalStageStatus === 'error') {
      message.turnOutcome = message.turnOutcome || 'failed';
      message.requestFailedRetry = true;
      message.terminationReason =
        message.terminationReason || completionReason || 'error';
    } else if (finalStageStatus === 'interrupted') {
      message.interrupted = true;
      message.partial = true;
      message.turnOutcome = message.turnOutcome || 'partial';
      message.terminationReason =
        message.terminationReason || completionReason || 'interrupted';
    }
    if (finalStageStatus === 'error' || finalStageStatus === 'interrupted') {
      const flow = getOrCreateCanonicalTurnFlow(message);
      if (completionReason) {
        flow.completionReason = completionReason;
      }
      const failureKind =
        normalizeFailureSignal(event.failure_kind) ??
        extractCanonicalFailureKind(turnRecord);
      if (failureKind) {
        flow.failureKind = failureKind;
      }
      if (turnOutcome) {
        flow.turnOutcome = turnOutcome;
      }
      flow.finalStageStatus = finalStageStatus;
      flow.complete = true;
      flow.interrupted = finalStageStatus === 'interrupted';
      settleTurnFlowFinalState(flow, finalStageStatus);
      message.turnFlow = flow;
    }
    return;
  }
  const baseFlow = existingFlow ?? getOrCreateCanonicalTurnFlow(message);
  const flow = incomingTurnFlow
    ? (mergeTurnFlow(baseFlow, incomingTurnFlow) ?? baseFlow)
    : baseFlow;
  const failureKind =
    normalizeFailureSignal(event.failure_kind) ??
    extractCanonicalFailureKind(turnRecord) ??
    failureKindFromFlow(flow);
  const turnOutcome =
    normalizeFailureSignal(event.turn_outcome ?? turnRecord?.turn_outcome) ??
    normalizeFailureSignal(flow.turnOutcome);
  if (failureKind) {
    flow.failureKind = failureKind;
  }
  if (turnOutcome) {
    flow.turnOutcome = turnOutcome;
  }

  const completionReason =
    normalizeOptionalString(event.completion_reason) ??
    normalizeOptionalString(event.termination_reason) ??
    normalizeOptionalString(flow.completionReason) ??
    inferCompletionReason(message);
  if (completionReason) {
    flow.completionReason = completionReason;
  }

  const finalStageStatus = stageStatusFromDone(event, flow);
  flow.finalStageStatus = finalStageStatus;
  flow.complete = normalizeBoolean(event.turn_flow_complete) ?? true;
  flow.interrupted =
    normalizeBoolean(event.interrupted) ??
    (completionReason === 'interrupted' ||
      finalStageStatus === 'interrupted' ||
      message.interrupted === true);
  const traceId = normalizeOptionalString(event.trace_id);
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

  settleTurnFlowFinalState(flow, finalStageStatus);
  syncMessageContentFromTurnFlow(message, flow);
  message.turnFlow = flow;
}

export function getRunningToolExecutionRefs(
  message: ChatMessage,
): Array<{ id?: string; name?: string }> {
  return collectRunningToolExecutionRefs(
    normalizeTurnFlowViewModel(message.turnFlow),
  );
}

export function settleTurnFlowAfterLifecycleFinalize(
  message: ChatMessage,
): void {
  const flow = normalizeTurnFlowViewModel(message.turnFlow);
  if (!flow) {
    return;
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
  settleTurnFlowFinalState(flow, finalStageStatus);
  syncMessageContentFromTurnFlow(message, flow);
  message.turnFlow = flow;
}
