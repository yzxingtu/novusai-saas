import type { Ref } from 'vue';

import type { PendingToolAction } from '#/store/shared/ai-panel';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, onUnmounted, ref, watch } from 'vue';

import { getToolCallsForDisplay } from '../ai-chat-panel/chat-message-turn-flow';

export interface PendingToolActionDisplayItem {
  allowed?: boolean;
  invokeId: string;
  operationDescription: string;
  operationLabel: string;
  params: Record<string, unknown>;
  resolved: boolean;
  startedAt: number;
  toolCallId?: string;
}

export type PendingOpDisplayItem = PendingToolActionDisplayItem;

interface UsePendingToolActionsOptions {
  chatMessages: Ref<ChatMessage[]>;
  pendingToolActions: Ref<PendingToolAction[]>;
}

export function usePendingToolActions(options: UsePendingToolActionsOptions) {
  const countdownNow = ref(Date.now());
  const hasUnresolvedToolActions = computed(() =>
    options.pendingToolActions.value.some((op) => !op.resolved),
  );
  let countdownInterval: null | ReturnType<typeof setInterval> = null;

  watch(
    hasUnresolvedToolActions,
    (has) => {
      if (has && !countdownInterval) {
        countdownInterval = setInterval(() => {
          countdownNow.value = Date.now();
        }, 1000);
      } else if (!has && countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
      }
    },
    { immediate: true },
  );

  onUnmounted(() => {
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
  });

  const allToolCallIds = computed(() => {
    const ids = new Set<string>();
    for (const msg of options.chatMessages.value ?? []) {
      for (const tc of getToolCallsForDisplay(msg) ?? []) {
        if (tc.id) ids.add(tc.id);
      }
    }
    return ids;
  });

  function toDisplayItem(op: PendingToolAction): PendingToolActionDisplayItem {
    return {
      allowed: op.allowed,
      invokeId: op.invokeId,
      operationDescription: op.operationDescription ?? '',
      operationLabel: op.operationLabel,
      params: op.params ?? {},
      resolved: op.resolved,
      startedAt: op.startedAt ?? 0,
      toolCallId: op.toolCallId,
    };
  }

  function getPendingOpsForMessage(
    msg: ChatMessage,
  ): PendingToolActionDisplayItem[] {
    const ids = new Set<string>();
    for (const tc of getToolCallsForDisplay(msg) ?? []) {
      if (tc.id) ids.add(tc.id);
    }
    return options.pendingToolActions.value
      .filter((op) => !op.resolved && op.toolCallId && ids.has(op.toolCallId))
      .map((op) => toDisplayItem(op));
  }

  const unassociatedPendingOps = computed<PendingToolActionDisplayItem[]>(
    () =>
      options.pendingToolActions.value
      .filter(
        (op) =>
          !op.resolved &&
          (!op.toolCallId || !allToolCallIds.value.has(op.toolCallId)),
      )
      .map((op) => toDisplayItem(op)),
  );

  return {
    countdownNow,
    getPendingOpsForMessage,
    unassociatedPendingOps,
  };
}
