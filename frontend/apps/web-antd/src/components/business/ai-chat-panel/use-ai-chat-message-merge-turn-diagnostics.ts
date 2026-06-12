import type { AssistantTurnMergeState } from './use-ai-chat-message-merge-turn-state';

import {
  normalizeContextSources,
  normalizeRuntimeDiagnosticTokens,
  normalizeTurnRecord,
} from './use-ai-chat-message-context';
import {
  normalizeObjectRecord,
  normalizeOptionalString,
} from './use-ai-chat-message-normalizers';

export function collectTurnDiagnostics(
  state: AssistantTurnMergeState,
  assistantMetadata: null | Record<string, unknown>,
) {
  state.turnContextDiagnosticsRaw =
    normalizeObjectRecord(assistantMetadata?.context_diagnostics) ??
    state.turnContextDiagnosticsRaw;
  state.turnLastRunSummaryRaw =
    normalizeObjectRecord(assistantMetadata?.last_run_summary) ??
    state.turnLastRunSummaryRaw;
  state.turnRecordRaw =
    normalizeObjectRecord(assistantMetadata?.turn_record) ??
    state.turnRecordRaw;

  const turnRecord = normalizeTurnRecord(assistantMetadata?.turn_record);
  if (turnRecord) {
    state.turnRecordPayload = turnRecord;
  }

  const metadataCompletionReason = normalizeOptionalString(
    assistantMetadata?.completion_reason,
  );
  if (!state.turnCompletionReason && metadataCompletionReason) {
    state.turnCompletionReason = metadataCompletionReason;
  }
  if (!state.turnCompletionReason && turnRecord?.completion_reason) {
    state.turnCompletionReason = turnRecord.completion_reason;
  }

  const metadataTurnOutcome = normalizeOptionalString(
    assistantMetadata?.turn_outcome,
  );
  if (!state.turnOutcome && metadataTurnOutcome) {
    state.turnOutcome = metadataTurnOutcome;
  }
  if (!state.turnOutcome && turnRecord?.turn_outcome) {
    state.turnOutcome = turnRecord.turn_outcome;
  }

  const metadataTerminationReason = normalizeOptionalString(
    assistantMetadata?.termination_reason,
  );
  if (!state.turnTerminationReason && metadataTerminationReason) {
    state.turnTerminationReason = metadataTerminationReason;
  }
  if (!state.turnTerminationReason && turnRecord?.termination_reason) {
    state.turnTerminationReason = turnRecord.termination_reason;
  }

  const metadataProtocolPath = normalizeOptionalString(
    assistantMetadata?.protocol_path,
  );
  if (!state.turnProtocolPath && metadataProtocolPath) {
    state.turnProtocolPath = metadataProtocolPath;
  }
  if (!state.turnProtocolPath && turnRecord?.protocol_path) {
    state.turnProtocolPath = turnRecord.protocol_path;
  }

  const metadataSelectedToolNames = normalizeRuntimeDiagnosticTokens(
    assistantMetadata?.selected_tool_names,
  );
  if (metadataSelectedToolNames.length > 0) {
    state.turnSelectedToolNames = metadataSelectedToolNames;
  } else if (
    state.turnSelectedToolNames.length === 0 &&
    (turnRecord?.selected_tool_names?.length ?? 0) > 0
  ) {
    state.turnSelectedToolNames = [...(turnRecord?.selected_tool_names ?? [])];
  }

  const metadataSelectedSkillNames = normalizeRuntimeDiagnosticTokens(
    assistantMetadata?.selected_skill_names,
  );
  if (metadataSelectedSkillNames.length > 0) {
    state.turnSelectedSkillNames = metadataSelectedSkillNames;
  } else if (
    state.turnSelectedSkillNames.length === 0 &&
    (turnRecord?.selected_skill_names?.length ?? 0) > 0
  ) {
    state.turnSelectedSkillNames = [
      ...(turnRecord?.selected_skill_names ?? []),
    ];
  }

  const metadataContextSources = normalizeContextSources(
    assistantMetadata?.context_sources,
  );
  if (metadataContextSources.length > 0) {
    state.turnContextSources = metadataContextSources;
  } else if (
    state.turnContextSources.length === 0 &&
    (turnRecord?.context_sources?.length ?? 0) > 0
  ) {
    state.turnContextSources = [...(turnRecord?.context_sources ?? [])];
  }
}
