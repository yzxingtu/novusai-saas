import type { PendingPageOpForDisplay } from './pending-page-op';
import type { ToolDisplayItem } from './tool-call-utils';
import type { ChatMessage, ToolCallEvent } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { getToolCallsForDisplay } from './chat-message-turn-flow';
import {
  hasToolCardDetails,
} from './tool-call-utils';
import {
  buildToolDisplayItems,
  getToolDisplayState as resolveToolDisplayState,
  getToolGroupSummary,
  hasPendingOpArgs,
  shouldToolExpandByDefault,
} from './chat-message-tool-call-display-helpers';

interface UseChatMessageToolCallsProps {
  index: number;
  msg: ChatMessage;
  pendingOps?: PendingPageOpForDisplay[];
}

export function useChatMessageToolCalls(props: UseChatMessageToolCallsProps) {
  const toolExpandedMap = ref<Record<number, boolean>>({});
  const toolRawExpandedMap = ref<Record<number, boolean>>({});
  const pendingOpExpandedMap = ref<Record<string, boolean>>({});

  function isToolExpanded(
    tc: Pick<ToolCallEvent, 'status' | 'summaryPayload'>,
    idx: number,
  ) {
    const existing = toolExpandedMap.value[idx];
    if (existing !== undefined) {
      return existing;
    }
    return shouldToolExpandByDefault(tc);
  }

  function toggleToolExpand(
    tc: Pick<
      ToolCallEvent,
      'arguments' | 'error' | 'output' | 'status' | 'summaryPayload'
    >,
    idx: number,
  ) {
    if (!hasToolCardDetails(tc)) return;
    toolExpandedMap.value = {
      ...toolExpandedMap.value,
      [idx]: !isToolExpanded(tc, idx),
    };
  }

  function isToolRawExpanded(idx: number) {
    return Boolean(toolRawExpandedMap.value[idx]);
  }

  function toggleToolRawExpand(idx: number) {
    toolRawExpandedMap.value = {
      ...toolRawExpandedMap.value,
      [idx]: !toolRawExpandedMap.value[idx],
    };
  }

  function isPendingOpExpanded(invokeId: string) {
    return Boolean(pendingOpExpandedMap.value[invokeId]);
  }

  function togglePendingOpExpand(invokeId: string) {
    pendingOpExpandedMap.value = {
      ...pendingOpExpandedMap.value,
      [invokeId]: !pendingOpExpandedMap.value[invokeId],
    };
  }

  const toolCallsForDisplay = computed(
    () => getToolCallsForDisplay(props.msg) ?? [],
  );

  const toolDisplayItems = computed<ToolDisplayItem[]>(() =>
    buildToolDisplayItems(toolCallsForDisplay.value, {
      resolveExpanded: (tc, idx) =>
        hasToolCardDetails(tc) ? isToolExpanded(tc, idx) : false,
    }),
  );

  /** Display sub-state for running tools: waiting_confirm vs executing */
  function getToolDisplayState(
    tc: Pick<ToolCallEvent, 'id' | 'name' | 'status'>,
  ): 'executing' | 'waiting_confirm' {
    return resolveToolDisplayState(tc, props.pendingOps);
  }

  /** Ticking now for "still running" countdown (8s+) */
  const now = ref(Date.now());
  const hasRunningTool = computed(() =>
    toolCallsForDisplay.value.some((tc) => tc.status === 'running'),
  );
  let tickInterval: null | ReturnType<typeof setInterval> = null;
  function startTick() {
    if (tickInterval) return;
    tickInterval = setInterval(() => {
      now.value = Date.now();
    }, 1000);
  }
  function stopTick() {
    if (tickInterval) {
      clearInterval(tickInterval);
      tickInterval = null;
    }
  }
  watch(
    hasRunningTool,
    (running) => {
      if (running) startTick();
      else stopTick();
    },
    { immediate: true },
  );
  onUnmounted(stopTick);

  const toolGroupExpandedMap = ref<Record<number, boolean>>({});

  const toolGroupSummary = computed(() =>
    getToolGroupSummary(toolCallsForDisplay.value),
  );

  function isToolGroupExpanded(idx: number): boolean {
    const explicit = toolGroupExpandedMap.value[idx];
    if (explicit !== undefined) return explicit;
    return hasRunningTool.value || !!props.msg.streaming;
  }

  function toggleToolGroupExpand(idx: number) {
    toolGroupExpandedMap.value = {
      ...toolGroupExpandedMap.value,
      [idx]: !isToolGroupExpanded(idx),
    };
  }

  watch(
    () => [hasRunningTool.value, props.msg.streaming, props.index] as const,
    ([running, streaming, idx], oldVal) => {
      const wasRunning = oldVal?.[0];
      const wasStreaming = oldVal?.[1];
      if (
        typeof idx === 'number' &&
        ((wasRunning === true && running === false) ||
          (wasStreaming === true && streaming === false && !running))
      ) {
        toolGroupExpandedMap.value = {
          ...toolGroupExpandedMap.value,
          [idx]: false,
        };
      }
    },
  );

  return {
    getToolDisplayState,
    hasPendingOpArgs,
    isPendingOpExpanded,
    isToolExpanded,
    isToolGroupExpanded,
    isToolRawExpanded,
    now,
    togglePendingOpExpand,
    toggleToolExpand,
    toggleToolGroupExpand,
    toggleToolRawExpand,
    toolCallsForDisplay,
    toolDisplayItems,
    toolGroupSummary,
  };
}
