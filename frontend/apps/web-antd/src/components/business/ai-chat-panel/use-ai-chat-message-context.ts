import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';

import {
  normalizeOptionalString,
  normalizeStringList,
} from './use-ai-chat-message-normalizers';

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
  const turnOutcome = normalizeOptionalString(payload.turn_outcome);
  const terminationReason = normalizeOptionalString(payload.termination_reason);
  const protocolPath = normalizeOptionalString(payload.protocol_path);
  const selectedToolNames = normalizeStringList(payload.selected_tool_names);
  const selectedSkillNames = normalizeStringList(payload.selected_skill_names);
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
    turn_outcome: turnOutcome,
    termination_reason: terminationReason,
    protocol_path: protocolPath,
    selected_tool_names: selectedToolNames,
    selected_skill_names: selectedSkillNames,
    context_sources: contextSources,
    ...(fallbackHistory.length > 0
      ? { fallback_history: fallbackHistory }
      : {}),
    ...(metadata ? { metadata } : {}),
  };
}

export function isTurnFailure(
  turnOutcome?: string,
  terminationReason?: string,
): boolean {
  const normalizedOutcome = normalizeOptionalString(turnOutcome);
  const normalizedTermination = normalizeOptionalString(terminationReason);
  const failureOutcomes = new Set(['error', 'failed', 'tool_round_failed']);
  const failureTerminations = new Set(['error', 'failed', 'tool_error']);
  return (
    (normalizedOutcome ? failureOutcomes.has(normalizedOutcome) : false) ||
    (normalizedTermination
      ? failureTerminations.has(normalizedTermination)
      : false)
  );
}
