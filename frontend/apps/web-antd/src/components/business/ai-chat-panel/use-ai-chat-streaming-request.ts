import type { Ref } from 'vue';

import type {
  ChatAttachment,
  ChatMessage,
  ConversationItem,
  InteractionMode,
} from './types';
import type { UseAIChatOptions } from './use-ai-chat-options';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

import type { ChatKBBindingInfo, PageContext } from '#/api/shared/ai-chat';
import type { AIInteractionUpdate } from '#/store/shared/ai-panel';
import type { AppErrorInfo } from '#/utils/request';

import { unref } from 'vue';

import { message } from 'ant-design-vue';

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

export async function runStreamRequest(
  deps: StreamRequestDeps,
  params: StreamRequestParams,
) {
  const {
    allAgentsVariables,
    ensurePageOperationChannelReady,
    hasPageOperations,
    interactionMode,
    loadConversations,
    options,
    pendingInteractionUpdates,
    selectedKBIds,
    uiPanelStore,
    imageParams,
  } = deps;
  const { texts, apiAttachments, targetAgentId, pageContext, routeSource } =
    params;

  const lifecycle = createStreamRequestLifecycle(deps, targetAgentId);
  const sseBuffer = { value: '' };
  const handleSsePayload = createStreamSseHandler(deps, lifecycle);

  let panelInteractionUpdates: AIInteractionUpdate[] = [];
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
      lifecycle.applyAssistantError(reconnectError);
      lifecycle.finalizeMessage();
      return;
    }

    const singleText = texts.length === 1 ? (texts[0] ?? '') : null;
    panelInteractionUpdates = uiPanelStore.consumeInteractionUpdates();
    localInteractionUpdates = [...pendingInteractionUpdates.value];
    const mergedInteractionUpdates = [
      ...panelInteractionUpdates,
      ...localInteractionUpdates,
    ];
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
      abortController: deps.streamControl.abortController,
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
        lifecycle.finalizeMessage();
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
      lifecycle.finalizeMessage();
    }
  } finally {
    await finalizeStreamRequest(deps, lifecycle);
  }
}
