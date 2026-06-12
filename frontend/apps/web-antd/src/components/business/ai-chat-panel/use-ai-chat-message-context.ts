import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';

import {
  normalizeOptionalString,
  normalizeStringList,
} from './use-ai-chat-message-normalizers';

export function normalizeRuntimeDiagnosticTokens(value: unknown): string[] {
  const out: string[] = [];
  for (const text of normalizeStringList(value)) {
    if (!out.includes(text)) {
      out.push(text);
    }
  }
  return out;
}

export function normalizeContextSources(
  value: unknown,
): TurnContextSourcePayload[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const normalized: TurnContextSourcePayload[] = [];
  for (const item of value) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const payload = item as Record<string, unknown>;
    const source: TurnContextSourcePayload = {};
    const kind = normalizeOptionalString(payload.kind);
    const name = normalizeOptionalString(payload.name);
    if (kind) {
      source.kind = kind;
    }
    if (name) {
      source.name = name;
    }
    if (typeof payload.active === 'boolean') {
      source.active = payload.active;
    }
    if (payload.metadata && typeof payload.metadata === 'object') {
      source.metadata = payload.metadata as Record<string, unknown>;
    }
    normalized.push(source);
  }
  return normalized;
}

export function normalizeTurnRecord(value: unknown): null | TurnRecordPayload {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const completionReason = normalizeOptionalString(payload.completion_reason);
  const failureKind = normalizeOptionalString(payload.failure_kind);
  const finalStageStatus = normalizeOptionalString(payload.final_stage_status);
  const turnOutcome = normalizeOptionalString(payload.turn_outcome);
  const terminationReason = normalizeOptionalString(payload.termination_reason);
  const protocolPath = normalizeOptionalString(payload.protocol_path);
  const turnFlow =
    payload.turn_flow && typeof payload.turn_flow === 'object'
      ? ({ ...(payload.turn_flow as Record<string, unknown>) } as Record<
          string,
          unknown
        >)
      : undefined;
  const selectedToolNames = normalizeRuntimeDiagnosticTokens(
    payload.selected_tool_names,
  );
  const selectedSkillNames = normalizeRuntimeDiagnosticTokens(
    payload.selected_skill_names,
  );
  const contextSources = normalizeContextSources(payload.context_sources);
  const fallbackHistory = Array.isArray(payload.fallback_history)
    ? payload.fallback_history
        .filter((item): item is Record<string, unknown> => {
          return !!item && typeof item === 'object';
        })
        .map((item) => ({ ...item }))
    : [];
  const metadata =
    payload.metadata && typeof payload.metadata === 'object'
      ? ({ ...(payload.metadata as Record<string, unknown>) } as Record<
          string,
          unknown
        >)
      : undefined;
  return {
    ...(completionReason ? { completion_reason: completionReason } : {}),
    ...(failureKind ? { failure_kind: failureKind } : {}),
    ...(finalStageStatus ? { final_stage_status: finalStageStatus } : {}),
    turn_outcome: turnOutcome,
    termination_reason: terminationReason,
    protocol_path: protocolPath,
    selected_tool_names: selectedToolNames,
    selected_skill_names: selectedSkillNames,
    context_sources: contextSources,
    ...(fallbackHistory.length > 0
      ? { fallback_history: fallbackHistory }
      : {}),
    ...(turnFlow ? { turn_flow: turnFlow } : {}),
    ...(metadata ? { metadata } : {}),
  };
}

const FAILURE_OUTCOMES = new Set(['error', 'failed', 'tool_round_failed']);
const FAILURE_TERMINATIONS = new Set([
  'budget_exit',
  'candidate_tool_budget_exceeded',
  'completion_budget_exceeded',
  'content_filter',
  'elapsed_budget_exceeded',
  'error',
  'failed',
  'incomplete',
  'length',
  'prompt_budget_exceeded',
  'provider_error',
  'provider_failure_after_partial_progress',
  'provider_timeout',
  'provider_unavailable',
  'stream_execution_error',
  'terminal_failure',
  'tool_error',
  'tool_result_budget_exceeded',
  'tool_round_budget_exceeded',
  'tool_round_failed',
  'untrusted_final_output_source',
]);

function isFailureTerminationSignal(value?: string): boolean {
  if (!value) {
    return false;
  }
  if (FAILURE_TERMINATIONS.has(value)) {
    return true;
  }
  return (
    value.startsWith('provider_') ||
    value.includes('error') ||
    value.includes('failed') ||
    value.endsWith('_budget_exceeded')
  );
}

export function isTurnFailure(
  turnOutcome?: string,
  terminationReason?: string,
): boolean {
  const normalizedOutcome = normalizeOptionalString(turnOutcome);
  const normalizedTermination = normalizeOptionalString(terminationReason);
  return (
    (normalizedOutcome ? FAILURE_OUTCOMES.has(normalizedOutcome) : false) ||
    isFailureTerminationSignal(normalizedTermination)
  );
}
