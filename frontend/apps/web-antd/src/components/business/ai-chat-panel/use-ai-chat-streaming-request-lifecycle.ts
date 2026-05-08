import type { ChatMessage } from './types';
import type {
  StreamAbortReason,
  StreamRequestDeps,
} from './use-ai-chat-streaming-request';

import type { AppErrorInfo } from '#/utils/request';

import {
  getRunningToolExecutionRefs,
  settleTurnFlowAfterLifecycleFinalize,
} from './use-ai-chat-turn-flow';

export interface StreamRequestLifecycle {
  assistantIdx: number;
  committedConversationSyncPromise: null | Promise<void>;
  didReceiveDoneEvent: boolean;
  didTerminalizeMessage: boolean;
  didSseEnd: boolean;
  doneAbortTimer: null | ReturnType<typeof setTimeout>;
  hasReceivedStreamPayload: boolean;
  interruptedHistoryBaseline: number;
  knownConversationIdsBeforeSend: Set<number>;
  requestAbortController: AbortController;
  shouldSyncCommittedConversation: boolean;
  shouldSyncInterruptedConversation: boolean;
  streamConversationId: null | number;
  streamLifecycle: null | { abortReason: StreamAbortReason };
  targetAgentId: number;
  applyAssistantError: (appError: AppErrorInfo) => void;
  clearDoneAbortTimer: () => void;
  getAssistantMessage: () => ChatMessage | undefined;
  scheduleDoneAbort: () => void;
  terminalizeMessage: (options?: { markInterrupted?: boolean }) => void;
  triggerCommittedConversationSync: () => void;
  updateConversation: (conversationId: null | number) => void;
}

export function createStreamRequestLifecycle(
  deps: StreamRequestDeps,
  targetAgentId: number,
): StreamRequestLifecycle {
  deps.sending.value = true;
  deps.streaming.value = true;
  deps.streamControl.abortController = new AbortController();
  const requestAbortController = deps.streamControl.abortController;
  const streamLifecycle = { abortReason: 'none' as StreamAbortReason };
  deps.streamControl.lifecycle = streamLifecycle;

  const assistantIdx = deps.chatMessages.value.length - 1;

  const lifecycle: StreamRequestLifecycle = {
    assistantIdx,
    committedConversationSyncPromise: null,
    didReceiveDoneEvent: false,
    didTerminalizeMessage: false,
    didSseEnd: false,
    doneAbortTimer: null,
    hasReceivedStreamPayload: false,
    interruptedHistoryBaseline: deps.chatMessages.value.length,
    knownConversationIdsBeforeSend: new Set(
      deps.conversations.value.map((conversation) => conversation.id),
    ),
    requestAbortController,
    shouldSyncCommittedConversation: false,
    shouldSyncInterruptedConversation: false,
    streamConversationId:
      deps.activeConversationId.value ?? deps.conversationAnchorId.value,
    streamLifecycle,
    targetAgentId,
    applyAssistantError(appError: AppErrorInfo) {
      const msg = lifecycle.getAssistantMessage();
      if (!msg) return;
      msg.error = appError;
      msg.requestFailedRetry = true;
      if (msg.content.trim().length > 0) {
        msg.partial = true;
      }
      msg.terminationReason = msg.terminationReason || 'error';
      msg.turnOutcome = msg.turnOutcome || 'failed';
      msg.completionReason = msg.completionReason || 'error';
    },
    clearDoneAbortTimer() {
      if (lifecycle.doneAbortTimer) {
        clearTimeout(lifecycle.doneAbortTimer);
        lifecycle.doneAbortTimer = null;
      }
    },
    terminalizeMessage(options) {
      if (lifecycle.didTerminalizeMessage) {
        return;
      }
      const msg = lifecycle.getAssistantMessage();
      if (!msg) {
        lifecycle.didTerminalizeMessage = true;
        return;
      }
      if (options?.markInterrupted) {
        msg.interrupted = true;
        msg.partial = true;
        msg.terminationReason = msg.terminationReason || 'interrupted';
        msg.turnOutcome = msg.turnOutcome || 'partial';
        msg.completionReason = msg.completionReason || 'interrupted';
      }
      msg.streaming = false;
      const orphaned = getRunningToolExecutionRefs(msg);
      const hadOrphanedRunningTools = orphaned.length > 0;
      if (hadOrphanedRunningTools) {
        console.warn(
          '[use-ai-chat] finalizeMessage: orphaned running tool(s), marking as error',
          orphaned,
        );
      }
      if (hadOrphanedRunningTools) {
        msg.turnOutcome = msg.turnOutcome || 'failed';
        msg.completionReason = msg.completionReason || 'tool_error';
      }
      lifecycle.didTerminalizeMessage = true;
      settleTurnFlowAfterLifecycleFinalize(msg);
    },
    getAssistantMessage() {
      return deps.chatMessages.value[lifecycle.assistantIdx];
    },
    scheduleDoneAbort() {
      lifecycle.clearDoneAbortTimer();
      lifecycle.doneAbortTimer = setTimeout(() => {
        deps.streamControl.abortController?.abort();
      }, 2000);
    },
    triggerCommittedConversationSync() {
      if (
        lifecycle.committedConversationSyncPromise ||
        lifecycle.streamConversationId === null ||
        deps.activeConversationId.value !== lifecycle.streamConversationId
      ) {
        return;
      }
      lifecycle.committedConversationSyncPromise = deps
        .syncConversationAfterInterrupt(
          lifecycle.streamConversationId,
          lifecycle.interruptedHistoryBaseline,
        )
        .finally(() => {
          lifecycle.committedConversationSyncPromise = null;
        });
    },
    updateConversation(conversationId: null | number) {
      if (conversationId === null || conversationId <= 0) {
        return;
      }
      lifecycle.streamConversationId = conversationId;
      deps.activeConversationId.value = conversationId;
      deps.activeConversationAgentId.value = lifecycle.targetAgentId;
      deps.rememberConversationAnchor(conversationId, lifecycle.targetAgentId);
    },
  };

  return lifecycle;
}
