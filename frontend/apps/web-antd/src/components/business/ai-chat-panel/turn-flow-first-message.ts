import type { ChatMessage, RagSource, ToolCallEvent } from './types';

import { projectAssistantFieldsIntoTurnFlow } from './use-ai-chat-turn-flow';

const TURN_FLOW_STAGE_TYPES = new Set([
  'answer_assembly',
  'completed',
  'failed',
  'retrieval',
  'thinking',
  'tool_execution',
  'tool_selection',
]);

const TURN_FLOW_STAGE_STATUSES = new Set([
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

type TurnFlowRecord = Record<string, unknown>;
type TurnFlowStageRecord = Record<string, unknown>;

function asRecord(value: unknown): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function asNumber(value: unknown): number | undefined {
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

function normalizeStageType(value: unknown): string | undefined {
  const type = asString(value);
  if (!type || !TURN_FLOW_STAGE_TYPES.has(type)) {
    return undefined;
  }
  return type;
}

function normalizeStageStatus(value: unknown): string | undefined {
  const status = asString(value);
  if (!status) {
    return undefined;
  }
  if (status === 'failed') {
    return 'error';
  }
  if (TURN_FLOW_STAGE_STATUSES.has(status)) {
    return status;
  }
  return undefined;
}

function hasTurnFlowShape(value: unknown): value is TurnFlowRecord {
  const record = asRecord(value);
  if (!record) {
    return false;
  }
  return Array.isArray(record.timeline) || Array.isArray(record.evidence);
}

function normalizeLegacyToolCalls(value: unknown): ToolCallEvent[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const toolCalls = value.filter((item) => {
    const record = asRecord(item);
    return !!asString(record?.name);
  }) as ToolCallEvent[];
  return toolCalls.length > 0 ? toolCalls : undefined;
}

function normalizeLegacyRagSources(value: unknown): RagSource[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const ragSources = value.filter((item) => {
    const record = asRecord(item);
    return !!asString(record?.doc_name);
  }) as RagSource[];
  return ragSources.length > 0 ? ragSources : undefined;
}

function normalizeLegacyOptimizingTools(
  value: unknown,
): { selected?: number; total?: number } | undefined {
  const record = asRecord(value);
  if (!record) {
    return undefined;
  }
  const selected = asNumber(record.selected);
  const total = asNumber(record.total);
  if (selected === undefined && total === undefined) {
    return undefined;
  }
  return {
    ...(selected === undefined ? {} : { selected }),
    ...(total === undefined ? {} : { total }),
  };
}

export function extractMessageTurnFlow(
  message: ChatMessage,
): TurnFlowRecord | undefined {
  if (hasTurnFlowShape(message.turnFlow)) {
    return message.turnFlow as unknown as TurnFlowRecord;
  }

  const messageRecord = message as unknown as Record<string, unknown>;
  if (hasTurnFlowShape(messageRecord.turn_flow)) {
    return messageRecord.turn_flow as TurnFlowRecord;
  }
  const metadata = asRecord(messageRecord.metadata);
  if (!metadata) {
    return undefined;
  }
  if (hasTurnFlowShape(metadata.turn_flow)) {
    return metadata.turn_flow as TurnFlowRecord;
  }
  if (hasTurnFlowShape(metadata.turnFlow)) {
    return metadata.turnFlow as TurnFlowRecord;
  }
  return undefined;
}

function isLegacyStage(stage: TurnFlowStageRecord): boolean {
  const stageId = asString(stage.id);
  if (stageId?.startsWith('legacy-')) {
    return true;
  }
  const source = asString(stage.source);
  if (source === 'legacy') {
    return true;
  }
  return false;
}

function dedupeTimelineByStageType(
  timeline: TurnFlowStageRecord[],
): TurnFlowStageRecord[] {
  const stageByType = new Map<
    string,
    { index: number; isLegacy: boolean; stage: TurnFlowStageRecord }
  >();
  const passthroughStages: Array<{
    index: number;
    stage: TurnFlowStageRecord;
  }> = [];

  timeline.forEach((stage, index) => {
    const normalizedType = normalizeStageType(stage.type);
    const normalizedStatus = normalizeStageStatus(stage.status);
    const normalizedStage: TurnFlowStageRecord = {
      ...stage,
      ...(normalizedType ? { type: normalizedType } : {}),
      ...(normalizedStatus ? { status: normalizedStatus } : {}),
      ...(asString(stage.id) ? {} : { id: `turn-stage-${index + 1}` }),
    };
    const stageType = normalizeStageType(normalizedStage.type);
    if (!stageType) {
      passthroughStages.push({ index, stage: normalizedStage });
      return;
    }
    const nextCandidate = {
      index,
      isLegacy: isLegacyStage(normalizedStage),
      stage: normalizedStage,
    };
    const currentCandidate = stageByType.get(stageType);
    if (!currentCandidate) {
      stageByType.set(stageType, nextCandidate);
      return;
    }
    const shouldReplace =
      (currentCandidate.isLegacy && !nextCandidate.isLegacy) ||
      (currentCandidate.isLegacy === nextCandidate.isLegacy &&
        nextCandidate.index > currentCandidate.index);
    if (shouldReplace) {
      stageByType.set(stageType, nextCandidate);
    }
  });

  return [...passthroughStages, ...stageByType.values()]
    .toSorted((left, right) => left.index - right.index)
    .map((item) => item.stage);
}

function inferFailureFromCompletionReason(
  turnFlow: TurnFlowRecord,
  message: ChatMessage,
): boolean {
  const reason =
    asString(turnFlow.completionReason) ||
    asString(turnFlow.completion_reason) ||
    asString(message.completionReason) ||
    asString((message as unknown as Record<string, unknown>).terminationReason);
  return !!reason && FAILURE_COMPLETION_REASONS.has(reason);
}

function normalizeFailureTerminalStages(
  timeline: TurnFlowStageRecord[],
  turnFlow: TurnFlowRecord,
  message: ChatMessage,
): TurnFlowStageRecord[] {
  const finalStageStatus =
    normalizeStageStatus(turnFlow.finalStageStatus) ||
    normalizeStageStatus(turnFlow.final_stage_status);
  const failureTerminal =
    finalStageStatus === 'error' ||
    inferFailureFromCompletionReason(turnFlow, message) ||
    Boolean(message.error) ||
    timeline.some((stage) => normalizeStageType(stage.type) === 'failed');
  if (!failureTerminal) {
    return timeline;
  }

  const normalizedTimeline: TurnFlowStageRecord[] = [];
  let failedStageSeen = false;
  let completedTerminal: null | TurnFlowStageRecord = null;

  for (const stage of timeline) {
    const type = normalizeStageType(stage.type);
    const nextStage: TurnFlowStageRecord = { ...stage };

    if (type === 'answer_assembly') {
      nextStage.status = 'error';
      normalizedTimeline.push(nextStage);
      continue;
    }

    if (type === 'failed') {
      nextStage.status = 'error';
      failedStageSeen = true;
      normalizedTimeline.push(nextStage);
      continue;
    }

    if (type === 'completed') {
      completedTerminal = nextStage;
      continue;
    }

    normalizedTimeline.push(nextStage);
  }

  if (!failedStageSeen) {
    const completedTerminalId = asString(completedTerminal?.id);
    normalizedTimeline.push({
      ...completedTerminal,
      id: completedTerminalId ? `${completedTerminalId}-failed` : 'turn-failed',
      status: 'error',
      type: 'failed',
    });
  }

  return normalizedTimeline;
}

function normalizeTurnFlowForDisplay(
  message: ChatMessage,
): TurnFlowRecord | undefined {
  const turnFlow = extractMessageTurnFlow(message);
  if (!turnFlow) {
    return undefined;
  }
  const timeline = Array.isArray(turnFlow.timeline) ? turnFlow.timeline : [];
  const stageRecords = timeline
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null);
  if (stageRecords.length === 0) {
    return { ...turnFlow };
  }
  const dedupedTimeline = dedupeTimelineByStageType(stageRecords);
  const normalizedTimeline = normalizeFailureTerminalStages(
    dedupedTimeline,
    turnFlow,
    message,
  );
  return {
    ...turnFlow,
    timeline: normalizedTimeline,
  };
}

export function toTurnFlowFirstChatMessage(message: ChatMessage): ChatMessage {
  const nextMessage = { ...message } as ChatMessage;
  const legacyRecord = message as unknown as Record<string, unknown>;
  projectAssistantFieldsIntoTurnFlow(nextMessage, {
    optimizingTools: normalizeLegacyOptimizingTools(
      legacyRecord.optimizingTools,
    ),
    ragSources: normalizeLegacyRagSources(legacyRecord.ragSources),
    thinkingContent: asString(legacyRecord.thinkingContent),
    toolCalls: normalizeLegacyToolCalls(legacyRecord.toolCalls),
  });
  const nextRecord = nextMessage as unknown as Record<string, unknown>;
  delete nextRecord.thinkingContent;
  delete nextRecord.optimizingTools;
  delete nextRecord.ragSources;
  delete nextRecord.toolCalls;

  const turnFlow = normalizeTurnFlowForDisplay(nextMessage);
  if (!turnFlow) {
    return nextMessage;
  }
  return {
    ...nextMessage,
    turnFlow: turnFlow as unknown as ChatMessage['turnFlow'],
  };
}
