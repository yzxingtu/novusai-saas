import type {
  TurnFlowForDisplay,
  TurnFlowStageForDisplay,
} from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type {
  DisplayReferenceLink,
  TurnAnswerCard,
  TurnEvidenceItem,
} from '#/components/business/ai-chat-panel/types';
import type { ChatMessage } from '#/types/ai-chat';

import {
  prepareMessageContent,
  selectAnswerCardReferences,
} from '#/components/business/ai-chat-panel/chat-message-display-preparation';
import { getTurnFlowForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';

export interface KernelPendingActionState {
  action?: string;
  arguments?: Record<string, unknown>;
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
    normalizeOptionalString(evidence.title) ??
    normalizeOptionalString(evidence.sourceRef) ??
    `Evidence ${index + 1}`;
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

function buildPendingActionState(
  msg: ChatMessage,
  pendingOps: PendingPageOpForDisplay[],
): KernelPendingActionState | undefined {
  if (msg.pendingConfirmation) {
    const unresolvedPendingOp = pendingOps.find(
      (item) => item.resolved !== true,
    );
    return {
      action: msg.pendingConfirmation.action,
      kind: 'confirmation',
      operationDescription: unresolvedPendingOp?.operationDescription,
      operationLabel: unresolvedPendingOp?.operationLabel,
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

export function buildTurnFlowState(
  msg: ChatMessage,
  pendingOps: PendingPageOpForDisplay[] = [],
): TurnFlowState {
  const flow = getTurnFlowForDisplay(msg);
  const preparedMessageContent = prepareMessageContent(msg);
  const references = preparedMessageContent.references;
  const selectedEvidence = selectAnswerCardReferences(
    references,
    flow.answerCard?.sourceChipIds,
  );
  const effectiveSelectedEvidence =
    selectedEvidence.length > 0
      ? selectedEvidence
      : flow.evidence.map((item, index) => toFallbackReference(item, index));

  return {
    answerCard: flow.answerCard,
    evidence: flow.evidence,
    flow,
    hiddenEvidenceCount: Math.max(
      0,
      references.length - effectiveSelectedEvidence.length,
    ),
    pendingAction: buildPendingActionState(msg, pendingOps),
    references,
    selectedEvidence: effectiveSelectedEvidence,
    timeline: flow.timeline,
  };
}
