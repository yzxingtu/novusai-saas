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
  applyNativeSearchStatusToTurnFlow,
  applyStreamingToolResultToTurnFlow,
  applyStreamingToolStartToTurnFlow,
  isTurnFailure,
  normalizeContextSources,
  normalizeObjectRecord,
  normalizeOptionalString,
  normalizeStringList,
  normalizeTurnRecord,
  resolveNativeSearchToolStatus,
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

function shouldSuppressLegacyTurnFlowStreamEvent(eventName?: string): boolean {
  return (
    eventName === 'optimizing_tools' ||
    eventName === 'thinking' ||
    eventName === 'rag_sources'
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
      if (shouldSuppressLegacyTurnFlowStreamEvent(event.event)) {
        return;
      }

      switch (event.event) {
        case 'clear_content': {
          if (!isDraftClearContentEventAllowed(msg)) {
            break;
          }
          msg.content = '';
          break;
        }
        case 'tool_call': {
          lifecycle.promoteToolRoundContent();
          applyStreamingToolResultToTurnFlow(msg, event);
          if (event.success && deps.options.onToolCall) {
            deps.options.onToolCall(
              event.name as string,
              (event.output as string) ?? '',
            );
          }
          deps.scrollToBottom();
          break;
        }
        case 'tool_start': {
          lifecycle.promoteToolRoundContent();
          applyStreamingToolStartToTurnFlow(msg, event);
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
          } else if (event.event === 'tool_consent_request') {
            lifecycle.promoteToolRoundContent();
            deps.interactionModeEffective.value = 'trusted_auto';
            msg.pendingConsent = {
              toolName: (event.name as string) || '',
              arguments: event.arguments as Record<string, unknown> | undefined,
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
            deps.scrollToBottom();
          } else if (
            event.event === 'status' &&
            event.status === 'web_search_in_progress'
          ) {
            lifecycle.promoteToolRoundContent();
            applyNativeSearchStatusToTurnFlow(msg, {
              displayName: $t('common.globalAiChat.toolNativeSearch'),
              status: 'running',
              toolName: 'native_web_search',
            });
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
            deps.scrollToBottom();
          } else if (event.event === 'image_result' && event.url) {
            if (!msg.imageResults) msg.imageResults = [];
            msg.imageResults.push({
              url: event.url as string,
              isBase64: Boolean(event.is_base64),
              revisedPrompt: (event.revised_prompt as string) || undefined,
            });
            deps.scrollToBottom();
          } else if (event.event === 'message' && event.delta) {
            msg.content += event.delta as string;
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
            const finalizedNativeSearchStatus =
              nativeSearchStatus === 'running' &&
              selectedToolNames.includes('web_search') &&
              !isTurnFailure(turnOutcome, terminationReason ?? completionReason)
                ? 'success'
                : nativeSearchStatus;

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
            if (finalizedNativeSearchStatus) {
              applyNativeSearchStatusToTurnFlow(msg, {
                displayName: $t('common.globalAiChat.toolNativeSearch'),
                status: finalizedNativeSearchStatus,
                toolName: 'native_web_search',
              });
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
