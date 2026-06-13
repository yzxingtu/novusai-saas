import type {
  TurnFlowForDisplay,
  TurnFlowStageForDisplay,
} from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type {
  DisplayReferenceLink,
  TurnAnswerCard,
  TurnEvidenceItem,
} from '#/components/business/ai-chat-panel/types';
import type { ChatMessage, ToolApprovalPresentation } from '#/types/ai-chat';

import {
  isUserFacingTurnEvidence,
  prepareMessageContent,
  selectAnswerCardReferences,
} from '#/components/business/ai-chat-panel/chat-message-display-preparation';
import { getTurnFlowForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import { $t } from '#/locales';

export interface KernelPendingActionState {
  action?: string;
  arguments?: Record<string, unknown>;
  approvalPresentation?: ToolApprovalPresentation;
  autoApproved?: boolean;
  kind: 'confirmation' | 'consent';
  operationDescription?: string;
  operationLabel?: string;
  preview?: Record<string, unknown>;
  rejected?: boolean;
  resolved?: boolean;
  skillName?: string;
  table?: string;
  toolName?: string;
}

export interface TurnFlowState {
  answerCard?: TurnAnswerCard;
  evidence: TurnEvidenceItem[];
  flow: TurnFlowForDisplay;
  hiddenEvidenceCount: number;
  pendingAction?: KernelPendingActionState;
  references: DisplayReferenceLink[];
  selectedEvidence: DisplayReferenceLink[];
  timeline: TurnFlowStageForDisplay[];
}

function normalizeOptionalString(value: unknown) {
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function toFallbackReference(
  evidence: TurnEvidenceItem,
  index: number,
): DisplayReferenceLink {
  const fallbackLabel =
    (evidence.knowledgeBaseName && evidence.docName
      ? `${evidence.knowledgeBaseName} / ${evidence.docName}`
      : undefined) ??
    normalizeOptionalString(evidence.knowledgeBaseName) ??
    normalizeOptionalString(evidence.docName) ??
    normalizeOptionalString(evidence.title) ??
    normalizeOptionalString(evidence.sourceRef) ??
    $t('common.globalAiChat.turnEvidenceFallback', { index: index + 1 });
  return {
    hostLabel: '',
    href: normalizeOptionalString(evidence.url) ?? '',
    id: evidence.id || `turn-flow-evidence-${index}`,
    kind: evidence.kind,
    label: fallbackLabel,
    snippet: evidence.snippet,
    source: 'turn_flow',
  };
}

function sanitizeAnswerCard(
  answerCard: TurnAnswerCard | undefined,
  displayEvidenceIds: Set<string>,
): TurnAnswerCard | undefined {
  if (!answerCard) {
    return undefined;
  }
  return {
    ...answerCard,
    sourceChipIds: (answerCard.sourceChipIds ?? []).filter((id) =>
      displayEvidenceIds.has(id),
    ),
  };
}

function sanitizeTimelineEvidenceRefs(
  timeline: TurnFlowStageForDisplay[],
  displayRetrievalEvidenceIds: Set<string>,
): TurnFlowStageForDisplay[] {
  return timeline.map((stage) => {
    if (stage.type !== 'retrieval') {
      return stage;
    }
    const explicitRefs = (stage.sourceRefs ?? []).filter((id) =>
      displayRetrievalEvidenceIds.has(id),
    );
    const sourceRefs =
      explicitRefs.length > 0 ? explicitRefs : [...displayRetrievalEvidenceIds];
    const sourceCount = sourceRefs.length;
    return {
      ...stage,
      metrics: {
        ...stage.metrics,
        evidence_count: sourceCount,
        source_count: sourceCount,
      },
      sourceRefs,
      ...(sourceCount > 0
        ? {}
        : {
            status: 'skipped' as const,
          }),
    };
  });
}

function buildPendingActionState(
  msg: ChatMessage,
): KernelPendingActionState | undefined {
  if (msg.pendingConfirmation) {
    return {
      action: msg.pendingConfirmation.action,
      approvalPresentation: msg.pendingConfirmation.approvalPresentation,
      kind: 'confirmation',
      preview: msg.pendingConfirmation.preview,
      resolved: msg.pendingConfirmation.resolved,
      table: msg.pendingConfirmation.table,
      toolName: msg.pendingConfirmation.toolName,
    };
  }

  if (msg.pendingConsent) {
    return {
      arguments: msg.pendingConsent.arguments,
      autoApproved: msg.pendingConsent.autoApproved,
      kind: 'consent',
      rejected: msg.pendingConsent.rejected,
      resolved: msg.pendingConsent.resolved,
      skillName: msg.pendingConsent.skillName,
      toolName: msg.pendingConsent.toolName,
    };
  }

  return undefined;
}

export function buildTurnFlowState(msg: ChatMessage): TurnFlowState {
  const flow = getTurnFlowForDisplay(msg);
  const displayEvidence = flow.evidence.filter((item) =>
    isUserFacingTurnEvidence(item),
  );
  const displayEvidenceIds = new Set(displayEvidence.map((item) => item.id));
  const displayRetrievalEvidenceIds = new Set(
    displayEvidence
      .filter((item) => item.kind !== 'tool')
      .map((item) => item.id),
  );
  const timeline = sanitizeTimelineEvidenceRefs(
    flow.timeline,
    displayRetrievalEvidenceIds,
  );
  const answerCard = sanitizeAnswerCard(flow.answerCard, displayEvidenceIds);
  const displayFlow = {
    ...flow,
    answerCard,
    evidence: displayEvidence,
    timeline,
  };
  const preparedMessageContent = prepareMessageContent(msg);
  const references = preparedMessageContent.references.filter(
    (reference) =>
      reference.source !== 'turn_flow' || displayEvidenceIds.has(reference.id),
  );
  const selectedEvidence = selectAnswerCardReferences(
    references,
    answerCard?.sourceChipIds,
  );
  const effectiveSelectedEvidence =
    selectedEvidence.length > 0
      ? selectedEvidence
      : displayEvidence.map((item, index) => toFallbackReference(item, index));

  return {
    answerCard,
    evidence: displayEvidence,
    flow: displayFlow,
    hiddenEvidenceCount: Math.max(
      0,
      references.length - effectiveSelectedEvidence.length,
    ),
    pendingAction: buildPendingActionState(msg),
    references,
    selectedEvidence: effectiveSelectedEvidence,
    timeline,
  };
}
