import type { ChatMessage } from './types';

import { visibleRuntimeDiagnosticTokens } from '#/utils/ai-runtime-diagnostics';

const BENIGN_TURN_OUTCOMES = new Set(['partial', 'success']);
const BENIGN_TERMINATION_REASONS = new Set([
  'budget_exit',
  'completed',
  'consent_pause',
  'interrupted',
  'stop',
]);

function normalizeDiagnosticText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function hasActiveContextSources(msg: ChatMessage): boolean {
  return (msg.contextSources ?? []).some((source) => {
    const metadata = source.metadata ?? {};
    return Boolean(
      source.active !== false &&
      (
        normalizeDiagnosticText(source.kind) ||
        normalizeDiagnosticText(source.name) ||
        normalizeDiagnosticText(metadata.name) ||
        normalizeDiagnosticText(metadata.title) ||
        normalizeDiagnosticText(metadata.knowledge_base_name) ||
        normalizeDiagnosticText(metadata.source)
      ),
    );
  });
}

export function hasTurnDiagnosticsData(msg: ChatMessage): boolean {
  const terminationReason =
    normalizeDiagnosticText(msg.terminationReason) ||
    normalizeDiagnosticText(msg.completionReason);
  return Boolean(
    normalizeDiagnosticText(msg.turnOutcome) ||
    terminationReason ||
    normalizeDiagnosticText(msg.protocolPath) ||
    visibleRuntimeDiagnosticTokens(msg.selectedToolNames).length > 0 ||
    visibleRuntimeDiagnosticTokens(msg.selectedSkillNames).length > 0 ||
    hasActiveContextSources(msg),
  );
}

export function shouldRenderTurnDiagnostics(
  msg: ChatMessage,
  diagnosticsEnabled: boolean,
): boolean {
  if (!diagnosticsEnabled || !hasTurnDiagnosticsData(msg) || msg.error) {
    return false;
  }

  if (msg.requestFailedRetry) {
    return true;
  }

  const normalizedOutcome = normalizeDiagnosticText(msg.turnOutcome).toLowerCase();
  if (normalizedOutcome && !BENIGN_TURN_OUTCOMES.has(normalizedOutcome)) {
    return true;
  }

  const normalizedTerminationReason = (
    normalizeDiagnosticText(msg.terminationReason) ||
    normalizeDiagnosticText(msg.completionReason)
  ).toLowerCase();
  return (
    normalizedTerminationReason.length > 0 &&
    !BENIGN_TERMINATION_REASONS.has(normalizedTerminationReason)
  );
}
