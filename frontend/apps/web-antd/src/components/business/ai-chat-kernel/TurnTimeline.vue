<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type { PendingToolActionForDisplay } from '#/components/business/ai-chat-panel/pending-tool-action';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  getOptimizingToolsForDisplay,
  getRagSourcesForDisplay,
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
} from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import ChatMessageThinkingBlock from '#/components/business/ai-chat-panel/ChatMessageThinkingBlock.vue';
import ChatMessageToolCalls from '#/components/business/ai-chat-panel/ChatMessageToolCalls.vue';
import {
  normalizeMergedTextPart,
  normalizeOptionalString,
} from '#/components/business/ai-chat-panel/use-ai-chat-message-normalizers';
import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

import {
  getMeaningfulStageSummary,
  getMeaningfulStageTitle,
  getProcessHeadlineForStage,
  isNoopSkippedStage,
  getStageStatusLabel,
  getStageSummary,
  getStageTypeLabel,
  normalizeComparableStageCopy,
  normalizeMeaningfulTranscriptCopy,
  readMetricNumber,
} from './turn-stage-presentation';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    index?: number;
    msg: ChatMessage;
    pendingOps?: PendingToolActionForDisplay[];
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

const PROCESS_AUTO_COLLAPSE_DELAY_MS = 220;

const timeline = computed(() => props.state.timeline);
const isLiveMessage = computed(() => props.msg.streaming === true);
const isProcessExpanded = ref(false);
let processAutoCollapseTimer:
  | ReturnType<typeof globalThis.setTimeout>
  | undefined;
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

function getStageKey(stage: TurnFlowStageForDisplay, index: number) {
  return `${messageIdentity.value}:${stage.id}-${index}`;
}

function getStageStatusClass(stage: TurnFlowStageForDisplay) {
  if (stage.status === 'running') {
    return 'stage-status-running';
  }
  if (stage.status === 'interrupted') {
    return 'stage-status-interrupted';
  }
  if (stage.status === 'completed') {
    return 'stage-status-completed';
  }
  if (stage.status === 'skipped') {
    return 'stage-status-skipped';
  }
  return 'stage-status-error';
}

function shouldShowStageStatus(stage: TurnFlowStageForDisplay) {
  return stage.status !== 'completed';
}

function getFilteredStageDetailLines(stage: TurnFlowStageForDisplay) {
  const seen = new Set<string>();
  const titleKey = normalizeComparableStageCopy(
    getMeaningfulStageTitle(stage) ?? '',
  );
  const summaryKey = normalizeComparableStageCopy(
    getMeaningfulStageSummary(stage) ?? '',
  );

  return (stage.detailLines ?? [])
    .flatMap((line) => {
      const normalized = normalizeMeaningfulTranscriptCopy(line);
      return normalized ? [normalized] : [];
    })
    .filter((line) => {
      const comparable = normalizeComparableStageCopy(line);
      if (!comparable) {
        return false;
      }
      if (
        (titleKey && comparable === titleKey) ||
        (summaryKey && comparable === summaryKey)
      ) {
        return false;
      }
      if (seen.has(comparable)) {
        return false;
      }
      seen.add(comparable);
      return true;
    });
}

function getThinkingDetailText(stage: TurnFlowStageForDisplay) {
  return getFilteredStageDetailLines(stage).join('\n\n');
}

function getThinkingBodyContent(stage: TurnFlowStageForDisplay) {
  if (stage.type !== 'thinking') {
    return undefined;
  }
  const detailText = getThinkingDetailText(stage);
  if (detailText) {
    return detailText;
  }
  if (
    stage.id === lastThinkingStageId.value &&
    normalizeOptionalString(displayThinkingContent.value)
  ) {
    return displayThinkingContent.value;
  }
  return getMeaningfulStageSummary(stage);
}

const lastThinkingStageId = computed(
  () => timeline.value.findLast((stage) => stage.type === 'thinking')?.id,
);
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
  if (stage.type !== 'thinking') {
    return false;
  }
  const bodyContent = normalizeOptionalString(getThinkingBodyContent(stage));
  if (!bodyContent) {
    return false;
  }
  const summary = getMeaningfulStageSummary(stage);
  if (!summary || bodyContent !== summary) {
    return true;
  }
  return (
    stage.id === lastThinkingStageId.value &&
    (isLiveMessage.value || stage.status === 'running')
  );
}

function isEmbeddedThinkingStage(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'thinking' &&
    stage.id === lastThinkingStageId.value &&
    Boolean(normalizeOptionalString(displayThinkingContent.value)) &&
    hasThinkingBody(stage)
  );
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
    Boolean(props.state.answerCard || normalizeMergedTextPart(props.msg.content))
  );
}

function shouldHideMeaninglessStage(stage: TurnFlowStageForDisplay) {
  if (isNoopSkippedStage(stage)) {
    return true;
  }
  if (hasStageBody(stage)) {
    return false;
  }
  const title = normalizeOptionalString(getMeaningfulStageTitle(stage));
  const summary = normalizeOptionalString(
    getStageSummary(stage, {
      errorSurface: props.state.flow.errorSurface,
    }),
  );
  const detailCount = getFilteredStageDetailLines(stage).length;
  const metrics = stage.metrics ?? {};
  const metricCount =
    readMetricNumber(metrics, [
      'total',
      'count',
      'source_count',
      'result_count',
      'tool_call_count',
    ]) ?? 0;
  return !title && !summary && detailCount === 0 && metricCount <= 0;
}

function shouldRenderStage(stage: TurnFlowStageForDisplay) {
  if (stage.type === 'completed') {
    return false;
  }
  if (shouldHideCompletedAnswerAssembly(stage)) {
    return false;
  }
  if (stage.type === 'thinking') {
    return Boolean(
      normalizeOptionalString(stage.summary) ||
        normalizeOptionalString(stage.title) ||
        hasThinkingBody(stage),
    );
  }
  return !shouldHideMeaninglessStage(stage);
}

const visibleTimeline = computed(() =>
  timeline.value.filter((stage) => shouldRenderStage(stage)),
);
const hasRunningVisibleStage = computed(() =>
  visibleTimeline.value.some((stage) => stage.status === 'running'),
);
const lastVisibleStage = computed(() => visibleTimeline.value.at(-1));

function getVisibleStageSummary(stage: TurnFlowStageForDisplay) {
  return getStageSummary(stage, {
    errorSurface: props.state.flow.errorSurface,
  });
}

const processHeadline = computed(() => {
  const liveStage = visibleTimeline.value.findLast(
    (stage) => stage.status === 'running',
  );
  const stage = liveStage ?? visibleTimeline.value.at(-1);
  return stage
    ? getProcessHeadlineForStage(stage, {
        errorSurface: props.state.flow.errorSurface,
      })
    : undefined;
});
const processStatusLabelKey = computed(() => {
  if (isLiveMessage.value || hasRunningVisibleStage.value) {
    return 'common.globalAiChat.processing';
  }
  const terminalStatus = lastVisibleStage.value?.status;
  if (terminalStatus === 'error') {
    return 'common.globalAiChat.turnStageStatus.error';
  }
  if (terminalStatus === 'interrupted') {
    return 'common.globalAiChat.turnStageStatus.interrupted';
  }
  if (terminalStatus === 'skipped') {
    return 'common.globalAiChat.turnStageStatus.skipped';
  }
  return 'common.globalAiChat.turnStageStatus.completed';
});
const processStatusIcon = computed(() => {
  if (isLiveMessage.value || hasRunningVisibleStage.value) {
    return 'lucide:loader-circle';
  }
  if (lastVisibleStage.value?.status === 'error') {
    return 'lucide:triangle-alert';
  }
  if (lastVisibleStage.value?.status === 'interrupted') {
    return 'lucide:pause-circle';
  }
  if (lastVisibleStage.value?.status === 'skipped') {
    return 'lucide:minus-circle';
  }
  return 'lucide:check';
});
const processStatusClass = computed(() => {
  if (isLiveMessage.value || hasRunningVisibleStage.value) {
    return 'turn-process-status-running';
  }
  if (lastVisibleStage.value?.status === 'error') {
    return 'turn-process-status-error';
  }
  if (lastVisibleStage.value?.status === 'interrupted') {
    return 'turn-process-status-interrupted';
  }
  if (lastVisibleStage.value?.status === 'skipped') {
    return 'turn-process-status-skipped';
  }
  return 'turn-process-status-completed';
});

function syncProcessExpanded(nextExpanded: boolean) {
  if (isProcessExpanded.value === nextExpanded) {
    return;
  }
  isProcessExpanded.value = nextExpanded;
}

function clearProcessAutoCollapseTimer() {
  if (processAutoCollapseTimer === undefined) {
    return;
  }
  globalThis.clearTimeout(processAutoCollapseTimer);
  processAutoCollapseTimer = undefined;
}

function scheduleProcessAutoCollapse() {
  clearProcessAutoCollapseTimer();
  processAutoCollapseTimer = globalThis.setTimeout(() => {
    processAutoCollapseTimer = undefined;
    syncProcessExpanded(false);
  }, PROCESS_AUTO_COLLAPSE_DELAY_MS);
}

function toggleProcessExpanded() {
  clearProcessAutoCollapseTimer();
  syncProcessExpanded(!isProcessExpanded.value);
}

watch(
  messageIdentity,
  () => {
    clearProcessAutoCollapseTimer();
    syncProcessExpanded(isLiveMessage.value);
  },
  { immediate: true },
);

watch(
  () => props.msg.streaming === true,
  (isStreaming, wasStreaming) => {
    if (isStreaming && !wasStreaming) {
      clearProcessAutoCollapseTimer();
      syncProcessExpanded(true);
      return;
    }
    if (!isStreaming && wasStreaming) {
      scheduleProcessAutoCollapse();
    }
  },
);

watch(isLiveMessage, (isStreaming) => {
  if (isStreaming) {
    return;
  }
  if (visibleTimeline.value.length > 0) {
    return;
  }
  clearProcessAutoCollapseTimer();
});

onBeforeUnmount(() => {
  clearProcessAutoCollapseTimer();
});
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
      class="turn-process-toggle group flex w-full items-center gap-2 rounded-[14px] px-1 py-1.5 text-left"
      @click="toggleProcessExpanded"
    >
      <span class="turn-process-pill inline-flex shrink-0 items-center gap-1">
        <IconifyIcon icon="lucide:orbit" class="size-2.5" />
        {{ $t('common.globalAiChat.turnTimeline') }}
      </span>

      <span
        class="turn-process-copy min-w-0 flex-1 truncate"
        :class="
          compact
            ? 'text-[9.5px] leading-[1rem]'
            : 'text-[9.75px] leading-[1.04rem]'
        "
      >
        {{
          processHeadline ||
          $t('common.globalAiChat.turnStageSummary.answer_assembly')
        }}
      </span>

      <span class="turn-process-count">
        {{
          $t('common.globalAiChat.turnStageCount', {
            count: visibleTimeline.length,
          })
        }}
      </span>

      <span :class="['turn-process-status', processStatusClass]">
        <IconifyIcon
          :icon="processStatusIcon"
          class="turn-process-status-icon size-3"
          :class="
            isLiveMessage || hasRunningVisibleStage
              ? 'turn-process-status-spin'
              : ''
          "
        />
        <span class="truncate">{{ $t(processStatusLabelKey) }}</span>
      </span>

      <span class="turn-process-chevron inline-flex shrink-0 items-center">
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
          class="turn-process-track mt-1.5 border-l"
          :class="compact ? 'space-y-1.5 pl-2.5' : 'space-y-1.5 pl-3'"
        >
          <div
            v-for="(stage, stageIndex) in visibleTimeline"
            :key="getStageKey(stage, stageIndex)"
            class="relative min-w-0"
            :class="compact ? 'pl-2' : 'pl-2.5'"
            :data-testid="`turn-stage-${stageIndex}`"
          >
            <div
              class="absolute top-[8px] flex size-3 items-center justify-center rounded-full bg-background shadow-[0_0_0_3px_hsl(var(--background)/0.96)]"
              :class="compact ? 'left-[-13px]' : 'left-[-15px]'"
            >
              <span
                class="block rounded-full"
                :class="[
                  compact ? 'size-[6px]' : 'size-[6px]',
                  stage.status === 'running' ? 'bg-primary tc-dot-pulse' : '',
                  stage.status === 'completed' ? 'bg-emerald-500' : '',
                  stage.status === 'interrupted' ? 'bg-amber-500' : '',
                  stage.status === 'skipped' ? 'bg-muted-foreground/35' : '',
                  stage.status === 'error' ? 'bg-red-500' : '',
                ]"
              ></span>
            </div>

            <div class="turn-stage-card min-w-0 rounded-[14px] border">
              <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                <span
                  class="text-foreground/76 truncate font-medium"
                  :class="compact ? 'text-[9.5px]' : 'text-[9.75px]'"
                >
                  {{ getStageTypeLabel(stage) }}
                </span>
                <span
                  v-if="shouldShowStageStatus(stage)"
                  class="turn-stage-status inline-flex shrink-0 items-center rounded-full px-1.5 py-0.5 text-[8.5px] font-medium"
                  :class="getStageStatusClass(stage)"
                >
                  {{ getStageStatusLabel(stage) }}
                </span>
              </div>

              <p
                class="text-muted-foreground/60 mt-0.5"
                :class="
                  compact
                    ? 'text-[9px] leading-[1rem]'
                    : 'text-[9.25px] leading-[1.04rem]'
                "
              >
                {{ getVisibleStageSummary(stage) }}
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
                  <div class="mt-1.5 min-w-0" :class="compact ? 'pl-0.5' : 'pl-1'">
                    <div
                      class="turn-stage-detail-surface min-w-0 rounded-[14px] border"
                      :class="compact ? 'px-2.5 py-2' : 'px-2.5 py-2.5'"
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
                        class="inline-flex max-w-full items-center gap-1.5 rounded-[12px] bg-muted/[0.05] px-2.5 py-2 text-muted-foreground/72"
                        :class="compact ? 'text-[9.75px]' : 'text-[10px]'"
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
                          class="min-w-0 rounded-[13px] bg-muted/[0.04] px-2.5 py-2"
                        >
                          <div class="flex min-w-0 items-start gap-2">
                            <IconifyIcon
                              icon="lucide:book-open"
                              class="text-primary/68 mt-0.5 size-3 shrink-0"
                            />
                            <div class="min-w-0 flex-1">
                              <div
                                class="flex min-w-0 flex-wrap items-center gap-1.5"
                              >
                                <span
                                  class="text-foreground/76 truncate text-[10px] font-medium"
                                >
                                  {{ source.doc_name }}
                                </span>
                                <span
                                  v-if="source.knowledge_base_name"
                                  class="text-muted-foreground/56 text-[9px]"
                                >
                                  {{ source.knowledge_base_name }}
                                </span>
                              </div>
                              <p
                                v-if="source.snippet"
                                class="mt-0.5 line-clamp-2 text-[9.5px] leading-5 text-muted-foreground/62"
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
  </div>
</template>

<style scoped>
.turn-process-toggle {
  border: 1px solid transparent;
  background: transparent;
  transition:
    background-color 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.turn-process-toggle:hover {
  border-color: hsl(var(--border) / 0.08);
  background: hsl(var(--muted) / 0.12);
}

.turn-process-pill {
  color: hsl(var(--primary) / 0.74);
  border: 1px solid hsl(var(--primary) / 0.12);
  background: hsl(var(--primary) / 0.06);
  border-radius: 9999px;
  padding: 0.2rem 0.45rem;
  font-size: 0.52rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.turn-process-copy {
  color: hsl(var(--foreground) / 0.72);
  letter-spacing: -0.01em;
}

.turn-process-count {
  color: hsl(var(--muted-foreground) / 0.56);
  border: 1px solid hsl(var(--border) / 0.08);
  background: hsl(var(--muted) / 0.16);
  border-radius: 9999px;
  padding: 0.14rem 0.42rem;
  font-size: 0.55rem;
  line-height: 0.8rem;
}

.turn-process-status {
  display: inline-flex;
  max-width: 8.8rem;
  align-items: center;
  gap: 0.32rem;
  border: 1px solid transparent;
  border-radius: 9999px;
  padding: 0.18rem 0.44rem;
  font-size: 0.54rem;
  font-weight: 600;
  line-height: 0.8rem;
}

.turn-process-status-running {
  color: hsl(var(--primary) / 0.82);
  border-color: hsl(var(--primary) / 0.16);
  background: hsl(var(--primary) / 0.08);
}

.turn-process-status-completed {
  color: rgb(4 120 87 / 0.92);
  border-color: rgb(16 185 129 / 0.16);
  background: rgb(16 185 129 / 0.08);
}

.turn-process-status-interrupted {
  color: rgb(180 83 9 / 0.88);
  border-color: rgb(245 158 11 / 0.18);
  background: rgb(245 158 11 / 0.1);
}

.turn-process-status-skipped {
  color: hsl(var(--muted-foreground) / 0.62);
  border-color: hsl(var(--border) / 0.12);
  background: hsl(var(--muted) / 0.14);
}

.turn-process-status-error {
  color: rgb(220 38 38 / 0.88);
  border-color: rgb(239 68 68 / 0.16);
  background: rgb(239 68 68 / 0.08);
}

.turn-process-track {
  border-color: hsl(var(--border) / 0.14);
}

.turn-process-status-icon {
  flex-shrink: 0;
}

.turn-process-status-spin {
  animation: turn-process-status-spin 1.1s linear infinite;
}

.turn-process-chevron {
  color: hsl(var(--muted-foreground) / 0.46);
}

.turn-stage-card {
  padding: 0.52rem 0.68rem 0.5rem;
  border-color: hsl(var(--border) / 0.08);
  background:
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.82) 0%,
      hsl(var(--background) / 0.68) 100%
    );
}

.turn-stage-status {
  border: 1px solid transparent;
}

.stage-status-running {
  color: hsl(var(--primary) / 0.82);
  border-color: hsl(var(--primary) / 0.16);
  background: hsl(var(--primary) / 0.08);
}

.stage-status-completed {
  color: rgb(4 120 87 / 0.92);
  border-color: rgb(16 185 129 / 0.16);
  background: rgb(16 185 129 / 0.08);
}

.stage-status-interrupted {
  color: rgb(180 83 9 / 0.88);
  border-color: rgb(245 158 11 / 0.18);
  background: rgb(245 158 11 / 0.1);
}

.stage-status-skipped {
  color: hsl(var(--muted-foreground) / 0.6);
  border-color: hsl(var(--border) / 0.12);
  background: hsl(var(--muted) / 0.16);
}

.stage-status-error {
  color: rgb(220 38 38 / 0.88);
  border-color: rgb(239 68 68 / 0.16);
  background: rgb(239 68 68 / 0.08);
}

.turn-stage-detail-surface {
  border-color: hsl(var(--border) / 0.1);
  background: hsl(var(--background) / 0.82);
  box-shadow: inset 0 1px 0 hsl(var(--background) / 0.55);
}

.turn-stage-inline-markdown {
  min-width: 0;
  color: hsl(var(--foreground) / 0.7);
  font-size: 0.8rem;
  line-height: 1.3rem;
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

@keyframes turn-process-status-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
