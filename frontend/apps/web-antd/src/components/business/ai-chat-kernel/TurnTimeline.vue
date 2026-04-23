<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { MarkdownRender } from '#/components/business/markdown-render';
import {
  getThinkingContentForDisplay,
  getOptimizingToolsForDisplay,
  getRagSourcesForDisplay,
  getToolCallsForDisplay,
} from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import ChatMessageThinkingBlock from '#/components/business/ai-chat-panel/ChatMessageThinkingBlock.vue';
import ChatMessageToolCalls from '#/components/business/ai-chat-panel/ChatMessageToolCalls.vue';
import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    index?: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
    state: TurnFlowState;
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    index: 0,
    pendingOps: () => [],
  },
);

const emit = defineEmits<{
  copy: [content: string];
}>();

const timeline = computed(() => props.state.timeline);
const isLiveMessage = computed(() => props.msg.streaming === true);
const isProcessExpanded = ref(false);
const liveProcessStatusLabel = computed(() =>
  $t('common.globalAiChat.turnStageStatus.running'),
);
const processTerminalStage = computed(() => visibleTimeline.value.at(-1));
const processStatusLabel = computed(() => {
  if (isLiveMessage.value) {
    return liveProcessStatusLabel.value;
  }
  const stage = processTerminalStage.value;
  if (!stage) {
    return undefined;
  }
  return getStageStatusLabel(stage);
});
const displayOptimizingTools = computed(() =>
  getOptimizingToolsForDisplay(props.msg),
);
const displayThinkingContent = computed(() =>
  getThinkingContentForDisplay(props.msg),
);
const displayToolCalls = computed(
  () => getToolCallsForDisplay(props.msg) ?? [],
);
const displayRagSources = computed(
  () => getRagSourcesForDisplay(props.msg) ?? [],
);

function normalizeIdentityPart(value: unknown): string | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return normalizeOptionalString(value);
}

function hashIdentityParts(parts: string[]): string {
  let hash = 2_166_136_261;
  const joined = parts.join('\u001F');
  for (let index = 0; index < joined.length; index += 1) {
    hash ^= joined.codePointAt(index) ?? 0;
    hash = Math.imul(hash, 16_777_619);
  }
  return (hash >>> 0).toString(36);
}

function resolveMessageIdentity(msg: ChatMessage): string {
  const messageRecord = msg as unknown as Record<string, unknown>;
  const persistedId = [
    messageRecord.message_id,
    messageRecord.messageId,
    messageRecord.id,
  ]
    .map((value) => normalizeIdentityPart(value))
    .find(Boolean);
  if (persistedId) {
    return `persisted:${persistedId}`;
  }

  const normalizedClientKey = normalizeOptionalString(msg.clientKey);
  if (normalizedClientKey) {
    return `client:${normalizedClientKey}`;
  }

  const content = normalizeMergedTextPart(msg.content) || msg.content;
  return `fallback:${hashIdentityParts([
    msg.role,
    normalizeOptionalString(msg.created_at) ?? '',
    String(content.length),
    content.slice(0, 256),
  ])}`;
}

const messageIdentity = computed(() => resolveMessageIdentity(props.msg));

const GENERIC_STAGE_STATUS_TOKENS = new Set([
  'completed',
  'error',
  'failed',
  'in progress',
  'interrupted',
  'running',
  'skipped',
]);

const GENERIC_STAGE_COPY_BY_TYPE: Record<
  TurnFlowStageForDisplay['type'],
  readonly string[]
> = {
  answer_assembly: [
    'answer assembly',
    'assembling answer',
    'assembling the final answer',
    'final answer assembly',
    'response assembly',
  ],
  completed: [
    'complete',
    'completed',
    'done',
    'process complete',
    'process completed',
    'turn complete',
    'turn completed',
    'workflow complete',
    'workflow completed',
  ],
  failed: [
    'error',
    'errored',
    'failed',
    'failure',
    'process failed',
    'turn failed',
    'workflow failed',
  ],
  retrieval: [
    'evidence retrieval',
    'information retrieval',
    'no evidence retrieved',
    'retrieval',
    'source retrieval',
  ],
  thinking: ['analysis', 'reasoning', 'thinking'],
  tool_execution: [
    'executing tools',
    'no tools executed',
    'tool call execution',
    'tool calls',
    'tool execution',
  ],
  tool_selection: [
    'select tools',
    'selecting tools',
    'tool filtering',
    'tool selection',
  ],
};

function normalizeAsciiStageCopy(value: unknown): string | undefined {
  const normalized = normalizeOptionalString(value);
  if (
    !normalized ||
    /[^\u0000-\u007F]/.test(normalized) ||
    !/[A-Za-z]/.test(normalized)
  ) {
    return undefined;
  }
  const collapsed = normalized
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return collapsed.length > 0 ? collapsed : undefined;
}

function isGenericBackendStageCopy(
  stage: TurnFlowStageForDisplay,
  value: unknown,
) {
  const normalized = normalizeAsciiStageCopy(value);
  if (!normalized) {
    return false;
  }
  const normalizedType = stage.type.replace(/_/g, ' ');
  const normalizedStatus = stage.status.replace(/_/g, ' ');
  return (
    GENERIC_STAGE_STATUS_TOKENS.has(normalized) ||
    GENERIC_STAGE_COPY_BY_TYPE[stage.type].includes(normalized) ||
    normalized === normalizedType ||
    normalized === `${normalizedType} ${normalizedStatus}` ||
    normalized === `${normalizedStatus} ${normalizedType}`
  );
}

function getMeaningfulStageTitle(stage: TurnFlowStageForDisplay) {
  const title = normalizeOptionalString(stage.title);
  if (!title || isGenericBackendStageCopy(stage, title)) {
    return undefined;
  }
  return title;
}

function getMeaningfulStageSummary(stage: TurnFlowStageForDisplay) {
  const summary = normalizeOptionalString(stage.summary);
  if (!summary || isGenericBackendStageCopy(stage, summary)) {
    return undefined;
  }
  return summary === getMeaningfulStageTitle(stage) ? undefined : summary;
}

function getStageKey(stage: TurnFlowStageForDisplay, index: number) {
  return `${messageIdentity.value}:${stage.id}-${index}`;
}

function getStageTypeLabel(stage: TurnFlowStageForDisplay) {
  const stageTitle = getMeaningfulStageTitle(stage);
  if (stageTitle) {
    return stageTitle;
  }
  return $t(`common.globalAiChat.turnStageType.${stage.type}`);
}

function getStageStatusLabel(stage: TurnFlowStageForDisplay) {
  return $t(`common.globalAiChat.turnStageStatus.${stage.status}`);
}

function normalizeMetricNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function readMetricNumber(
  metrics: Record<string, number | string>,
  keys: string[],
): number | undefined {
  for (const key of keys) {
    const normalized = normalizeMetricNumber(metrics[key]);
    if (normalized !== undefined) {
      return normalized;
    }
  }
  return undefined;
}

function readMetricText(
  metrics: Record<string, number | string>,
  keys: string[],
): string | undefined {
  for (const key of keys) {
    const normalized = normalizeOptionalString(metrics[key]);
    if (normalized) {
      return normalized;
    }
  }
  return undefined;
}

function getMetricSummaryForStage(
  stage: TurnFlowStageForDisplay,
): string | undefined {
  const metrics = stage.metrics ?? {};
  if (stage.type === 'tool_selection') {
    const selected = readMetricNumber(metrics, [
      'selected',
      'candidate_tools_count',
      'candidateToolsCount',
      'selected_count',
      'selectedCount',
    ]);
    const total = Math.max(
      selected ?? 0,
      readMetricNumber(metrics, [
        'total',
        'all_tools_count',
        'allToolsCount',
        'total_tools_count',
        'totalToolsCount',
        'candidate_count',
        'candidateCount',
      ]) ?? 0,
    );
    if (total > 0) {
      return $t('common.globalAiChat.optimizingTools', {
        total,
        selected: selected ?? 0,
      });
    }
  }

  if (stage.type === 'tool_execution') {
    const total = Math.max(
      readMetricNumber(metrics, ['total', 'tool_rounds', 'tool_call_count']) ??
        0,
      (readMetricNumber(metrics, ['completed_tool_calls']) ?? 0) +
        (readMetricNumber(metrics, ['failed_tool_calls']) ?? 0),
    );
    if (total > 0) {
      return stage.status === 'running'
        ? $t('common.globalAiChat.toolGroupRunning', { count: total })
        : $t('common.globalAiChat.toolGroupSummary', { count: total });
    }
  }

  if (stage.type === 'retrieval') {
    const count = readMetricNumber(metrics, [
      'count',
      'source_count',
      'sourceCount',
      'result_count',
      'resultCount',
      'evidence_count',
      'evidenceCount',
      'total',
    ]);
    if (count !== undefined && count > 0) {
      return $t('common.globalAiChat.turnRetrievalSummary', { count });
    }
  }

  return undefined;
}

function getStageSummary(stage: TurnFlowStageForDisplay) {
  const stageSummary = getMeaningfulStageSummary(stage);
  if (stageSummary) {
    return stageSummary;
  }

  if (stage.type === 'failed') {
    const errorSurface = props.state.flow.errorSurface;
    const errorMessage =
      (typeof errorSurface?.message === 'string' &&
        errorSurface.message.trim()) ||
      (typeof errorSurface?.summary === 'string' &&
        errorSurface.summary.trim()) ||
      undefined;
    if (errorMessage) {
      return errorMessage;
    }
  }

  const metricSummary = getMetricSummaryForStage(stage);
  if (metricSummary) {
    return metricSummary;
  }

  const metrics = stage.metrics ?? {};
  if (stage.type === 'tool_execution' && stage.status === 'running') {
    const provider =
      readMetricText(metrics, [
        'provider',
        'selected_backend',
        'selectedBackend',
        'provider_name',
        'providerName',
      ]) ?? readMetricText(metrics, ['provider_chain', 'providerChain']);
    if (provider) {
      return `${$t('common.globalAiChat.toolSearchProvider')}: ${provider}`;
    }
  }

  if (stage.status === 'running') {
    return $t(`common.globalAiChat.turnStageSummary.${stage.type}`);
  }

  return `${getStageTypeLabel(stage)} · ${getStageStatusLabel(stage)}`;
}

function getStageStatusClass(stage: TurnFlowStageForDisplay) {
  if (stage.status === 'running') {
    return 'border-primary/18 bg-primary/[0.08] text-primary';
  }
  if (stage.status === 'interrupted') {
    return 'border-amber-500/16 bg-amber-500/[0.10] text-amber-700 dark:text-amber-300';
  }
  if (stage.status === 'completed') {
    return 'border-emerald-500/16 bg-emerald-500/[0.10] text-emerald-700 dark:text-emerald-300';
  }
  return 'border-red-500/16 bg-red-500/[0.10] text-red-500';
}

function shouldShowStageStatus(stage: TurnFlowStageForDisplay) {
  return (
    stage.status === 'running' ||
    stage.status === 'error' ||
    stage.status === 'interrupted'
  );
}

function getProcessStatusClass() {
  const stage = processTerminalStage.value;
  if (isLiveMessage.value) {
    return 'border-primary/16 bg-primary/[0.08] text-primary';
  }
  if (stage?.status === 'error') {
    return 'border-red-500/16 bg-red-500/[0.10] text-red-500';
  }
  if (stage?.status === 'interrupted') {
    return 'border-amber-500/16 bg-amber-500/[0.10] text-amber-700 dark:text-amber-300';
  }
  return 'border-emerald-500/16 bg-emerald-500/[0.10] text-emerald-700 dark:text-emerald-300';
}

function getThinkingBodyContent(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'thinking') {
    return undefined;
  }
  if (displayThinkingContent.value) {
    return displayThinkingContent.value;
  }
  const detailText = (stage.detailLines ?? [])
    .map((line) => normalizeOptionalString(line))
    .filter((line): line is string => Boolean(line))
    .join('\n\n');
  if (detailText) {
    return detailText;
  }
  return getMeaningfulStageSummary(stage);
}

const lastToolSelectionStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'tool_selection')?.id,
);
const lastToolExecutionStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'tool_execution')?.id,
);
const lastRetrievalStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'retrieval')?.id,
);

function hasThinkingBody(stage: TurnFlowStageForDisplay) {
  return stage.type === 'thinking' && Boolean(getThinkingBodyContent(stage));
}

function isEmbeddedThinkingStage(stage: TurnFlowStageForDisplay) {
  return hasThinkingBody(stage) && Boolean(displayThinkingContent.value);
}

function hasToolSelectionBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_selection' &&
    stage.id === lastToolSelectionStageId.value &&
    (displayOptimizingTools.value?.selected ?? 0) > 0 &&
    (displayOptimizingTools.value?.total ?? 0) > 0
  );
}

function hasToolExecutionBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_execution' &&
    stage.id === lastToolExecutionStageId.value &&
    displayToolCalls.value.length > 0
  );
}

function hasRetrievalBody(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'retrieval' &&
    stage.id === lastRetrievalStageId.value &&
    displayRagSources.value.length > 0
  );
}

function hasStageBody(stage: TurnFlowStageForDisplay) {
  return (
    hasThinkingBody(stage) ||
    hasToolSelectionBody(stage) ||
    hasToolExecutionBody(stage) ||
    hasRetrievalBody(stage)
  );
}

function shouldHideCompletedAnswerAssembly(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'answer_assembly' &&
    stage.status === 'completed' &&
    Boolean(
      props.state.answerCard || normalizeMergedTextPart(props.msg.content),
    )
  );
}

function shouldHideSkippedToolSelection(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_selection' &&
    stage.status === 'skipped' &&
    (displayOptimizingTools.value?.selected ?? 0) === 0
  );
}

function shouldHideNoopToolExecution(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'tool_execution' || displayToolCalls.value.length > 0) {
    return false;
  }
  const metrics = stage.metrics ?? {};
  const total =
    readMetricNumber(metrics, ['total', 'tool_rounds', 'tool_call_count']) ?? 0;
  return (
    total <= 0 &&
    stage.status !== 'running' &&
    !(stage.detailLines?.length && stage.detailLines.length > 0)
  );
}

function shouldHideNoopRetrieval(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'retrieval' || displayRagSources.value.length > 0) {
    return false;
  }
  const metrics = stage.metrics ?? {};
  const total =
    readMetricNumber(metrics, [
      'count',
      'source_count',
      'sourceCount',
      'result_count',
      'resultCount',
      'evidence_count',
      'evidenceCount',
      'total',
    ]) ?? 0;
  return (
    total <= 0 &&
    stage.status !== 'running' &&
    !(stage.detailLines?.length && stage.detailLines.length > 0)
  );
}

function shouldRenderStage(stage: TurnFlowStageForDisplay) {
  if (stage.type === 'completed') {
    return false;
  }
  if (shouldHideCompletedAnswerAssembly(stage)) {
    return false;
  }
  if (shouldHideSkippedToolSelection(stage)) {
    return false;
  }
  if (shouldHideNoopToolExecution(stage)) {
    return false;
  }
  if (shouldHideNoopRetrieval(stage)) {
    return false;
  }
  if (stage.type === 'thinking') {
    return Boolean(
      normalizeOptionalString(stage.summary) ||
        normalizeOptionalString(stage.title) ||
        hasThinkingBody(stage),
    );
  }
  return true;
}

const visibleTimeline = computed(() =>
  timeline.value.filter((stage) => shouldRenderStage(stage)),
);

const processHeadline = computed(() => {
  const liveStage = visibleTimeline.value.findLast(
    (stage) => stage.status === 'running',
  );
  const stage = liveStage ?? visibleTimeline.value.at(-1);
  return stage ? getStageSummary(stage) : undefined;
});

function syncProcessExpanded(nextExpanded: boolean) {
  if (isProcessExpanded.value === nextExpanded) {
    return;
  }
  isProcessExpanded.value = nextExpanded;
}

function toggleProcessExpanded() {
  syncProcessExpanded(!isProcessExpanded.value);
}

watch(
  messageIdentity,
  () => {
    syncProcessExpanded(isLiveMessage.value);
  },
  { immediate: true },
);

watch(
  () => props.msg.streaming === true,
  (isStreaming, wasStreaming) => {
    if (isStreaming && !wasStreaming) {
      syncProcessExpanded(true);
    } else if (!isStreaming && wasStreaming) {
      syncProcessExpanded(false);
    }
  },
);
</script>

<template>
  <div
    v-if="visibleTimeline.length > 0"
    data-testid="chat-message-kernel-timeline"
    class="min-w-0"
  >
    <button
      type="button"
      :aria-expanded="isProcessExpanded"
      data-testid="turn-process-toggle"
      :title="
        isProcessExpanded
          ? $t('common.globalAiChat.turnTimelineCollapse')
          : $t('common.globalAiChat.turnTimelineExpand')
      "
      class="turn-process-toggle group flex w-full items-start gap-2 rounded-xl px-0.5 py-0.5 text-left"
      @click="toggleProcessExpanded"
    >
      <span
        class="mt-0.5 inline-flex shrink-0 items-center rounded-full border border-border/26 bg-background/72 px-1.5 py-0.5 text-[8.5px] font-medium uppercase tracking-[0.14em] text-muted-foreground/58"
      >
        {{ $t('common.globalAiChat.turnTimeline') }}
      </span>

      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 flex-wrap items-center gap-1.5">
          <p
            class="min-w-0 flex-1 truncate font-medium text-foreground/76"
            :class="compact ? 'text-[10px] leading-5' : 'text-[10.5px] leading-5'"
          >
            {{
              processHeadline ||
              $t('common.globalAiChat.turnStageSummary.answer_assembly')
            }}
          </p>
          <span
            v-if="processStatusLabel"
            class="inline-flex items-center rounded-full border px-1.5 py-0.5 text-[9px] font-medium"
            :class="getProcessStatusClass()"
          >
            {{ processStatusLabel }}
          </span>
          <span
            class="inline-flex items-center rounded-full border border-border/14 bg-background/70 px-1.5 py-0.5 text-[9px] text-muted-foreground/62"
          >
            {{
              $t('common.globalAiChat.turnStageCount', {
                count: visibleTimeline.length,
              })
            }}
          </span>
        </div>
      </div>
      <span
        class="mt-0.5 inline-flex shrink-0 items-center justify-center rounded-full border border-border/14 bg-background/70 p-1 text-muted-foreground/48 transition-colors group-hover:border-primary/18 group-hover:text-primary/72"
      >
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-3 transition-transform duration-200"
          :style="{
            transform: isProcessExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
          }"
        />
      </span>
    </button>

    <div
      data-testid="turn-process-body"
      class="grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-out"
      :style="{
        gridTemplateRows: isProcessExpanded ? '1fr' : '0fr',
        opacity: isProcessExpanded ? 1 : 0,
      }"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="relative mt-2 border-l border-border/22"
          :class="compact ? 'space-y-2 pl-3' : 'space-y-2.5 pl-3.5'"
        >
          <div
            v-for="(stage, stageIndex) in visibleTimeline"
            :key="getStageKey(stage, stageIndex)"
            class="relative min-w-0"
            :class="compact ? 'pl-2.5' : 'pl-3'"
            :data-testid="`turn-stage-${stageIndex}`"
          >
            <div
              class="absolute top-[7px] flex size-3 items-center justify-center rounded-full bg-background"
              :class="compact ? 'left-[-12px]' : 'left-[-14px]'"
            >
              <span
                class="block rounded-full"
                :class="[
                  compact ? 'size-[6px]' : 'size-[6px]',
                  stage.status === 'running'
                    ? 'bg-primary'
                    : stage.status === 'completed'
                      ? 'bg-emerald-500'
                      : stage.status === 'interrupted'
                        ? 'bg-amber-500'
                        : stage.status === 'skipped'
                          ? 'bg-muted-foreground/35'
                          : 'bg-red-500',
                  stage.status === 'running' ? 'tc-dot-pulse' : '',
                ]"
              ></span>
            </div>

            <div class="min-w-0">
              <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                <span
                  class="truncate font-medium text-foreground/74"
                  :class="compact ? 'text-[10px]' : 'text-[10px]'"
                >
                  {{ getStageTypeLabel(stage) }}
                </span>
                <span
                  v-if="shouldShowStageStatus(stage)"
                  class="inline-flex shrink-0 items-center rounded-full border px-1.5 py-0.5 text-[9px] font-medium"
                  :class="getStageStatusClass(stage)"
                >
                  {{ getStageStatusLabel(stage) }}
                </span>
              </div>
              <p
                class="mt-0.5 text-muted-foreground/58"
                :class="compact ? 'text-[10px] leading-5' : 'text-[10px] leading-5'"
              >
                {{ getStageSummary(stage) }}
              </p>

              <div
                v-if="hasStageBody(stage)"
                class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                :data-testid="`turn-stage-body-${stageIndex}`"
                :style="{
                  gridTemplateRows: isProcessExpanded ? '1fr' : '0fr',
                  opacity: isProcessExpanded ? 1 : 0,
                }"
              >
                <div class="min-h-0 overflow-hidden">
                  <div
                    class="mt-1.5 min-w-0"
                    :class="compact ? 'pl-0.5' : 'pl-1'"
                  >
                    <ChatMessageThinkingBlock
                      v-if="isEmbeddedThinkingStage(stage)"
                      :compact="compact"
                      embedded
                      :index="0"
                      :msg="msg"
                    />

                    <div
                      v-else-if="hasThinkingBody(stage)"
                      class="turn-stage-inline-markdown min-w-0"
                    >
                      <MarkdownRender
                        :content="getThinkingBodyContent(stage) ?? ''"
                        :streaming="false"
                      />
                    </div>

                    <div
                      v-else-if="hasToolSelectionBody(stage)"
                      class="inline-flex max-w-full items-center gap-1.5 rounded-lg bg-muted/[0.05] px-2.5 py-2 text-muted-foreground/70"
                      :class="compact ? 'text-[10px]' : 'text-[11px]'"
                    >
                      <IconifyIcon
                        icon="lucide:sparkles"
                        class="size-3 text-primary"
                      />
                      <span>{{
                        $t('common.globalAiChat.optimizingTools', {
                          total: displayOptimizingTools?.total ?? 0,
                          selected: displayOptimizingTools?.selected ?? 0,
                        })
                      }}</span>
                    </div>

                    <ChatMessageToolCalls
                      v-else-if="hasToolExecutionBody(stage)"
                      :compact="compact"
                      :countdown-now="countdownNow"
                      embedded
                      :index="0"
                      :msg="msg"
                      :pending-ops="pendingOps"
                      @copy="(content) => emit('copy', content)"
                    />

                    <div
                      v-else-if="hasRetrievalBody(stage)"
                      class="space-y-1.5"
                    >
                      <div
                        v-for="(source, sourceIndex) in displayRagSources"
                        :key="`${stage.id}-source-${source.doc_id}-${sourceIndex}`"
                        class="min-w-0 rounded-lg bg-muted/[0.04] px-2.5 py-2"
                      >
                        <div class="flex min-w-0 items-start gap-2">
                          <IconifyIcon
                            icon="lucide:book-open"
                            class="mt-0.5 size-3 shrink-0 text-primary/68"
                          />
                          <div class="min-w-0 flex-1">
                            <div
                              class="flex min-w-0 flex-wrap items-center gap-1.5"
                            >
                              <span
                                class="truncate text-[10px] font-medium text-foreground/74"
                              >
                                {{ source.doc_name }}
                              </span>
                              <span
                                v-if="source.knowledge_base_name"
                                class="text-[9px] text-muted-foreground/58"
                              >
                                {{ source.knowledge_base_name }}
                              </span>
                            </div>
                            <p
                              v-if="source.snippet"
                              class="mt-0.5 line-clamp-2 text-[10px] leading-5 text-muted-foreground/60"
                            >
                              {{ source.snippet }}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.turn-stage-inline-markdown {
  min-width: 0;
  color: hsl(var(--foreground) / 0.7);
  font-size: 0.75rem;
  line-height: 1.35rem;
}

.turn-stage-inline-markdown :deep(p:first-child) {
  margin-top: 0;
}

.turn-stage-inline-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.turn-stage-inline-markdown :deep(ul),
.turn-stage-inline-markdown :deep(ol) {
  margin: 0.5rem 0 0;
  padding-inline-start: 1.1rem;
}

.turn-stage-inline-markdown :deep(li + li) {
  margin-top: 0.25rem;
}
</style>
