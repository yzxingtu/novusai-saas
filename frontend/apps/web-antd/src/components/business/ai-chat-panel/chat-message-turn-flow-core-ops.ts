import type {
  TurnFlowAnswerCard,
  TurnFlowEvidenceItem,
  TurnFlowStage,
  TurnFlowStageStatus,
  TurnFlowViewModel,
} from './types';

import { $t } from '#/locales';

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
    ...(flow.answerCard ? { answerCard: cloneAnswerCard(flow.answerCard) } : {}),
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
    ...(displayName ? { displayName, title: displayName } : { title: toolName }),
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
