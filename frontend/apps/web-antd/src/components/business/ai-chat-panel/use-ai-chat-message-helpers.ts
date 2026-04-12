import type {
  ActionButton,
  AgentItem,
  ChatMessage,
  PendingConfirmation,
  PendingConsent,
  RagSource,
  ToolCallEvent,
} from './types';

import type {
  RawMessageItem,
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

import { normalizeChatAttachments } from '#/api/shared/ai-chat';
import { $t } from '#/locales';

function normalizeMergedTextPart(value: null | string | undefined): string {
  return String(value ?? '').replace(/\r\n/g, '\n').trim();
}

function appendDistinctMergedTextPart(
  parts: string[],
  value: null | string | undefined,
): void {
  const normalized = normalizeMergedTextPart(value);
  if (!normalized) {
    return;
  }
  const previous = parts.length > 0 ? parts[parts.length - 1] : undefined;
  if (normalizeMergedTextPart(previous) === normalized) {
    return;
  }
  parts.push(String(value ?? ''));
}

function resolveToolCallStatus(
  response: undefined | { success: boolean },
  persistedTc: Record<string, unknown>,
): ToolCallEvent['status'] {
  if (response) {
    return response.success ? 'success' : 'error';
  }
  if (persistedTc.pending_confirmation || persistedTc.pending_consent) {
    return 'running';
  }
  if (persistedTc.success === true) {
    return 'success';
  }
  return 'error';
}

export function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? '').trim())
    .filter((item) => item.length > 0);
}

export function normalizeOptionalString(
  value: unknown,
): string | undefined {
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function resolvePersistedAssistantError(
  metadata: null | Record<string, unknown>,
  fallbackContent: string,
): null | { appError: AppErrorInfo; errorOnly: boolean } {
  if (!metadata || metadata.error !== true) {
    return null;
  }

  const messageText =
    normalizeOptionalString(metadata.error_message) ||
    normalizeOptionalString(fallbackContent) ||
    $t('common.http.internalServerError');
  const debugMessage =
    normalizeOptionalString(metadata.error_debug_message) ||
    normalizeOptionalString(metadata.raw_error_message);
  const traceId = normalizeOptionalString(metadata.error_trace_id);
  const errorType = normalizeOptionalString(metadata.error_type);

  return {
    appError: {
      code: errorType,
      debugMessage,
      message: messageText,
      raw: metadata,
      source: 'sse',
      traceId,
    },
    errorOnly: metadata.error_only !== false,
  };
}

const NATIVE_WEB_SEARCH_PROVIDER = 'native_hosted';
const NATIVE_WEB_SEARCH_TOOL_NAME = 'native_web_search';

export function normalizeObjectRecord(
  value: unknown,
): null | Record<string, unknown> {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return { ...(value as Record<string, unknown>) };
}

function normalizeObjectRecordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => {
      return !!item && typeof item === 'object';
    })
    .map((item) => ({ ...item }));
}

function buildNativeSearchSummaryPayload(
  status: ToolCallEvent['status'],
): Record<string, unknown> {
  return {
    provider: NATIVE_WEB_SEARCH_PROVIDER,
    ...(status === 'success' ? { status: 'success' } : {}),
  };
}

function hasConcreteWebSearchToolCall(
  toolCalls?: ToolCallEvent[],
): boolean {
  return Boolean(toolCalls?.some((toolCall) => toolCall.name === 'web_search'));
}

export function removeNativeSearchToolCall(
  toolCalls?: ToolCallEvent[],
): undefined | ToolCallEvent[] {
  if (!toolCalls?.length) {
    return toolCalls;
  }
  const filtered = toolCalls.filter(
    (toolCall) => toolCall.name !== NATIVE_WEB_SEARCH_TOOL_NAME,
  );
  return filtered.length === toolCalls.length ? toolCalls : filtered;
}

export function upsertNativeSearchToolCall(
  toolCalls: undefined | ToolCallEvent[],
  status: Extract<ToolCallEvent['status'], 'running' | 'success'>,
): ToolCallEvent[] {
  const nextToolCalls = [...(toolCalls ?? [])];
  if (hasConcreteWebSearchToolCall(nextToolCalls)) {
    return nextToolCalls;
  }

  const existing = nextToolCalls.findLast(
    (toolCall) => toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME,
  );
  if (existing) {
    existing.displayName =
      existing.displayName || $t('common.globalAiChat.toolNativeSearch');
    existing.status = status;
    if (status === 'running' && !existing.startedAt) {
      existing.startedAt = Date.now();
    }
    existing.summaryPayload = {
      ...(existing.summaryPayload ?? {}),
      ...buildNativeSearchSummaryPayload(status),
    };
    return nextToolCalls;
  }

  nextToolCalls.push({
    displayName: $t('common.globalAiChat.toolNativeSearch'),
    name: NATIVE_WEB_SEARCH_TOOL_NAME,
    startedAt: status === 'running' ? Date.now() : undefined,
    status,
    summaryPayload: buildNativeSearchSummaryPayload(status),
  });
  return nextToolCalls;
}

export function finalizeNativeSearchToolCall(
  toolCalls: undefined | ToolCallEvent[],
): undefined | ToolCallEvent[] {
  if (!toolCalls?.length || hasConcreteWebSearchToolCall(toolCalls)) {
    return toolCalls;
  }
  const runningNativeTool = toolCalls.findLast(
    (toolCall) =>
      toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
      toolCall.status === 'running',
  );
  if (!runningNativeTool) {
    return toolCalls;
  }
  return upsertNativeSearchToolCall(toolCalls, 'success');
}

function markNativeSearchToolCallError(
  toolCalls: undefined | ToolCallEvent[],
): undefined | ToolCallEvent[] {
  if (!toolCalls?.length || hasConcreteWebSearchToolCall(toolCalls)) {
    return toolCalls;
  }
  const runningNativeTool = toolCalls.findLast(
    (toolCall) =>
      toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
      toolCall.status === 'running',
  );
  if (!runningNativeTool) {
    return toolCalls;
  }

  runningNativeTool.displayName =
    runningNativeTool.displayName || $t('common.globalAiChat.toolNativeSearch');
  runningNativeTool.status = 'error';
  runningNativeTool.summaryPayload = {
    ...(runningNativeTool.summaryPayload ?? {}),
    provider: NATIVE_WEB_SEARCH_PROVIDER,
    status: 'error',
  };
  return toolCalls;
}

function hasNativeSearchProgressSignal(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }
  const metadata = normalizeObjectRecord(payload.metadata);
  const progressKinds = [
    ...normalizeStringList(payload.stream_progress_kinds),
    ...normalizeStringList(metadata?.stream_progress_kinds),
  ];
  if (
    progressKinds.includes('web_search_in_progress') ||
    progressKinds.includes('native_search_in_progress')
  ) {
    return true;
  }
  if (!metadata) {
    return false;
  }
  if (metadata.native_search_progress === true) {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search_status) === 'running') {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search) === 'running') {
    return true;
  }
  if (normalizeOptionalString(metadata.native_search_state) === 'running') {
    return true;
  }
  return normalizeObjectRecordList(payload.provider_events).some((item) => {
    const itemMetadata = normalizeObjectRecord(item.metadata);
    return (
      normalizeOptionalString(itemMetadata?.auto_fetch_gate_reason) ===
      'native_search_running'
    );
  });
}

function hasIntentPlanNativeSearchCompletion(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }

  const metadata = normalizeObjectRecord(payload.metadata);
  const intentPlanItems = [
    ...normalizeObjectRecordList(payload.intent_plan),
    ...normalizeObjectRecordList(metadata?.intent_plan),
  ];

  return intentPlanItems.some((item) => {
    const completedTools = normalizeStringList(item.completed_by_tool_names);
    return (
      completedTools.includes(NATIVE_WEB_SEARCH_TOOL_NAME) ||
      completedTools.includes('web_search')
    );
  });
}

function hasNativeSearchCompletionSignal(value: unknown): boolean {
  const payload = normalizeObjectRecord(value);
  if (!payload) {
    return false;
  }
  const metadata = normalizeObjectRecord(payload.metadata);
  if (metadata) {
    if (metadata.native_search_completed === true) {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search_status) === 'success') {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search) === 'success') {
      return true;
    }
    if (normalizeOptionalString(metadata.native_search_state) === 'success') {
      return true;
    }
  }
  if (hasIntentPlanNativeSearchCompletion(payload)) {
    return true;
  }
  return normalizeObjectRecordList(payload.intent_plan).some((item) => {
    const itemMetadata = normalizeObjectRecord(item.metadata);
    return (
      normalizeOptionalString(itemMetadata?.auto_fetch_gate_reason) ===
      'native_search_completed'
    );
  });
}

export function resolveNativeSearchToolStatus(
  ...sources: unknown[]
): null | Extract<ToolCallEvent['status'], 'running' | 'success'> {
  let sawProgress = false;
  for (const source of sources) {
    if (hasNativeSearchCompletionSignal(source)) {
      return 'success';
    }
    if (hasNativeSearchProgressSignal(source)) {
      sawProgress = true;
    }
  }
  return sawProgress ? 'running' : null;
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

export function normalizeTurnRecord(
  value: unknown,
): null | TurnRecordPayload {
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

/**
 * Merge raw DB messages into display ChatMessages / 将原始 DB 消息合并为展示用 ChatMessages
 *
 * During streaming, all tool call rounds are accumulated into a single
 * assistant ChatMessage. But the DB stores each round as separate messages:
 *   assistant (tool_calls) → tool → assistant (tool_calls) → tool → ... → assistant (final content)
 *
 * This function groups consecutive non-user messages between user messages
 * into a single ChatMessage with toolCalls reconstructed.
 */
export function mergeMessagesForDisplay(
  rawMessages: RawMessageItem[],
  agents: AgentItem[] = [],
): ChatMessage[] {
  // Filter out system messages / 过滤 system 消息
  const filtered = rawMessages.filter((m) => m.role !== 'system');
  if (filtered.length === 0) return [];

  const result: ChatMessage[] = [];

  // Collect tool responses keyed by tool_call_id for quick lookup / 按 tool_call_id 索引 tool 回包
  const toolResponseMap = new Map<
    string,
    {
      content: string;
      displayName?: string;
      error?: string;
      errorType?: string;
      name?: string;
      resultLink?: string;
      success: boolean;
      summary?: string;
      summaryPayload?: Record<string, unknown>;
    }
  >();
  for (const m of filtered) {
    if (m.role === 'tool' && m.tool_call_id) {
      const meta = (m.metadata ?? {}) as Record<string, unknown>;
      const toolSuccess = meta.tool_success !== false; // default true for legacy data
      toolResponseMap.set(m.tool_call_id, {
        content: m.content ?? '',
        success: toolSuccess,
        error: (meta.tool_error as string) || undefined,
        errorType: (meta.tool_error_type as string) || undefined,
        name: m.tool_name ?? undefined,
        displayName: (meta.tool_display_name as string) || undefined,
        summary: (meta.tool_summary as string) || undefined,
        summaryPayload:
          (meta.tool_summary_payload as Record<string, unknown>) || undefined,
        resultLink: (meta.tool_result_link as string) || undefined,
      });
    }
  }

  // Group consecutive non-user messages into assistant turns / 合并连续非 user 为助手轮次
  let i = 0;
  while (i < filtered.length) {
    const msg = filtered[i];
    if (!msg) break;

    if (msg.role === 'user') {
      result.push({
        clientKey: `persisted-user-${i}-${msg.created_at ?? ''}`,
        role: 'user',
        content: msg.content ?? '',
        attachments: normalizeChatAttachments(msg.metadata?.attachments),
        ...(msg.created_at ? { created_at: msg.created_at } : {}),
      });
      i++;
      continue;
    }

    // Collect all consecutive non-user messages as one assistant turn / 单轮助手合并多条消息
    const toolCalls: ToolCallEvent[] = [];
    const contentParts: string[] = [];
    const thinkingContentParts: string[] = [];
    let hasMemoryUpdated = false;
    let hasPartial = false;
    let hasInterrupted = false;
    let turnCompletionReason: string | undefined;
    let turnTerminationReason: string | undefined;
    let turnOutcome: string | undefined;
    let turnProtocolPath: string | undefined;
    let turnSelectedSkillNames: string[] = [];
    let turnSelectedToolNames: string[] = [];
    let turnContextSources: TurnContextSourcePayload[] = [];
    let turnRecordPayload: null | TurnRecordPayload = null;
    let turnContextDiagnosticsRaw: null | Record<string, unknown> = null;
    let turnLastRunSummaryRaw: null | Record<string, unknown> = null;
    let turnRecordRaw: null | Record<string, unknown> = null;
    let turnAgentId: null | number = null;
    let turnAgentName: null | string = null;
    let turnAgentAvatar: null | string = null;
    let turnAgentDescription: null | string = null;
    let turnModelName: null | string = null;
    let turnRouteSource: null | string = null;
    let turnCreatedAt: null | string = null;
    let turnRagSources: RagSource[] | undefined;
    let turnActionButtons: ActionButton[] | undefined;
    let turnActionButtonsUsed = false;
    let turnPendingConfirmation: PendingConfirmation | undefined;
    let turnPendingConsent: PendingConsent | undefined;
    let turnPersistedError: AppErrorInfo | undefined;
    let turnPersistedErrorOnly = false;
    const startIdx = i;

    while (i < filtered.length) {
      const current = filtered[i];
      if (!current || current.role === 'user') {
        break;
      }
      const cur = current;

      if (cur.role === 'assistant') {
        const assistantMetadata = normalizeObjectRecord(cur.metadata);
        const persistedErrorState = resolvePersistedAssistantError(
          assistantMetadata,
          cur.content ?? '',
        );
        if (persistedErrorState) {
          turnPersistedError = persistedErrorState.appError;
          turnPersistedErrorOnly =
            turnPersistedErrorOnly || persistedErrorState.errorOnly;
        }
        if (cur.created_at) turnCreatedAt = cur.created_at;
        // Capture agent info from the first assistant message in this turn / 本轮首条 assistant 取 agent 信息
        if (turnAgentId === null && cur.agent_id) {
          turnAgentId = cur.agent_id;
          turnAgentName = cur.agent_name ?? null;
          turnAgentAvatar = cur.agent_avatar ?? null;
          // Enrich from agents list / 从已加载 agents 列表补全描述等
          const agentInfo = agents.find((a) => a.id === cur.agent_id);
          if (agentInfo) {
            turnAgentDescription = agentInfo.description ?? null;
            if (!turnModelName) {
              turnModelName = agentInfo.model_name ?? null;
            }
            if (!turnAgentAvatar && agentInfo.avatar) {
              turnAgentAvatar = agentInfo.avatar;
            }
          }
        }
        if (turnModelName === null) {
          turnModelName =
            cur.model_name ??
            (typeof assistantMetadata?.model_name === 'string'
              ? assistantMetadata.model_name
              : null);
        }
        if (
          turnRouteSource === null &&
          typeof assistantMetadata?.route_source === 'string'
        ) {
          turnRouteSource = assistantMetadata.route_source;
        }
        if (Array.isArray(assistantMetadata?.action_buttons)) {
          turnActionButtons = assistantMetadata.action_buttons as ActionButton[];
        }
        if (assistantMetadata?.action_buttons_used === true) {
          turnActionButtonsUsed = true;
        }
        if (
          !turnPendingConfirmation &&
          assistantMetadata?.pending_confirmation &&
          typeof assistantMetadata.pending_confirmation === 'object'
        ) {
          const pending = assistantMetadata.pending_confirmation as Record<
            string,
            unknown
          >;
          turnPendingConfirmation = {
            action: String(pending.action || ''),
            table: String(pending.table || ''),
            preview: pending.preview as Record<string, unknown> | undefined,
            toolName: String(pending.tool_name || pending.toolName || ''),
            resolved: pending.resolved as boolean | undefined,
          };
        }
        if (
          !turnPendingConsent &&
          assistantMetadata?.pending_consent &&
          typeof assistantMetadata.pending_consent === 'object'
        ) {
          const pending = assistantMetadata.pending_consent as Record<
            string,
            unknown
          >;
          turnPendingConsent = {
            toolName: String(pending.tool_name || pending.toolName || ''),
            arguments: pending.arguments as
              | Record<string, unknown>
              | undefined,
            skillName: (pending.skill_name as string) || undefined,
            skillType: (pending.package_name as string) || undefined,
            resolved: pending.resolved as boolean | undefined,
            rejected: pending.rejected as boolean | undefined,
            autoApproved:
              (pending.auto_approved as boolean | undefined) ??
              (pending.autoApproved as boolean | undefined),
          };
        }
        // Extract tool calls from this assistant message / 解析本条的 tool_calls
        if (cur.tool_calls && cur.tool_calls.length > 0) {
          for (const tc of cur.tool_calls) {
            const tcId = tc.id ?? '';
            const funcName = tc.function?.name ?? 'unknown';
            const persistedTc = tc as Record<string, unknown>;
            let parsedArgs: Record<string, unknown> | undefined;
            try {
              parsedArgs = tc.function?.arguments
                ? JSON.parse(tc.function.arguments)
                : undefined;
            } catch {
              parsedArgs = tc.function?.arguments
                ? { raw: tc.function.arguments }
                : undefined;
            }

            // Match with tool response (use metadata.tool_success for status) / 与 tool 回包对齐状态
            const response = tcId ? toolResponseMap.get(tcId) : undefined;

            if (
              !turnPendingConfirmation &&
              persistedTc.pending_confirmation &&
              typeof persistedTc.pending_confirmation === 'object'
            ) {
              const pending = persistedTc.pending_confirmation as Record<
                string,
                unknown
              >;
              turnPendingConfirmation = {
                action: String(pending.action || ''),
                table: String(pending.table || ''),
                preview: pending.preview as
                  | Record<string, unknown>
                  | undefined,
                toolName: String(
                  pending.tool_name || pending.toolName || funcName,
                ),
              };
            }
            if (
              !turnPendingConsent &&
              persistedTc.pending_consent &&
              typeof persistedTc.pending_consent === 'object'
            ) {
              const pending = persistedTc.pending_consent as Record<
                string,
                unknown
              >;
              turnPendingConsent = {
                toolName: String(
                  pending.tool_name || pending.toolName || funcName,
                ),
                arguments:
                  (pending.arguments as
                    | Record<string, unknown>
                    | undefined) ?? parsedArgs,
                skillName: (pending.skill_name as string) || undefined,
                skillType: (pending.package_name as string) || undefined,
              };
            }

            toolCalls.push({
              id: tcId || undefined,
              name: funcName,
              status: resolveToolCallStatus(response, persistedTc),
              arguments: parsedArgs,
              output: response?.success
                ? response.content
                : (persistedTc.output as string | undefined),
              error:
                response && !response.success
                  ? response.error || response.content
                  : (persistedTc.error as string | undefined) ||
                    response?.error,
              durationMs: persistedTc.duration_ms as number | undefined,
              displayName:
                (persistedTc.display_name as string) ?? response?.displayName,
              summary: (persistedTc.summary as string) ?? response?.summary,
              summaryPayload:
                (persistedTc.summary_payload as Record<string, unknown>) ??
                response?.summaryPayload,
              resultLink:
                (persistedTc.result_link as string) ?? response?.resultLink,
              errorType:
                (persistedTc.error_type as string) ?? response?.errorType,
              skillName:
                (persistedTc.skill_name as string) ??
                (persistedTc.package_name as string) ??
                undefined,
            });
          }
        }

        // Check memory_updated flag in metadata / 检查 metadata 记忆更新标记
        if (assistantMetadata?.memory_updated) {
          hasMemoryUpdated = true;
        }
        turnContextDiagnosticsRaw =
          normalizeObjectRecord(assistantMetadata?.context_diagnostics) ??
          turnContextDiagnosticsRaw;
        turnLastRunSummaryRaw =
          normalizeObjectRecord(assistantMetadata?.last_run_summary) ??
          turnLastRunSummaryRaw;
        turnRecordRaw =
          normalizeObjectRecord(assistantMetadata?.turn_record) ??
          turnRecordRaw;
        const turnRecord = normalizeTurnRecord(assistantMetadata?.turn_record);
        if (turnRecord) {
          turnRecordPayload = turnRecord;
        }
        const metadataTurnOutcome = normalizeOptionalString(
          assistantMetadata?.turn_outcome,
        );
        if (!turnOutcome && metadataTurnOutcome) {
          turnOutcome = metadataTurnOutcome;
        }
        if (!turnOutcome && turnRecord?.turn_outcome) {
          turnOutcome = turnRecord.turn_outcome;
        }
        const metadataTerminationReason = normalizeOptionalString(
          assistantMetadata?.termination_reason,
        );
        if (!turnTerminationReason && metadataTerminationReason) {
          turnTerminationReason = metadataTerminationReason;
        }
        if (!turnTerminationReason && turnRecord?.termination_reason) {
          turnTerminationReason = turnRecord.termination_reason;
        }
        const metadataProtocolPath = normalizeOptionalString(
          assistantMetadata?.protocol_path,
        );
        if (!turnProtocolPath && metadataProtocolPath) {
          turnProtocolPath = metadataProtocolPath;
        }
        if (!turnProtocolPath && turnRecord?.protocol_path) {
          turnProtocolPath = turnRecord.protocol_path;
        }
        const metadataSelectedToolNames = normalizeStringList(
          assistantMetadata?.selected_tool_names,
        );
        if (metadataSelectedToolNames.length > 0) {
          turnSelectedToolNames = metadataSelectedToolNames;
        } else if (
          turnSelectedToolNames.length === 0 &&
          (turnRecord?.selected_tool_names?.length ?? 0) > 0
        ) {
          turnSelectedToolNames = [
            ...(turnRecord?.selected_tool_names ?? []),
          ];
        }
        const metadataSelectedSkillNames = normalizeStringList(
          assistantMetadata?.selected_skill_names,
        );
        if (metadataSelectedSkillNames.length > 0) {
          turnSelectedSkillNames = metadataSelectedSkillNames;
        } else if (
          turnSelectedSkillNames.length === 0 &&
          (turnRecord?.selected_skill_names?.length ?? 0) > 0
        ) {
          turnSelectedSkillNames = [
            ...(turnRecord?.selected_skill_names ?? []),
          ];
        }
        const metadataContextSources = normalizeContextSources(
          assistantMetadata?.context_sources,
        );
        if (metadataContextSources.length > 0) {
          turnContextSources = metadataContextSources;
        } else if (
          turnContextSources.length === 0 &&
          (turnRecord?.context_sources?.length ?? 0) > 0
        ) {
          turnContextSources = [...(turnRecord?.context_sources ?? [])];
        }
        if (
          !persistedErrorState?.errorOnly &&
          (assistantMetadata?.partial || turnOutcome === 'partial')
        ) {
          hasPartial = true;
        }
        if (
          !persistedErrorState?.errorOnly &&
          (assistantMetadata?.interrupted ||
            turnTerminationReason === 'interrupted')
        ) {
          hasInterrupted = true;
        }
        if (hasInterrupted) {
          hasPartial = true;
        }
        if (assistantMetadata?.completion_reason) {
          turnCompletionReason = assistantMetadata.completion_reason as string;
        }
        if (!turnCompletionReason && turnTerminationReason) {
          turnCompletionReason = turnTerminationReason;
        }
        const persistedThinking =
          typeof assistantMetadata?.thinking_content === 'string'
            ? assistantMetadata.thinking_content
            : '';
        if (persistedThinking.trim()) {
          appendDistinctMergedTextPart(thinkingContentParts, persistedThinking);
        }

        // Accumulate content from all assistant messages in this turn / 拼接本轮所有 assistant 正文
        // (matches streaming behavior where all deltas are concatenated) / 与流式增量拼接行为一致
        if (cur.content && cur.content.trim()) {
          if (persistedErrorState?.errorOnly) {
            i++;
            continue;
          }
          // Backward-compat: recover thinking from assistant.content when metadata lacks thinking_content / 向后兼容：旧轮次将思考写入 content，此处恢复为思考块以便历史展示
          if (cur.tool_calls?.length) {
            if (!persistedThinking.trim()) {
              appendDistinctMergedTextPart(thinkingContentParts, cur.content);
            }
          } else {
            appendDistinctMergedTextPart(contentParts, cur.content);
          }
        }
        const rs = assistantMetadata?.rag_sources;
        if (Array.isArray(rs) && rs.length > 0) {
          turnRagSources = rs as RagSource[];
        }
      }
      // tool messages are already handled via toolResponseMap / tool 行已由 Map 处理
      i++;
    }

    // Only add if we actually processed something / 确有内容再推入助手消息
    if (i > startIdx) {
      const nativeSearchStatus = resolveNativeSearchToolStatus(
        turnContextDiagnosticsRaw,
        turnLastRunSummaryRaw,
        turnRecordRaw,
      );
      let mergedToolCalls = nativeSearchStatus
        ? upsertNativeSearchToolCall(toolCalls, nativeSearchStatus)
        : toolCalls;
      const hasPendingNativeSearchTool = mergedToolCalls.some(
        (toolCall) =>
          toolCall.name === NATIVE_WEB_SEARCH_TOOL_NAME &&
          toolCall.status === 'running',
      );
      if (hasPendingNativeSearchTool) {
        const shouldFinalizeNativeSearchAsSuccess =
          turnSelectedToolNames.includes('web_search') ||
          (!hasPartial &&
            !hasInterrupted &&
            !isTurnFailure(
              turnOutcome,
              turnTerminationReason ?? turnCompletionReason,
            ));
        mergedToolCalls =
          (shouldFinalizeNativeSearchAsSuccess
            ? finalizeNativeSearchToolCall(mergedToolCalls)
            : markNativeSearchToolCallError(mergedToolCalls)) ?? [];
      }
      const assistantMsg: ChatMessage = {
        clientKey: `persisted-assistant-${startIdx}-${turnCreatedAt ?? ''}`,
        role: 'assistant',
        content: turnPersistedErrorOnly ? '' : contentParts.join('\n\n'),
        toolCalls: mergedToolCalls.length > 0 ? mergedToolCalls : undefined,
        agent_id: turnAgentId,
        agent_name: turnAgentName,
        agent_avatar: turnAgentAvatar,
        agent_description: turnAgentDescription,
        model_name: turnModelName,
        routeSource: turnRouteSource,
      };
      if (turnRouteSource === 'rich_text_ai') {
        assistantMsg.source = 'rich_text_ai';
      }
      if (turnCreatedAt) assistantMsg.created_at = turnCreatedAt;
      if (hasMemoryUpdated) {
        assistantMsg.memoryUpdated = true;
      }
      if (hasPartial) {
        assistantMsg.partial = true;
      }
      if (hasInterrupted) {
        assistantMsg.interrupted = true;
      }
      if (turnOutcome) {
        assistantMsg.turnOutcome = turnOutcome;
      }
      if (turnTerminationReason) {
        assistantMsg.terminationReason = turnTerminationReason;
      }
      if (turnProtocolPath) {
        assistantMsg.protocolPath = turnProtocolPath;
      }
      if (turnSelectedToolNames.length > 0) {
        assistantMsg.selectedToolNames = turnSelectedToolNames;
      }
      if (turnSelectedSkillNames.length > 0) {
        assistantMsg.selectedSkillNames = turnSelectedSkillNames;
      }
      if (turnContextSources.length > 0) {
        assistantMsg.contextSources = turnContextSources;
      }
      if (turnRecordPayload) {
        assistantMsg.turnRecord = turnRecordPayload;
      }
      if (turnCompletionReason) {
        assistantMsg.completionReason = turnCompletionReason;
      }
      if (
        isTurnFailure(
          turnOutcome,
          turnTerminationReason ?? turnCompletionReason,
        )
      ) {
        assistantMsg.requestFailedRetry = true;
      }
      if (turnPersistedError) {
        assistantMsg.error = turnPersistedError;
        assistantMsg.requestFailedRetry = true;
      }
      if (thinkingContentParts.length > 0) {
        assistantMsg.thinkingContent = thinkingContentParts.join('\n\n');
      }
      if (turnRagSources?.length) {
        assistantMsg.ragSources = turnRagSources;
      }
      if (turnActionButtons?.length) {
        assistantMsg.actionButtons = turnActionButtons;
      }
      if (turnActionButtonsUsed === true) {
        assistantMsg.actionButtonsUsed = true;
      }
      if (turnPendingConfirmation) {
        assistantMsg.pendingConfirmation = turnPendingConfirmation;
      }
      if (turnPendingConsent) {
        assistantMsg.pendingConsent = turnPendingConsent;
      }
      if (turnPersistedErrorOnly) {
        delete assistantMsg.partial;
        delete assistantMsg.interrupted;
      }
      result.push(assistantMsg);
    }
  }

  return result;
}
