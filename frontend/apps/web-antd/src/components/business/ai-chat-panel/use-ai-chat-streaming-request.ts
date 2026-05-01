import type { Ref } from 'vue';

import type {
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  InteractionMode,
} from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

import type { ChatKBBindingInfo } from '#/api/shared/ai-chat';
import type { AIInteractionUpdate } from '#/store/shared/ai-panel';
import type { AppErrorInfo } from '#/utils/request';

import { unref } from 'vue';

import { sendChatStreamApi } from '#/api/shared/ai-chat';
import { $t } from '#/locales';
import { getConsentedActions } from '#/utils/ai-consent';
import { normalizeSseTransportError } from '#/utils/request';

import { createStreamRequestLifecycle } from './use-ai-chat-streaming-request-lifecycle';
import {
  finalizeStreamRequest,
  restoreStreamInteractionUpdates,
} from './use-ai-chat-streaming-request-recovery';
import {
  createStreamSseHandler,
  parseSSEEvents,
} from './use-ai-chat-streaming-request-sse';

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
  selectedSkillNames: Ref<string[]>;
  sendMessage: (options?: {
    agentId?: number;
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
  targetAgentId: number;
  texts: string[];
}

export async function runStreamRequest(
  deps: StreamRequestDeps,
  params: StreamRequestParams,
) {
  const {
    allAgentsVariables,
    interactionMode,
    loadConversations,
    options,
    pendingInteractionUpdates,
    selectedKBIds,
    selectedSkillNames,
    uiPanelStore,
    imageParams,
  } = deps;
  const { texts, apiAttachments, targetAgentId } = params;

  const lifecycle = createStreamRequestLifecycle(deps, targetAgentId);
  const sseBuffer = { value: '' };
  const handleSsePayload = createStreamSseHandler(deps, lifecycle);

  let panelInteractionUpdates: AIInteractionUpdate[] = [];
  let localInteractionUpdates: PendingInteractionUpdate[] = [];

  try {
    const prefix = unref(options.apiPrefix) as string;
    const singleText = texts.length === 1 ? (texts[0] ?? '') : null;
    panelInteractionUpdates = uiPanelStore.consumeInteractionUpdates();
    localInteractionUpdates = [...pendingInteractionUpdates.value];
    const mergedInteractionUpdates = [
      ...panelInteractionUpdates,
      ...localInteractionUpdates,
    ];
    const selectedSkillNamesForTurn = [...selectedSkillNames.value];
    deps.interactionModeEffective.value = interactionMode.value;

    const requestBody = {
      ...(singleText === null ? { messages: texts } : { message: singleText }),
      conversation_id: lifecycle.streamConversationId,
      ...(mergedInteractionUpdates.length > 0
        ? { interaction_updates: mergedInteractionUpdates }
        : {}),
      ...(selectedKBIds.value.length > 0
        ? { knowledge_base_ids: selectedKBIds.value }
        : {}),
      ...(selectedSkillNamesForTurn.length > 0
        ? { selected_skill_names: selectedSkillNamesForTurn }
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
    };

    pendingInteractionUpdates.value = [];
    selectedSkillNames.value = [];
    const requestAbortController = deps.streamControl.abortController;
    if (!requestAbortController) {
      throw new Error('Stream abort controller was not initialized');
    }
    await sendChatStreamApi(prefix, targetAgentId, requestBody, {
      abortController: requestAbortController,
      async onMessage(rawChunk: string) {
        await parseSSEEvents(rawChunk, sseBuffer, handleSsePayload);
      },
      async onEnd() {
        lifecycle.didSseEnd = true;
        lifecycle.clearDoneAbortTimer();
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
        lifecycle.shouldSyncInterruptedConversation =
          lifecycle.shouldSyncInterruptedConversation ||
          lifecycle.hasReceivedStreamPayload;
        lifecycle.applyAssistantError(appError);
        lifecycle.terminalizeMessage();
      },
    });
  } catch (error: unknown) {
    restoreStreamInteractionUpdates(
      deps,
      panelInteractionUpdates,
      localInteractionUpdates,
    );
    const normalizedError = normalizeSseTransportError(error, $t);
    lifecycle.shouldSyncInterruptedConversation =
      (normalizedError.raw as undefined | { name?: string })?.name ===
      'AbortError'
        ? lifecycle.shouldSyncInterruptedConversation ||
          lifecycle.streamLifecycle?.abortReason === 'user'
        : lifecycle.shouldSyncInterruptedConversation ||
          lifecycle.hasReceivedStreamPayload;
    if (
      (normalizedError.raw as undefined | { name?: string })?.name !==
      'AbortError'
    ) {
      lifecycle.applyAssistantError(normalizedError);
      lifecycle.terminalizeMessage();
    }
  } finally {
    await finalizeStreamRequest(deps, lifecycle);
  }
}
