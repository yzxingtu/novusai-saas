import type {
  ChatMessage,
  TurnFlowErrorSurface,
  TurnFlowEvidenceItem,
  TurnFlowStage,
  TurnFlowStageStatus,
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
  upsertEvidence,
  upsertStage,
} from './chat-message-turn-flow-core';
import {
  normalizeObjectRecord,
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
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'tool_error',
  'tool_round_failed',
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
  '已完成',
  '已完成答案整理',
  '已完成证据整理',
  '本轮过程',
  '结果整理',
]);

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
  const flow = getOrCreateCanonicalTurnFlow(message);
  flow.answerCard = answerCard;
  message.turnFlow = flow;
}

export function applyCanonicalDoneEvent(
  message: ChatMessage,
  event: Record<string, unknown>,
): void {
  const turnRecord = normalizeObjectRecord(
    event.turn_record ?? event.turnRecord,
  );
  const turnRecordMetadata = normalizeObjectRecord(turnRecord?.metadata);
  const incomingTurnFlow = normalizeTurnFlowViewModel(
    event.turn_flow ??
      event.turnFlow ??
      turnRecord?.turn_flow ??
      turnRecord?.turnFlow ??
      turnRecordMetadata?.turn_flow ??
      turnRecordMetadata?.turnFlow,
  );
  const baseFlow = getOrCreateCanonicalTurnFlow(message);
  const flow = incomingTurnFlow
    ? (mergeTurnFlow(baseFlow, incomingTurnFlow) ?? baseFlow)
    : baseFlow;

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
  const flow = getOrCreateCanonicalTurnFlow(message);
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
