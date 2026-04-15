import type { Ref } from 'vue';

import type { PendingPageOp } from '#/store/shared/ai-panel';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, onUnmounted, ref, watch } from 'vue';

export interface PendingOpDisplayItem {
  allowed?: boolean;
  invokeId: string;
  operationDescription: string;
  operationLabel: string;
  params: Record<string, unknown>;
  resolved: boolean;
  startedAt: number;
  toolCallId?: string;
}

interface UsePendingPageOpsOptions {
  chatMessages: Ref<ChatMessage[]>;
  pendingPageOps: Ref<PendingPageOp[]>;
}

export function usePendingPageOps(options: UsePendingPageOpsOptions) {
  const countdownNow = ref(Date.now());
  const hasUnresolvedPageOps = computed(() =>
    options.pendingPageOps.value.some((op) => !op.resolved),
  );
  let countdownInterval: null | ReturnType<typeof setInterval> = null;

  watch(
    hasUnresolvedPageOps,
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
      for (const tc of msg.toolCalls || []) {
        if (tc.id) ids.add(tc.id);
      }
    }
    return ids;
  });

  function toDisplayItem(op: PendingPageOp): PendingOpDisplayItem {
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

  function getPendingOpsForMessage(msg: ChatMessage): PendingOpDisplayItem[] {
    const ids = new Set<string>();
    for (const tc of msg.toolCalls || []) {
      if (tc.id) ids.add(tc.id);
    }
    return options.pendingPageOps.value
      .filter((op) => !op.resolved && op.toolCallId && ids.has(op.toolCallId))
      .map(toDisplayItem);
  }

  const unassociatedPendingOps = computed<PendingOpDisplayItem[]>(() =>
    options.pendingPageOps.value
      .filter(
        (op) =>
          !op.resolved &&
          (!op.toolCallId || !allToolCallIds.value.has(op.toolCallId)),
      )
      .map(toDisplayItem),
  );

  return {
    countdownNow,
    getPendingOpsForMessage,
    unassociatedPendingOps,
  };
}
