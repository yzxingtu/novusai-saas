import type { StreamRequestDeps } from './use-ai-chat-streaming-request';
import type { StreamRequestLifecycle } from './use-ai-chat-streaming-request-lifecycle';
import type { PendingInteractionUpdate } from './use-ai-chat-streaming-types';

import type { AIInteractionUpdate } from '#/store/shared/ai-panel';

import { nextTick } from 'vue';

export function restoreStreamInteractionUpdates(
  deps: StreamRequestDeps,
  panelInteractionUpdates: AIInteractionUpdate[],
  localInteractionUpdates: PendingInteractionUpdate[],
) {
  deps.uiPanelStore.restoreInteractionUpdates(panelInteractionUpdates);
  deps.pendingInteractionUpdates.value = [
    ...localInteractionUpdates,
    ...deps.pendingInteractionUpdates.value,
  ];
}

export async function finalizeStreamRequest(
  deps: StreamRequestDeps,
  lifecycle: StreamRequestLifecycle,
) {
  lifecycle.clearDoneAbortTimer();
  deps.sending.value = false;
  deps.streaming.value = false;
  if (deps.streamControl.abortController === lifecycle.requestAbortController) {
    deps.streamControl.abortController = null;
  }
  if (deps.streamControl.lifecycle === lifecycle.streamLifecycle) {
    deps.streamControl.lifecycle = null;
  }
  deps.userScrolledUp.value = false;
  lifecycle.finalizeMessage();

  const shouldReloadConversationList =
    lifecycle.shouldSyncCommittedConversation ||
    !lifecycle.didReceiveDoneEvent ||
    lifecycle.shouldSyncInterruptedConversation;
  if (shouldReloadConversationList) {
    await deps.loadConversations();
  }

  let interruptedConversationId = lifecycle.streamConversationId;
  let recoveredConversationFromHistory = false;
  if (interruptedConversationId === null) {
    const recoveredConversationId = deps.recoverConversationIdFromHistory(
      lifecycle.knownConversationIdsBeforeSend,
      lifecycle.targetAgentId,
    );
    if (recoveredConversationId !== null) {
      recoveredConversationFromHistory = true;
      interruptedConversationId = recoveredConversationId;
      lifecycle.updateConversation(recoveredConversationId);
    }
  }

  const shouldSyncConversationHistory =
    interruptedConversationId !== null &&
    (recoveredConversationFromHistory ||
      lifecycle.shouldSyncCommittedConversation ||
      (!lifecycle.didReceiveDoneEvent &&
        (lifecycle.streamLifecycle?.abortReason === 'user' ||
          lifecycle.shouldSyncInterruptedConversation ||
          lifecycle.didSseEnd)));

  if (shouldSyncConversationHistory) {
    const syncConversationId = interruptedConversationId;
    if (syncConversationId === null) {
      return;
    }
    const conversationSyncPromise =
      lifecycle.committedConversationSyncPromise ||
      deps.syncConversationAfterInterrupt(
        syncConversationId,
        lifecycle.interruptedHistoryBaseline,
      );
    await conversationSyncPromise;
  }

  if (
    deps.deferredAutoConfirm.value &&
    deps.pendingInteractionUpdates.value.length > 0
  ) {
    deps.deferredAutoConfirm.value = false;
    await nextTick();
    void deps.sendMessage({ silent: true });
  }
}
