import type { ChatMessage, TurnFlowViewModel } from './types';

import {
  hasCanonicalRagEvidence,
  hasCanonicalThinkingContent,
  hasCanonicalToolSelection,
  hasTurnFlowData,
  normalizeAnswerCard,
  normalizeBoolean,
  normalizeErrorSurface,
  normalizeEvidence,
  normalizeNumber,
  normalizeStage,
  normalizeStageStatus,
  normalizeThinkingStageText,
  resolveThinkingStage,
} from './chat-message-turn-flow-core-normalizers';
import {
  buildToolEvidencePayload,
  cloneAnswerCard,
  cloneEvidence,
  cloneStage,
  cloneTurnFlow,
  collectRunningToolExecutionRefs,
  mergeEvidence,
  mergeStage,
  settleTurnFlowFinalState,
  syncToolExecutionStage,
  upsertEvidence,
  upsertStage,
  upsertToolEvidence,
} from './chat-message-turn-flow-core-ops';
import {
  normalizeObjectRecord,
  normalizeObjectRecordList,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';

export {
  buildToolEvidencePayload,
  cloneAnswerCard,
  cloneEvidence,
  cloneStage,
  cloneTurnFlow,
  collectRunningToolExecutionRefs,
  hasCanonicalRagEvidence,
  hasCanonicalThinkingContent,
  hasCanonicalToolSelection,
  mergeEvidence,
  mergeStage,
  normalizeAnswerCard,
  normalizeBoolean,
  normalizeErrorSurface,
  normalizeEvidence,
  normalizeNumber,
  normalizeStage,
  normalizeStageStatus,
  normalizeThinkingStageText,
  resolveThinkingStage,
  settleTurnFlowFinalState,
  syncToolExecutionStage,
  upsertEvidence,
  upsertStage,
  upsertToolEvidence,
};

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
  const failureKind =
    normalizeOptionalString(record.failure_kind) ??
    normalizeOptionalString(record.failureKind);
  const turnOutcome =
    normalizeOptionalString(record.turn_outcome) ??
    normalizeOptionalString(record.turnOutcome);
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
    ...(failureKind ? { failureKind } : {}),
    ...(complete === undefined ? {} : { complete }),
    ...(traceId ? { traceId } : {}),
    ...(turnOutcome ? { turnOutcome } : {}),
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
