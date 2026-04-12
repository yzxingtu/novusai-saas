import type { Ref } from 'vue';

import type {
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  InteractionMode,
} from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

import type {
  ChatKBBindingInfo,
  PageContext,
} from '#/api/shared/ai-chat';
import type { AIInteractionUpdate } from '#/store/shared/ai-panel';
import type { AppErrorInfo } from '#/utils/request';

import { nextTick, unref } from 'vue';

import { message } from 'ant-design-vue';

import { sendChatStreamApi } from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { addConsent, getConsentedActions } from '#/utils/ai-consent';
import {
  normalizeSseEventError,
  normalizeSseTransportError,
} from '#/utils/request';

import {
  formatKnowledgeBaseName,
  formatLocalizedList,
} from './display-formatters';
import { moveStreamingContentToThinking } from './chat-input-utils';
import {
  finalizeNativeSearchToolCall,
  isTurnFailure,
  normalizeContextSources,
  normalizeObjectRecord,
  normalizeOptionalString,
  normalizeStringList,
  normalizeTurnRecord,
  removeNativeSearchToolCall,
  resolveNativeSearchToolStatus,
  upsertNativeSearchToolCall,
} from './use-ai-chat-message-helpers';

export type StreamAbortReason = 'context_switch' | 'none' | 'user';

export interface StreamControl {
  abortController: AbortController | null;
  lifecycle: null | { abortReason: StreamAbortReason };
}

export interface StreamRequestDeps {
  activeConversationAgentId: Ref<null | number>;
  activeConversationId: Ref<null | number>;
  agentKBBindings: Ref<ChatKBBindingInfo[]>;
  allAgentsVariables: Ref<Record<number, Record<string, string>>>;
  chatMessages: Ref<ChatMessage[]>;
  conversationAnchorId: Ref<null | number>;
  conversationContextDiagnostics: Ref<null | Record<string, unknown>>;
  conversations: Ref<ConversationItem[]>;
  deferredAutoConfirm: Ref<boolean>;
  ensurePageOperationChannelReady: (
    apiPrefix: string,
    pageContext?: null | PageContext,
  ) => Promise<boolean>;
  hasPageOperations: (pageContext?: null | PageContext) => boolean;
  interactionMode: Ref<InteractionMode>;
  interactionModeEffective: Ref<InteractionMode>;
  lastMemoryUpdated: Ref<boolean>;
  lastRunSummary: Ref<null | Record<string, unknown>>;
  loadConversations: () => Promise<void>;
  options: UseAIChatOptions;
  pendingInteractionUpdates: Ref<PendingInteractionUpdate[]>;
  recoverConversationIdFromHistory: (
    knownConversationIds: Set<number>,
    agentId: number,
  ) => null | number;
  rememberConversationAnchor: (conversationId: number, agentId: number) => void;
  selectedKBIds: Ref<number[]>;
  sendMessage: (options?: {
    agentId?: number;
    pageContext?: null | PageContext;
    routeSource?: null | string;
    silent?: boolean;
  }) => Promise<boolean>;
  streamControl: StreamControl;
  streaming: Ref<boolean>;
  sending: Ref<boolean>;
  syncConversationAfterInterrupt: (
    conversationId: number,
    interruptedHistoryBaseline: number,
  ) => Promise<void>;
  uiPanelStore: {
    consumeInteractionUpdates: () => AIInteractionUpdate[];
    restoreInteractionUpdates: (updates: AIInteractionUpdate[]) => void;
  };
  userScrolledUp: Ref<boolean>;
  scrollToBottom: (force?: boolean) => void;
  imageParams: Ref<{
    n: number;
    quality: string;
    size: string;
    style: string;
  }>;
}

export interface StreamRequestParams {
  apiAttachments?:
    | Pick<ChatAttachment, 'mime_type' | 'name' | 'type' | 'url'>[]
    | undefined;
  pageContext: null | PageContext;
  routeSource?: null | string;
  targetAgentId: number;
  texts: string[];
}

async function parseSSEEvents(
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
        needFlush = ev.event === 'message' || ev.event === 'thinking';
      } catch {
        needFlush = true;
      }
      if (needFlush) await nextTick();
    }
  }
}

export async function runStreamRequest(
  deps: StreamRequestDeps,
  params: StreamRequestParams,
) {
  const {
    activeConversationAgentId,
    activeConversationId,
    agentKBBindings,
    allAgentsVariables,
    chatMessages,
    conversationAnchorId,
    conversationContextDiagnostics,
    conversations,
    deferredAutoConfirm,
    ensurePageOperationChannelReady,
    hasPageOperations,
    interactionMode,
    interactionModeEffective,
    lastMemoryUpdated,
    lastRunSummary,
    loadConversations,
    options,
    pendingInteractionUpdates,
    recoverConversationIdFromHistory,
    rememberConversationAnchor,
    selectedKBIds,
    sendMessage,
    streamControl,
    streaming,
    sending,
    syncConversationAfterInterrupt,
    uiPanelStore,
    userScrolledUp,
    scrollToBottom,
    imageParams,
  } = deps;
  const { texts, apiAttachments, targetAgentId, pageContext, routeSource } =
    params;

  sending.value = true;
  streaming.value = true;
  const sseBuffer = { value: '' };
  streamControl.abortController = new AbortController();
  const requestAbortController = streamControl.abortController;
  const streamLifecycle = { abortReason: 'none' as StreamAbortReason };
  streamControl.lifecycle = streamLifecycle;
  const assistantIdx = chatMessages.value.length - 1;
  const interruptedHistoryBaseline = chatMessages.value.length;
  const knownConversationIdsBeforeSend = new Set(
    conversations.value.map((conversation) => conversation.id),
  );
  let doneAbortTimer: null | ReturnType<typeof setTimeout> = null;
  let didReceiveDoneEvent = false;
  let didSseEnd = false;
  let hasReceivedStreamPayload = false;
  let shouldSyncInterruptedConversation = false;
  let shouldSyncCommittedConversation = false;
  let committedConversationSyncPromise: null | Promise<void> = null;
  let streamConversationId =
    activeConversationId.value ?? conversationAnchorId.value;

  function finalizeMessage() {
    const msg = chatMessages.value[assistantIdx];
    if (msg) {
      msg.streaming = false;
      if (msg.toolCalls) {
        const orphaned = msg.toolCalls.filter((tc) => tc.status === 'running');
        if (orphaned.length > 0) {
          console.warn(
            '[use-ai-chat] finalizeMessage: orphaned running tool(s), marking as error',
            orphaned.map((t) => ({ name: t.name, id: t.id })),
          );
        }
        for (const tc of msg.toolCalls) {
          if (tc.status === 'running') {
            tc.status = 'error';
          }
        }
      }
    }
  }

  function triggerCommittedConversationSync() {
    if (
      committedConversationSyncPromise ||
      streamConversationId === null ||
      activeConversationId.value !== streamConversationId
    ) {
      return;
    }
    committedConversationSyncPromise = syncConversationAfterInterrupt(
      streamConversationId,
      interruptedHistoryBaseline,
    ).finally(() => {
      committedConversationSyncPromise = null;
    });
  }

  function promoteToolRoundContent() {
    const msg = chatMessages.value[assistantIdx];
    if (!msg || msg.role !== 'assistant') {
      return;
    }
    moveStreamingContentToThinking(msg);
  }

  function applyAssistantError(
    msg: ChatMessage | undefined,
    appError: AppErrorInfo,
  ) {
    if (!msg) return;
    msg.error = appError;
    msg.requestFailedRetry = true;
    if (msg.content.trim().length > 0) {
      msg.partial = true;
    }
    msg.terminationReason = msg.terminationReason || 'error';
    msg.turnOutcome = msg.turnOutcome || 'failed';
    msg.completionReason = msg.completionReason || 'error';
  }

  function handleSsePayload(data: string) {
    if (data === '[DONE]') return;
    try {
      hasReceivedStreamPayload = true;
      const event = JSON.parse(data) as Record<string, unknown> & {
        delta?: string;
        event?: string;
      };
      const msg = chatMessages.value[assistantIdx];
      if (!msg) return;

      switch (event.event) {
        case 'clear_content': {
          msg.content = '';

          break;
        }
        case 'optimizing_tools': {
          msg.optimizingTools = {
            total: (event.total as number) || 0,
            selected: (event.selected as number) || 0,
          };
          scrollToBottom();

          break;
        }
        case 'thinking': {
          if (event.delta) {
            msg.thinkingContent = `${msg.thinkingContent || ''}${event.delta}`;
            scrollToBottom();
          }

          break;
        }
        case 'tool_call': {
          promoteToolRoundContent();
          if (event.name === 'web_search') {
            msg.toolCalls = removeNativeSearchToolCall(msg.toolCalls);
          }
          if (!msg.toolCalls) msg.toolCalls = [];
          let existing = msg.toolCalls.findLast(
            (tc) => tc.name === event.name && tc.status === 'running',
          );
          if (!existing) {
            existing = msg.toolCalls.findLast((tc) => tc.status === 'running');
          }
          if (existing) {
            existing.status = event.success ? 'success' : 'error';
            existing.durationMs = event.duration_ms as number | undefined;
            existing.output = event.output as string | undefined;
            existing.error = event.error as string | undefined;
            existing.errorType = event.error_type as string | undefined;
            if (event.skill_name) existing.skillName = event.skill_name as string;
            if (event.skill_type) existing.skillType = event.skill_type as string;
            if (event.display_name)
              existing.displayName = event.display_name as string;
            if (event.summary) existing.summary = event.summary as string;
            if (event.summary_payload) {
              existing.summaryPayload = event.summary_payload as Record<
                string,
                unknown
              >;
            }
            if (event.result_link) existing.resultLink = event.result_link as string;
          } else {
            msg.toolCalls.push({
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
          if (event.success && options.onToolCall) {
            options.onToolCall(
              event.name as string,
              (event.output as string) ?? '',
            );
          }
          scrollToBottom();

          break;
        }
        case 'tool_start': {
          promoteToolRoundContent();
          if (event.name === 'web_search') {
            msg.toolCalls = removeNativeSearchToolCall(msg.toolCalls);
          }
          if (!msg.toolCalls) msg.toolCalls = [];
          msg.toolCalls.push({
            id: event.id as string,
            name: event.name as string,
            status: 'running',
            arguments: event.arguments as Record<string, unknown> | undefined,
            skillName: (event.skill_name as string) || undefined,
            skillType: (event.skill_type as string) || undefined,
            startedAt: Date.now(),
          });
          scrollToBottom();

          break;
        }
        default: {
          if (event.event === 'authorization_required' && event.consent_key) {
            addConsent(event.consent_key as string);
          } else if (event.event === 'confirmation_request') {
            promoteToolRoundContent();
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
            promoteToolRoundContent();
            const nextInteractionModeEffective =
              normalizeOptionalString(event.interaction_mode_effective) ??
              interactionModeEffective.value;
            if (
              nextInteractionModeEffective === 'confirm' ||
              nextInteractionModeEffective === 'trusted_auto'
            ) {
              interactionModeEffective.value = nextInteractionModeEffective;
            }
            if (nextInteractionModeEffective === 'trusted_auto') {
              msg.pendingConsent = {
                toolName: (event.name as string) || '',
                arguments: event.arguments as Record<string, unknown> | undefined,
                skillName: (event.skill_name as string) || undefined,
                skillType: (event.skill_type as string) || undefined,
                resolved: true,
                autoApproved: true,
              };
              pendingInteractionUpdates.value.push({
                kind: 'pending_consent',
                auto_approved: true,
                rejected: false,
                tool_name: (event.name as string) || '',
              });
              deferredAutoConfirm.value = true;
            } else {
              msg.pendingConsent = {
                toolName: (event.name as string) || '',
                arguments: event.arguments as Record<string, unknown> | undefined,
                skillName: (event.skill_name as string) || undefined,
                skillType: (event.skill_type as string) || undefined,
              };
            }
            scrollToBottom();
          } else if (
            event.event === 'status' &&
            event.status === 'web_search_in_progress'
          ) {
            promoteToolRoundContent();
            msg.toolCalls = upsertNativeSearchToolCall(msg.toolCalls, 'running');
            scrollToBottom();
          } else if (
            event.event === 'knowledge_base_feedback' &&
            (event.dropped_knowledge_base_ids ||
              event.effective_knowledge_base_ids)
          ) {
            const effective = Array.isArray(
              event.effective_knowledge_base_ids,
            )
              ? (event.effective_knowledge_base_ids as number[])
              : [];
            const dropped = Array.isArray(event.dropped_knowledge_base_ids)
              ? (event.dropped_knowledge_base_ids as number[])
              : [];
            selectedKBIds.value = effective;
            if (dropped.length > 0) {
              const droppedLabels = dropped.map((kid) => {
                const binding = agentKBBindings.value.find(
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
            streamConversationId = event.conversation_id as number;
            activeConversationId.value = streamConversationId;
            activeConversationAgentId.value = targetAgentId;
            rememberConversationAnchor(streamConversationId, targetAgentId);
          } else if (event.event === 'action_buttons' && event.buttons) {
            msg.actionButtons = event.buttons as typeof msg.actionButtons;
            scrollToBottom();
          } else if (event.event === 'image_result' && event.url) {
            if (!msg.imageResults) msg.imageResults = [];
            msg.imageResults.push({
              url: event.url as string,
              isBase64: Boolean(event.is_base64),
              revisedPrompt: (event.revised_prompt as string) || undefined,
            });
            scrollToBottom();
          } else if (event.event === 'rag_sources' && event.sources) {
            msg.ragSources = event.sources as typeof msg.ragSources;
          } else if (event.event === 'message' && event.delta) {
            msg.content += event.delta as string;
            scrollToBottom();
          } else if (event.event === 'done') {
            didReceiveDoneEvent = true;
            const doneConversationId = Number(event.conversation_id ?? 0);
            if (doneConversationId > 0) {
              streamConversationId = doneConversationId;
              activeConversationId.value = doneConversationId;
              activeConversationAgentId.value = targetAgentId;
              rememberConversationAnchor(doneConversationId, targetAgentId);
            }
            shouldSyncCommittedConversation =
              shouldSyncCommittedConversation ||
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
            const turnRecord = normalizeTurnRecord(event.turn_record);
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
            msg.toolCalls = resolveNativeSearchToolStatus(turnRecordRaw)
              ? upsertNativeSearchToolCall(
                  msg.toolCalls,
                  resolveNativeSearchToolStatus(turnRecordRaw) || 'success',
                )
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
              isTurnFailure(turnOutcome, terminationReason ?? completionReason)
            ) {
              msg.requestFailedRetry = true;
            }

            const nextContextDiagnostics: Record<string, unknown> = {
              context_compacted: Boolean(event.context_compacted),
              estimated_tokens: (event.total_tokens as number) || 0,
              interaction_mode_effective: interactionModeEffective.value,
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
            conversationContextDiagnostics.value = nextContextDiagnostics;

            const nextLastRunSummary: Record<string, unknown> = {
              duration_ms: (event.duration_ms as number) || 0,
              interaction_mode_effective: interactionModeEffective.value,
              interaction_mode_requested: interactionMode.value,
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
            lastRunSummary.value = nextLastRunSummary;
            if (event.conversation_id) {
              streamConversationId = event.conversation_id as number;
              activeConversationId.value = streamConversationId;
              activeConversationAgentId.value = targetAgentId;
              rememberConversationAnchor(streamConversationId, targetAgentId);
            }
            if (event.memory_updated) {
              lastMemoryUpdated.value = true;
              msg.memoryUpdated = true;
            }
            if (options.onStreamComplete) {
              options.onStreamComplete();
            }
            finalizeMessage();
            streaming.value = false;
            sending.value = false;
            loadConversations();
            if (shouldSyncCommittedConversation) {
              triggerCommittedConversationSync();
            }
            if (doneAbortTimer) {
              clearTimeout(doneAbortTimer);
            }
            doneAbortTimer = setTimeout(() => {
              streamControl.abortController?.abort();
            }, 2000);
          } else if (event.error) {
            if (event.conversation_id) {
              streamConversationId = event.conversation_id as number;
              activeConversationId.value = streamConversationId;
              activeConversationAgentId.value = targetAgentId;
              rememberConversationAnchor(streamConversationId, targetAgentId);
            }
            shouldSyncInterruptedConversation =
              shouldSyncInterruptedConversation ||
              hasReceivedStreamPayload ||
              streamConversationId !== null;
            applyAssistantError(msg, normalizeSseEventError(event, $t));
          }
        }
      }
    } catch (error: unknown) {
      console.warn('[AI Chat] SSE parse error:', error);
    }
  }

  let panelInteractionUpdates: PendingInteractionUpdate[] = [];
  let localInteractionUpdates: PendingInteractionUpdate[] = [];

  try {
    const prefix = unref(options.apiPrefix) as string;
    const pageChannelReady = await ensurePageOperationChannelReady(
      prefix,
      pageContext,
    );
    if (!pageChannelReady && hasPageOperations(pageContext)) {
      const reconnectError = {
        message: $t('shared.common.connectionLost'),
        raw: { name: 'PageOperationChannelUnavailable' },
      } as AppErrorInfo;
      message.warning(reconnectError.message);
      applyAssistantError(chatMessages.value[assistantIdx], reconnectError);
      finalizeMessage();
      return;
    }
    const singleText = texts.length === 1 ? (texts[0] ?? '') : null;
    panelInteractionUpdates = uiPanelStore.consumeInteractionUpdates();
    localInteractionUpdates = [...pendingInteractionUpdates.value];
    const mergedInteractionUpdates = [
      ...panelInteractionUpdates,
      ...localInteractionUpdates,
    ];
    interactionModeEffective.value = interactionMode.value;
    const requestBody = {
      ...(singleText === null ? { messages: texts } : { message: singleText }),
      conversation_id: streamConversationId,
      ...(mergedInteractionUpdates.length > 0
        ? { interaction_updates: mergedInteractionUpdates }
        : {}),
      ...(selectedKBIds.value.length > 0
        ? { knowledge_base_ids: selectedKBIds.value }
        : {}),
      ...(Object.keys(allAgentsVariables.value[targetAgentId] ?? {}).length > 0
        ? { variables: allAgentsVariables.value[targetAgentId] }
        : {}),
      consented_actions: getConsentedActions(),
      ...(apiAttachments ? { attachments: apiAttachments } : {}),
      ...(imageParams.value.size !== '1024x1024' ||
      imageParams.value.quality !== 'standard' ||
      imageParams.value.style !== 'vivid' ||
      imageParams.value.n !== 1
        ? { image_params: imageParams.value }
        : {}),
      ...(pageContext ? { page_context: pageContext } : {}),
      ...(routeSource ? { route_source: routeSource } : {}),
      interaction_mode: interactionMode.value,
      ...(options.pageSessionIdGetter
        ? { page_session_id: options.pageSessionIdGetter() || null }
        : {}),
    };
    pendingInteractionUpdates.value = [];
    await sendChatStreamApi(prefix, targetAgentId, requestBody, {
      abortController: streamControl.abortController,
      async onMessage(rawChunk: string) {
        await parseSSEEvents(rawChunk, sseBuffer, handleSsePayload);
      },
      async onEnd() {
        didSseEnd = true;
        if (doneAbortTimer) {
          clearTimeout(doneAbortTimer);
          doneAbortTimer = null;
        }
        await parseSSEEvents('\n', sseBuffer, handleSsePayload);
        await loadConversations();
      },
      onError(error: AppErrorInfo | Error) {
        const appError = normalizeSseTransportError(error, $t);
        if (
          (appError.raw as undefined | { name?: string })?.name === 'AbortError'
        ) {
          return;
        }
        shouldSyncInterruptedConversation =
          shouldSyncInterruptedConversation || hasReceivedStreamPayload;
        const msg = chatMessages.value[assistantIdx];
        applyAssistantError(msg, appError);
        finalizeMessage();
      },
    });
  } catch (error: unknown) {
    uiPanelStore.restoreInteractionUpdates(panelInteractionUpdates);
    pendingInteractionUpdates.value = [
      ...localInteractionUpdates,
      ...pendingInteractionUpdates.value,
    ];
    const normalizedError = normalizeSseTransportError(error, $t);
    shouldSyncInterruptedConversation =
      (normalizedError.raw as undefined | { name?: string })?.name ===
      'AbortError'
        ? shouldSyncInterruptedConversation ||
          streamLifecycle.abortReason === 'user'
        : shouldSyncInterruptedConversation || hasReceivedStreamPayload;
    const msg = chatMessages.value[assistantIdx];
    if (
      (normalizedError.raw as undefined | { name?: string })?.name !==
      'AbortError'
    ) {
      applyAssistantError(msg, normalizedError);
      finalizeMessage();
    }
  } finally {
    if (doneAbortTimer) {
      clearTimeout(doneAbortTimer);
      doneAbortTimer = null;
    }
    sending.value = false;
    streaming.value = false;
    if (streamControl.abortController === requestAbortController) {
      streamControl.abortController = null;
    }
    if (streamControl.lifecycle === streamLifecycle) {
      streamControl.lifecycle = null;
    }
    userScrolledUp.value = false;
    finalizeMessage();

    const shouldReloadConversationList =
      shouldSyncCommittedConversation ||
      !didReceiveDoneEvent ||
      shouldSyncInterruptedConversation;
    if (shouldReloadConversationList) {
      await loadConversations();
    }

    let interruptedConversationId = streamConversationId;
    let recoveredConversationFromHistory = false;
    if (interruptedConversationId === null) {
      const recoveredConversationId = recoverConversationIdFromHistory(
        knownConversationIdsBeforeSend,
        targetAgentId,
      );
      if (recoveredConversationId !== null) {
        recoveredConversationFromHistory = true;
        interruptedConversationId = recoveredConversationId;
        activeConversationId.value = recoveredConversationId;
        activeConversationAgentId.value = targetAgentId;
        rememberConversationAnchor(recoveredConversationId, targetAgentId);
      }
    }
    const shouldSyncConversationHistory =
      interruptedConversationId !== null &&
      (recoveredConversationFromHistory ||
        shouldSyncCommittedConversation ||
        (!didReceiveDoneEvent &&
          (streamLifecycle.abortReason === 'user' ||
            shouldSyncInterruptedConversation ||
            didSseEnd)));
    if (shouldSyncConversationHistory) {
      if (committedConversationSyncPromise) {
        await committedConversationSyncPromise;
      } else if (interruptedConversationId !== null) {
        await syncConversationAfterInterrupt(
          interruptedConversationId,
          interruptedHistoryBaseline,
        );
      }
    }

    if (
      deferredAutoConfirm.value &&
      pendingInteractionUpdates.value.length > 0
    ) {
      deferredAutoConfirm.value = false;
      await nextTick();
      sendMessage({ silent: true });
    }
  }
}
