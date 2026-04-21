import type { PendingPageOpForDisplay } from './pending-page-op';
import type { ToolDisplayItem } from './tool-call-utils';
import type { ChatMessage, ToolCallEvent } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { getToolCallsForDisplay } from './chat-message-turn-flow';
import {
  getSearchSummary,
  getStructuredToolOutput,
  getToolHeadlineSummary,
  getToolTargetBadges,
  hasToolCardDetails,
  isRuntimePageToolName,
} from './tool-call-utils';

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
    return tc.status === 'error';
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

  function hasPendingOpArgs(params?: Record<string, unknown>) {
    return Boolean(params && Object.keys(params).length > 0);
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
    toolCallsForDisplay.value.map((tc, idx) => {
      const hasDetails = hasToolCardDetails(tc);
      const structuredOutput = getStructuredToolOutput(tc);
      const searchSummary = getSearchSummary(tc);
      return {
        index: idx,
        tc,
        hasDetails,
        expanded: hasDetails ? isToolExpanded(tc, idx) : false,
        headlineSummary: getToolHeadlineSummary(tc),
        searchSummary,
        structuredOutput,
        targetBadges: getToolTargetBadges(tc),
      };
    }),
  );

  /** Whether this tool call has a pending confirmation (inline) */
  function hasPendingForToolCall(tc: {
    id?: string;
    name: string;
    status: string;
  }): boolean {
    if (tc.status !== 'running') return false;
    if (!isRuntimePageToolName(tc.name)) return false;
    if (!props.pendingOps?.length) return false;
    const matched = props.pendingOps.some(
      (op) => op.toolCallId && op.toolCallId === tc.id && !op.resolved,
    );
    if (matched) return true;
    return props.pendingOps.some((op) => !op.toolCallId && !op.resolved);
  }

  /** Display sub-state for running tools: waiting_confirm vs executing */
  function getToolDisplayState(tc: {
    id?: string;
    name: string;
    status: string;
  }): 'executing' | 'waiting_confirm' {
    if (tc.status !== 'running') return 'executing';
    if (hasPendingForToolCall(tc)) return 'waiting_confirm';
    return 'executing';
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

  const toolGroupSummary = computed(() => {
    const tools = toolCallsForDisplay.value;
    if (!tools?.length) return null;
    const total = tools.length;
    const success = tools.filter((tc) => tc.status === 'success').length;
    const error = tools.filter((tc) => tc.status === 'error').length;
    const running = tools.filter((tc) => tc.status === 'running').length;
    return { total, success, error, running };
  });

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
