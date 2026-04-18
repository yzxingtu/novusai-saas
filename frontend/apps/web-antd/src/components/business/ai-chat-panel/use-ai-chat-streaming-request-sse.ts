import type { StreamRequestDeps } from './use-ai-chat-streaming-request';
import type { StreamRequestLifecycle } from './use-ai-chat-streaming-request-lifecycle';

import { nextTick } from 'vue';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';
import { addConsent } from '#/utils/ai-consent';
import { normalizeSseEventError } from '#/utils/request';

import {
  formatKnowledgeBaseName,
  formatLocalizedList,
} from './display-formatters';
import {
  applyCanonicalDoneEvent,
  applyCanonicalTurnAnswerCardEvent,
  applyCanonicalTurnEvidenceEvent,
  applyCanonicalTurnStageEvent,
  finalizeNativeSearchToolCall,
  isTurnFailure,
  normalizeContextSources,
  normalizeObjectRecord,
  normalizeOptionalString,
  normalizeStringList,
  normalizeTurnRecord,
  reconcileTurnFlowWithLegacy,
  removeNativeSearchToolCall,
  resolveNativeSearchToolStatus,
  upsertNativeSearchToolCall,
} from './use-ai-chat-message-helpers';

export async function parseSSEEvents(
  rawChunk: string,
  buffer: { value: string },
  handler: (data: string) => void,
) {
  buffer.value += rawChunk;
  const lines = buffer.value.split('\n');
  buffer.value = lines.pop() ?? '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('data: ')) {
      const data = trimmed.slice(6);
      handler(data);
      if (data === '[DONE]') continue;
      let needFlush = false;
      try {
        const ev = JSON.parse(data) as { event?: string };
        needFlush =
          ev.event === 'message' ||
          ev.event === 'thinking' ||
          ev.event === 'turn_answer_card' ||
          ev.event === 'turn_evidence' ||
          ev.event === 'turn_stage' ||
          ev.event === 'turn_stage_update';
      } catch {
        needFlush = true;
      }
      if (needFlush) await nextTick();
    }
  }
}

function isDraftClearContentEventAllowed(messageItem: {
  error?: unknown;
  streaming?: boolean;
  turnFlow?: unknown;
}): boolean {
  if (messageItem.streaming !== true || messageItem.error) {
    return false;
  }
  const turnFlowRecord = normalizeObjectRecord(messageItem.turnFlow);
  return !(
    turnFlowRecord?.complete === true ||
    turnFlowRecord?.turn_flow_complete === true
  );
}

function resolveToolCallEventId(
  event: Record<string, unknown>,
): string | undefined {
  return normalizeOptionalString(
    event.tool_call_id ?? event.toolCallId ?? event.id,
  );
}

export function createStreamSseHandler(
  deps: StreamRequestDeps,
  lifecycle: StreamRequestLifecycle,
) {
  return function handleSsePayload(data: string) {
    if (data === '[DONE]') return;
    try {
      lifecycle.hasReceivedStreamPayload = true;
      const event = JSON.parse(data) as Record<string, unknown> & {
        delta?: string;
        event?: string;
      };
      const msg = lifecycle.getAssistantMessage();
      if (!msg) return;
      if (lifecycle.didTerminalizeMessage) {
        return;
      }

      switch (event.event) {
        case 'clear_content': {
          if (!isDraftClearContentEventAllowed(msg)) {
            break;
          }
          msg.content = '';
          reconcileTurnFlowWithLegacy(msg);
          break;
        }
        case 'optimizing_tools': {
          msg.optimizingTools = {
            total: (event.total as number) || 0,
            selected: (event.selected as number) || 0,
          };
          reconcileTurnFlowWithLegacy(msg);
          deps.scrollToBottom();
          break;
        }
        case 'thinking': {
          if (event.delta) {
            msg.thinkingContent = `${msg.thinkingContent || ''}${event.delta}`;
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          }
          break;
        }
        case 'tool_call': {
          lifecycle.promoteToolRoundContent();
          if (event.name === 'web_search') {
            msg.toolCalls = removeNativeSearchToolCall(msg.toolCalls);
          }
          if (!msg.toolCalls) msg.toolCalls = [];
          const toolCallId = resolveToolCallEventId(event);
          let existing =
            (toolCallId
              ? msg.toolCalls.findLast(
                  (toolCall) =>
                    toolCall.id === toolCallId && toolCall.status === 'running',
                )
              : undefined) ??
            (toolCallId
              ? msg.toolCalls.findLast((toolCall) => toolCall.id === toolCallId)
              : undefined) ??
            msg.toolCalls.findLast(
              (toolCall) =>
                toolCall.name === event.name && toolCall.status === 'running',
            ) ??
            msg.toolCalls.findLast((toolCall) => toolCall.status === 'running');
          if (!existing && toolCallId) {
            existing = msg.toolCalls.findLast(
              (toolCall) => toolCall.id === toolCallId,
            );
          }
          if (existing) {
            if (toolCallId && !existing.id) {
              existing.id = toolCallId;
            }
            existing.status = event.success ? 'success' : 'error';
            existing.durationMs = event.duration_ms as number | undefined;
            existing.output = event.output as string | undefined;
            existing.error = event.error as string | undefined;
            existing.errorType = event.error_type as string | undefined;
            if (event.skill_name)
              existing.skillName = event.skill_name as string;
            if (event.skill_type)
              existing.skillType = event.skill_type as string;
            if (event.display_name) {
              existing.displayName = event.display_name as string;
            }
            if (event.summary) existing.summary = event.summary as string;
            if (event.summary_payload) {
              existing.summaryPayload = event.summary_payload as Record<
                string,
                unknown
              >;
            }
            if (event.result_link)
              existing.resultLink = event.result_link as string;
          } else {
            msg.toolCalls.push({
              id: toolCallId,
              name: event.name as string,
              status: event.success ? 'success' : 'error',
              durationMs: event.duration_ms as number | undefined,
              output: event.output as string | undefined,
              error: event.error as string | undefined,
              errorType: event.error_type as string | undefined,
              skillName: (event.skill_name as string) || undefined,
              skillType: (event.skill_type as string) || undefined,
              displayName: (event.display_name as string) || undefined,
              summary: (event.summary as string) || undefined,
              summaryPayload:
                (event.summary_payload as Record<string, unknown>) || undefined,
              resultLink: (event.result_link as string) || undefined,
            });
          }
          if (event.success && deps.options.onToolCall) {
            deps.options.onToolCall(
              event.name as string,
              (event.output as string) ?? '',
            );
          }
          reconcileTurnFlowWithLegacy(msg);
          deps.scrollToBottom();
          break;
        }
        case 'tool_start': {
          lifecycle.promoteToolRoundContent();
          if (event.name === 'web_search') {
            msg.toolCalls = removeNativeSearchToolCall(msg.toolCalls);
          }
          if (!msg.toolCalls) msg.toolCalls = [];
          const toolCallId = resolveToolCallEventId(event);
          const existing =
            (toolCallId
              ? msg.toolCalls.findLast((toolCall) => toolCall.id === toolCallId)
              : undefined) ?? undefined;
          if (existing) {
            existing.name = event.name as string;
            existing.status = 'running';
            existing.arguments = event.arguments as
              | Record<string, unknown>
              | undefined;
            existing.skillName = (event.skill_name as string) || undefined;
            existing.skillType = (event.skill_type as string) || undefined;
            existing.startedAt = Date.now();
          } else {
            msg.toolCalls.push({
              id: toolCallId,
              name: event.name as string,
              status: 'running',
              arguments: event.arguments as Record<string, unknown> | undefined,
              skillName: (event.skill_name as string) || undefined,
              skillType: (event.skill_type as string) || undefined,
              startedAt: Date.now(),
            });
          }
          reconcileTurnFlowWithLegacy(msg);
          deps.scrollToBottom();
          break;
        }
        case 'turn_answer_card': {
          applyCanonicalTurnAnswerCardEvent(msg, event);
          deps.scrollToBottom();
          break;
        }
        case 'turn_evidence': {
          applyCanonicalTurnEvidenceEvent(msg, event);
          deps.scrollToBottom();
          break;
        }
        case 'turn_stage': {
          applyCanonicalTurnStageEvent(msg, event);
          deps.scrollToBottom();
          break;
        }
        case 'turn_stage_update': {
          applyCanonicalTurnStageEvent(msg, event);
          deps.scrollToBottom();
          break;
        }
        default: {
          if (event.event === 'authorization_required' && event.consent_key) {
            addConsent(event.consent_key as string);
          } else if (event.event === 'confirmation_request') {
            lifecycle.promoteToolRoundContent();
            msg.pendingConfirmation = {
              action: (event.action as string) || '',
              table: (event.table as string) || '',
              preview: event.preview as Record<string, unknown> | undefined,
              toolName:
                (event.tool_name as string) ||
                (event.name as string) ||
                undefined,
            };
            reconcileTurnFlowWithLegacy(msg);
          } else if (event.event === 'tool_consent_request') {
            lifecycle.promoteToolRoundContent();
            deps.interactionModeEffective.value = 'trusted_auto';
            msg.pendingConsent = {
              toolName: (event.name as string) || '',
              arguments: event.arguments as
                | Record<string, unknown>
                | undefined,
              skillName: (event.skill_name as string) || undefined,
              skillType: (event.skill_type as string) || undefined,
              resolved: true,
              autoApproved: true,
            };
            deps.pendingInteractionUpdates.value.push({
              kind: 'pending_consent',
              auto_approved: true,
              rejected: false,
              tool_name: (event.name as string) || '',
            });
            deps.deferredAutoConfirm.value = true;
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          } else if (
            event.event === 'status' &&
            event.status === 'web_search_in_progress'
          ) {
            lifecycle.promoteToolRoundContent();
            msg.toolCalls = upsertNativeSearchToolCall(
              msg.toolCalls,
              'running',
            );
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          } else if (
            event.event === 'knowledge_base_feedback' &&
            (event.dropped_knowledge_base_ids ||
              event.effective_knowledge_base_ids)
          ) {
            const effective = Array.isArray(event.effective_knowledge_base_ids)
              ? (event.effective_knowledge_base_ids as number[])
              : [];
            const dropped = Array.isArray(event.dropped_knowledge_base_ids)
              ? (event.dropped_knowledge_base_ids as number[])
              : [];
            deps.selectedKBIds.value = effective;
            if (dropped.length > 0) {
              const droppedLabels = dropped.map((kid) => {
                const binding = deps.agentKBBindings.value.find(
                  (item) => item.knowledge_base_id === kid,
                );
                return formatKnowledgeBaseName(binding?.kb_name, kid);
              });
              message.warning(
                $t('common.globalAiChat.knowledgeBaseSelectionAdjusted', {
                  dropped: formatLocalizedList(droppedLabels),
                }),
              );
            }
          } else if (event.event === 'conversation' && event.conversation_id) {
            lifecycle.updateConversation(event.conversation_id as number);
          } else if (event.event === 'action_buttons' && event.buttons) {
            msg.actionButtons = event.buttons as typeof msg.actionButtons;
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          } else if (event.event === 'image_result' && event.url) {
            if (!msg.imageResults) msg.imageResults = [];
            msg.imageResults.push({
              url: event.url as string,
              isBase64: Boolean(event.is_base64),
              revisedPrompt: (event.revised_prompt as string) || undefined,
            });
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          } else if (event.event === 'rag_sources' && event.sources) {
            msg.ragSources = event.sources as typeof msg.ragSources;
            reconcileTurnFlowWithLegacy(msg);
          } else if (event.event === 'message' && event.delta) {
            msg.content += event.delta as string;
            reconcileTurnFlowWithLegacy(msg);
            deps.scrollToBottom();
          } else if (event.event === 'done') {
            lifecycle.didReceiveDoneEvent = true;
            const doneConversationId = Number(event.conversation_id ?? 0);
            if (doneConversationId > 0) {
              lifecycle.updateConversation(doneConversationId);
            }
            lifecycle.shouldSyncCommittedConversation =
              lifecycle.shouldSyncCommittedConversation ||
              doneConversationId > 0 ||
              event.persistence_committed === true ||
              event.persistence_error === true ||
              event.on_complete_error === true;
            msg.tokenUsage = (event.total_tokens as number) || 0;
            msg.durationMs = (event.duration_ms as number) || 0;
            msg.contextCompacted = Boolean(event.context_compacted);
            msg.memoryFlushTriggered = Boolean(event.memory_flush_triggered);
            msg.memoryRecalled = Boolean(event.memory_recalled);
            msg.pruneStats =
              (event.prune_stats as Record<string, unknown> | undefined) ??
              undefined;
            msg.ragSourceKinds = Array.isArray(event.rag_source_kinds)
              ? (event.rag_source_kinds as string[])
              : undefined;

            const turnRecordRaw = normalizeObjectRecord(event.turn_record);
            let turnRecord = normalizeTurnRecord(event.turn_record);
            const turnOutcome =
              normalizeOptionalString(event.turn_outcome) ??
              turnRecord?.turn_outcome;
            const terminationReason =
              normalizeOptionalString(event.termination_reason) ??
              turnRecord?.termination_reason;
            const completionReason =
              terminationReason ??
              normalizeOptionalString(event.completion_reason);
            const interruptedTurn =
              terminationReason === 'interrupted' ||
              completionReason === 'interrupted';
            const protocolPath =
              normalizeOptionalString(event.protocol_path) ??
              turnRecord?.protocol_path;
            const selectedToolNamesFromEvent = normalizeStringList(
              event.selected_tool_names,
            );
            const selectedToolNames =
              selectedToolNamesFromEvent.length > 0
                ? selectedToolNamesFromEvent
                : (turnRecord?.selected_tool_names ?? []);
            const selectedSkillNamesFromEvent = normalizeStringList(
              event.selected_skill_names,
            );
            const selectedSkillNames =
              selectedSkillNamesFromEvent.length > 0
                ? selectedSkillNamesFromEvent
                : (turnRecord?.selected_skill_names ?? []);
            const contextSourcesFromEvent = normalizeContextSources(
              event.context_sources,
            );
            const contextSources =
              contextSourcesFromEvent.length > 0
                ? contextSourcesFromEvent
                : (turnRecord?.context_sources ?? []);
            const failureKind =
              normalizeOptionalString(
                event.failure_kind ?? event.failureKind,
              ) ??
              normalizeOptionalString(
                turnRecordRaw?.failure_kind ?? turnRecordRaw?.failureKind,
              ) ??
              normalizeOptionalString(
                normalizeObjectRecord(turnRecordRaw?.metadata)?.failure_kind ??
                  normalizeObjectRecord(turnRecordRaw?.metadata)?.failureKind,
              );
            if (failureKind) {
              turnRecord = {
                ...turnRecord,
                ...(turnOutcome ? { turn_outcome: turnOutcome } : {}),
                ...(terminationReason
                  ? { termination_reason: terminationReason }
                  : {}),
                ...(protocolPath ? { protocol_path: protocolPath } : {}),
                ...(selectedToolNames.length > 0
                  ? { selected_tool_names: selectedToolNames }
                  : {}),
                ...(selectedSkillNames.length > 0
                  ? { selected_skill_names: selectedSkillNames }
                  : {}),
                ...(contextSources.length > 0
                  ? { context_sources: contextSources }
                  : {}),
                metadata: {
                  ...turnRecord?.metadata,
                  failure_kind: failureKind,
                },
              };
            }
            const nativeSearchStatus =
              resolveNativeSearchToolStatus(turnRecordRaw);

            if (completionReason) {
              msg.completionReason = completionReason;
            }
            if (turnOutcome) {
              msg.turnOutcome = turnOutcome;
            }
            if (turnRecord) {
              msg.turnRecord = turnRecord;
            }
            if (terminationReason) {
              msg.terminationReason = terminationReason;
            }
            if (interruptedTurn) {
              msg.interrupted = true;
              msg.partial = true;
            }
            if (protocolPath) {
              msg.protocolPath = protocolPath;
            }
            if (selectedToolNames.length > 0) {
              msg.selectedToolNames = selectedToolNames;
            }
            msg.toolCalls = nativeSearchStatus
              ? upsertNativeSearchToolCall(msg.toolCalls, nativeSearchStatus)
              : msg.toolCalls;
            if (selectedToolNames.includes('web_search')) {
              msg.toolCalls = finalizeNativeSearchToolCall(msg.toolCalls);
            }
            if (selectedSkillNames.length > 0) {
              msg.selectedSkillNames = selectedSkillNames;
            }
            if (contextSources.length > 0) {
              msg.contextSources = contextSources;
            }
            if (turnOutcome === 'partial') {
              msg.partial = true;
            }
            if (
              isTurnFailure(
                turnOutcome,
                terminationReason ?? completionReason,
              ) ||
              (turnOutcome === 'partial' && !!failureKind)
            ) {
              msg.requestFailedRetry = true;
            }
            applyCanonicalDoneEvent(msg, event);
            reconcileTurnFlowWithLegacy(msg);

            const nextContextDiagnostics: Record<string, unknown> = {
              context_compacted: Boolean(event.context_compacted),
              estimated_tokens: (event.total_tokens as number) || 0,
              last_interrupted: interruptedTurn,
              memory_flush_triggered: Boolean(event.memory_flush_triggered),
              memory_recalled: Boolean(event.memory_recalled),
              prune_stats:
                (event.prune_stats as Record<string, unknown> | undefined) ??
                null,
              rag_source_kinds: Array.isArray(event.rag_source_kinds)
                ? (event.rag_source_kinds as string[])
                : [],
            };
            if (turnOutcome) {
              nextContextDiagnostics.turn_outcome = turnOutcome;
            }
            if (terminationReason) {
              nextContextDiagnostics.termination_reason = terminationReason;
            }
            if (protocolPath) {
              nextContextDiagnostics.protocol_path = protocolPath;
            }
            if (selectedToolNames.length > 0) {
              nextContextDiagnostics.selected_tool_names = selectedToolNames;
            }
            if (selectedSkillNames.length > 0) {
              nextContextDiagnostics.selected_skill_names = selectedSkillNames;
            }
            if (contextSources.length > 0) {
              nextContextDiagnostics.context_sources = contextSources;
            }
            if (failureKind) {
              nextContextDiagnostics.failure_kind = failureKind;
            }
            deps.conversationContextDiagnostics.value = nextContextDiagnostics;

            const nextLastRunSummary: Record<string, unknown> = {
              duration_ms: (event.duration_ms as number) || 0,
              total_tokens: (event.total_tokens as number) || 0,
            };
            if (completionReason) {
              nextLastRunSummary.completion_reason = completionReason;
            }
            if (interruptedTurn) {
              nextLastRunSummary.interrupted = true;
            }
            if (terminationReason) {
              nextLastRunSummary.termination_reason = terminationReason;
            }
            if (turnOutcome) {
              nextLastRunSummary.turn_outcome = turnOutcome;
            }
            if (protocolPath) {
              nextLastRunSummary.protocol_path = protocolPath;
            }
            if (selectedToolNames.length > 0) {
              nextLastRunSummary.selected_tool_names = selectedToolNames;
            }
            if (selectedSkillNames.length > 0) {
              nextLastRunSummary.selected_skill_names = selectedSkillNames;
            }
            if (contextSources.length > 0) {
              nextLastRunSummary.context_sources = contextSources;
            }
            if (failureKind) {
              nextLastRunSummary.failure_kind = failureKind;
            }
            deps.lastRunSummary.value = nextLastRunSummary;

            if (event.conversation_id) {
              lifecycle.updateConversation(event.conversation_id as number);
            }
            if (event.memory_updated) {
              deps.lastMemoryUpdated.value = true;
              msg.memoryUpdated = true;
            }
            if (deps.options.onStreamComplete) {
              deps.options.onStreamComplete();
            }
            lifecycle.terminalizeMessage();
            deps.streaming.value = false;
            deps.sending.value = false;
            void deps.loadConversations();
            if (lifecycle.shouldSyncCommittedConversation) {
              lifecycle.triggerCommittedConversationSync();
            }
            lifecycle.scheduleDoneAbort();
          } else if (event.error) {
            if (event.conversation_id) {
              lifecycle.updateConversation(event.conversation_id as number);
            }
            lifecycle.shouldSyncInterruptedConversation =
              lifecycle.shouldSyncInterruptedConversation ||
              lifecycle.hasReceivedStreamPayload ||
              lifecycle.streamConversationId !== null;
            lifecycle.applyAssistantError(normalizeSseEventError(event, $t));
            lifecycle.terminalizeMessage();
            deps.streaming.value = false;
            deps.sending.value = false;
            void deps.loadConversations();
          }
        }
      }
    } catch (error: unknown) {
      console.warn('[AI Chat] SSE parse error:', error);
    }
  };
}
