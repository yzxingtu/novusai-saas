<script lang="ts" setup>
import type { TurnFlowState } from './TurnFlowState';

import type { TurnFlowStageForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';
import type { PendingPageOpForDisplay } from '#/components/business/ai-chat-panel/pending-page-op';
import type { ChatMessage } from '#/types/ai-chat';

import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import ChatMessageRagSources from '#/components/business/ai-chat-panel/ChatMessageRagSources.vue';
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

const AUTO_COLLAPSE_DELAY_MS = 220;
const timeline = computed(() => props.state.timeline);
const isLiveMessage = computed(() => props.msg.streaming === true);
const hasLegacyFallbackSections = computed(
  () =>
    timeline.value.length === 0 &&
    Boolean(
      props.msg.thinkingContent ||
      props.msg.optimizingTools ||
      props.msg.toolCalls?.length ||
      props.msg.ragSources?.length,
    ),
);
const expandedStageKeys = ref<Record<string, boolean>>({});
const stageStatusSnapshot = ref<Record<string, string>>({});
const collapseTimers = new Map<string, ReturnType<typeof setTimeout>>();

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

function getStageTypeLabel(stage: TurnFlowStageForDisplay) {
  if (stage.title) {
    return stage.title;
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
  if (stage.summary) {
    return stage.summary;
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
    if (props.state.flow.failureKind) {
      return props.state.flow.failureKind;
    }
    if (props.state.flow.completionReason) {
      return props.state.flow.completionReason;
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

  return `${getStageTypeLabel(stage)} · ${getStageStatusLabel(stage)}`;
}

function getStageIcon(stage: TurnFlowStageForDisplay) {
  if (stage.status === 'error') {
    return 'lucide:circle-alert';
  }
  if (stage.status === 'interrupted') {
    return 'lucide:pause-circle';
  }
  if (stage.status === 'completed') {
    return 'lucide:check-circle-2';
  }
  if (stage.status === 'skipped') {
    return 'lucide:minus-circle';
  }
  if (stage.type === 'thinking') {
    return 'lucide:brain';
  }
  if (stage.type === 'tool_selection') {
    return 'lucide:sparkles';
  }
  if (stage.type === 'tool_execution') {
    return 'lucide:wrench';
  }
  if (stage.type === 'retrieval') {
    return 'lucide:book-open';
  }
  if (stage.type === 'answer_assembly') {
    return 'lucide:file-text';
  }
  if (stage.type === 'completed') {
    return 'lucide:badge-check';
  }
  return 'lucide:circle-x';
}

function getStageStatusClass(stage: TurnFlowStageForDisplay) {
  if (stage.status === 'running') {
    return 'bg-primary/10 text-primary';
  }
  if (stage.status === 'completed') {
    return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400';
  }
  if (stage.status === 'skipped') {
    return 'bg-slate-500/10 text-slate-600 dark:text-slate-300';
  }
  if (stage.status === 'interrupted') {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-300';
  }
  return 'bg-red-500/10 text-red-500';
}

function getStageDetailLines(stage: TurnFlowStageForDisplay): string[] {
  const lines = (stage.detailLines ?? [])
    .map((line) => normalizeOptionalString(line))
    .filter((line): line is string => line !== undefined);
  if (lines.length > 0) {
    return lines;
  }
  const fallbackLine = getStageSummary(stage);
  return fallbackLine ? [fallbackLine] : [];
}

function hasExplicitStageDetailLines(stage: TurnFlowStageForDisplay) {
  return (stage.detailLines ?? []).some(
    (line) => normalizeOptionalString(line) !== undefined,
  );
}

function getCollapsedDetailLines(lines: string[], expanded: boolean) {
  if (expanded || lines.length <= 4) {
    return lines;
  }
  const first = lines[0];
  const second = lines[1];
  const secondLast = lines.at(-2);
  const last = lines.at(-1);
  if (!first || !second || !secondLast || !last) {
    return lines;
  }
  return [first, second, '…', secondLast, last];
}

function hasToolSelectionFallbackContent(stage: TurnFlowStageForDisplay) {
  return stage.type === 'tool_selection' && Boolean(props.msg.optimizingTools);
}

function hasToolExecutionFallbackContent(stage: TurnFlowStageForDisplay) {
  return (
    stage.type === 'tool_execution' && Boolean(props.msg.toolCalls?.length)
  );
}

function hasRetrievalFallbackContent(stage: TurnFlowStageForDisplay) {
  return stage.type === 'retrieval' && Boolean(props.msg.ragSources?.length);
}

function hasLegacyThinkingContent(stage: TurnFlowStageForDisplay) {
  return stage.type === 'thinking' && Boolean(props.msg.thinkingContent);
}

function isStageExpandable(stage: TurnFlowStageForDisplay) {
  return (
    hasExplicitStageDetailLines(stage) ||
    hasLegacyThinkingContent(stage) ||
    hasToolSelectionFallbackContent(stage) ||
    hasToolExecutionFallbackContent(stage) ||
    hasRetrievalFallbackContent(stage)
  );
}

function isStageExpanded(stage: TurnFlowStageForDisplay, index: number) {
  return Boolean(expandedStageKeys.value[getStageKey(stage, index)]);
}

function clearCollapseTimer(stageKey: string) {
  const timer = collapseTimers.get(stageKey);
  if (timer) {
    clearTimeout(timer);
    collapseTimers.delete(stageKey);
  }
}

function clearAllCollapseTimers() {
  for (const timer of collapseTimers.values()) {
    clearTimeout(timer);
  }
  collapseTimers.clear();
}

function scheduleAutoCollapse(stageKey: string) {
  clearCollapseTimer(stageKey);
  collapseTimers.set(
    stageKey,
    setTimeout(() => {
      collapseTimers.delete(stageKey);
      expandedStageKeys.value = {
        ...expandedStageKeys.value,
        [stageKey]: false,
      };
    }, AUTO_COLLAPSE_DELAY_MS),
  );
}

function toggleStage(stage: TurnFlowStageForDisplay, index: number) {
  if (!isStageExpandable(stage)) {
    return;
  }
  const stageKey = getStageKey(stage, index);
  clearCollapseTimer(stageKey);
  expandedStageKeys.value = {
    ...expandedStageKeys.value,
    [stageKey]: !expandedStageKeys.value[stageKey],
  };
}

function shouldAutoCollapseAfterRun(
  previousStatus: string | undefined,
  stage: TurnFlowStageForDisplay,
) {
  if (!isStageExpandable(stage)) {
    return false;
  }
  if (previousStatus !== 'running' || stage.status === 'running') {
    return false;
  }
  if (stage.type === 'answer_assembly') {
    return true;
  }
  if (stage.status === 'error' || stage.status === 'interrupted') {
    return true;
  }
  if (
    stage.type === 'thinking' ||
    stage.type === 'tool_execution' ||
    stage.type === 'retrieval' ||
    stage.status === 'skipped'
  ) {
    return true;
  }
  return !isLiveMessage.value;
}

function scheduleCollapseForSettledStages() {
  for (const [index, stage] of timeline.value.entries()) {
    if (!isStageExpandable(stage) || stage.status === 'running') {
      continue;
    }
    scheduleAutoCollapse(getStageKey(stage, index));
  }
}

watch(
  () => ({
    identity: messageIdentity.value,
    stageKeys: timeline.value.map((stage, index) => getStageKey(stage, index)),
  }),
  (snapshot, previousSnapshot) => {
    const activeStageKeys = new Set(snapshot.stageKeys);
    for (const stageKey of collapseTimers.keys()) {
      if (!activeStageKeys.has(stageKey)) {
        clearCollapseTimer(stageKey);
      }
    }

    const nextExpanded: Record<string, boolean> = {};
    for (const [index, stage] of timeline.value.entries()) {
      const stageKey = snapshot.stageKeys[index]!;
      nextExpanded[stageKey] =
        expandedStageKeys.value[stageKey] ??
        Boolean(isLiveMessage.value && stage.status === 'running');
    }
    expandedStageKeys.value = nextExpanded;
    const sameIdentity =
      snapshot.identity === previousSnapshot?.identity &&
      snapshot.stageKeys.length === (previousSnapshot?.stageKeys.length ?? 0) &&
      snapshot.stageKeys.every(
        (stageKey, index) => stageKey === previousSnapshot?.stageKeys[index],
      );
    if (!sameIdentity) {
      clearAllCollapseTimers();
      stageStatusSnapshot.value = {};
    }
  },
  { deep: true, immediate: true },
);

watch(
  () =>
    timeline.value.map((stage, index) => ({
      key: getStageKey(stage, index),
      status: stage.status,
      stage,
    })),
  (nextStages) => {
    const nextStatusMap: Record<string, string> = {};
    for (const item of nextStages) {
      const previousStatus = stageStatusSnapshot.value[item.key];
      nextStatusMap[item.key] = item.status;

      if (item.status === 'running' && isLiveMessage.value) {
        clearCollapseTimer(item.key);
        expandedStageKeys.value = {
          ...expandedStageKeys.value,
          [item.key]: true,
        };
        continue;
      }

      if (shouldAutoCollapseAfterRun(previousStatus, item.stage)) {
        scheduleAutoCollapse(item.key);
      }
    }
    stageStatusSnapshot.value = nextStatusMap;
  },
  { deep: true, immediate: true },
);

watch(
  () => props.msg.streaming === true,
  (isStreaming, wasStreaming) => {
    if (!isStreaming && wasStreaming) {
      scheduleCollapseForSettledStages();
    }
  },
);

onBeforeUnmount(() => {
  clearAllCollapseTimers();
});
</script>

<template>
  <div
    v-if="timeline.length > 0"
    data-testid="chat-message-kernel-timeline"
    class="overflow-hidden rounded-xl border border-border/25 bg-accent/10"
    :class="compact ? 'mb-1.5' : 'mb-2'"
  >
    <div
      class="flex items-center gap-1.5 border-b border-border/20 text-muted-foreground/80"
      :class="compact ? 'px-2.5 py-1.5 text-[11px]' : 'px-3 py-2 text-xs'"
    >
      <IconifyIcon
        icon="lucide:workflow"
        :class="compact ? 'size-3' : 'size-3.5'"
      />
      <span class="font-medium">{{
        $t('common.globalAiChat.turnTimeline')
      }}</span>
    </div>

    <div class="space-y-1" :class="compact ? 'px-2 py-1.5' : 'px-2.5 py-2'">
      <div
        v-for="(stage, stageIndex) in timeline"
        :key="getStageKey(stage, stageIndex)"
        class="overflow-hidden rounded-lg border border-border/20 bg-background/70"
        :data-testid="`turn-stage-${stageIndex}`"
      >
        <button
          type="button"
          class="flex w-full items-center gap-2 text-left transition-colors"
          :class="[
            compact ? 'px-2 py-1.5 text-[11px]' : 'px-2.5 py-2 text-xs',
            isStageExpandable(stage) ? 'hover:bg-accent/20' : 'cursor-default',
          ]"
          :disabled="!isStageExpandable(stage)"
          :data-testid="`turn-stage-toggle-${stageIndex}`"
          @click="toggleStage(stage, stageIndex)"
        >
          <IconifyIcon
            :icon="getStageIcon(stage)"
            class="shrink-0 text-muted-foreground/70"
            :class="[
              compact ? 'size-3.5' : 'size-4',
              stage.status === 'running' ? 'tc-pill-pulse text-primary' : '',
            ]"
          />
          <div class="min-w-0 flex-1">
            <div class="flex min-w-0 items-center gap-1.5">
              <span class="truncate font-medium text-foreground/90">
                {{ getStageTypeLabel(stage) }}
              </span>
              <span
                class="inline-flex shrink-0 items-center rounded-full px-1.5 py-[1px] text-[10px] font-medium"
                :class="getStageStatusClass(stage)"
              >
                {{ getStageStatusLabel(stage) }}
              </span>
            </div>
            <p
              class="truncate text-muted-foreground/75"
              :class="compact ? 'mt-0.5 text-[10px]' : 'mt-0.5 text-[11px]'"
            >
              {{ getStageSummary(stage) }}
            </p>
          </div>
          <IconifyIcon
            v-if="isStageExpandable(stage)"
            icon="lucide:chevron-down"
            class="shrink-0 text-muted-foreground/50 transition-transform duration-200"
            :class="compact ? 'size-3' : 'size-3.5'"
            :data-testid="`turn-stage-chevron-${stageIndex}`"
            :style="{
              transform: isStageExpanded(stage, stageIndex)
                ? 'rotate(180deg)'
                : 'rotate(0deg)',
            }"
          />
        </button>

        <div
          class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
          :data-testid="`turn-stage-body-${stageIndex}`"
          :style="{
            gridTemplateRows: isStageExpanded(stage, stageIndex)
              ? '1fr'
              : '0fr',
            opacity: isStageExpanded(stage, stageIndex) ? 1 : 0.8,
          }"
        >
          <div class="min-h-0 overflow-hidden border-t border-border/20">
            <div :class="compact ? 'p-2 text-[11px]' : 'p-2.5 text-xs'">
              <ul
                v-if="getStageDetailLines(stage).length > 0"
                class="space-y-1 text-muted-foreground"
                :class="compact ? 'mb-1.5' : 'mb-2'"
              >
                <li
                  v-for="line in getCollapsedDetailLines(
                    getStageDetailLines(stage),
                    isStageExpanded(stage, stageIndex),
                  )"
                  :key="line"
                  class="leading-relaxed"
                >
                  {{ line }}
                </li>
              </ul>

              <ChatMessageThinkingBlock
                v-if="hasLegacyThinkingContent(stage)"
                :compact="compact"
                :index="0"
                :msg="msg"
              />

              <div
                v-if="hasToolSelectionFallbackContent(stage)"
                class="flex items-center rounded-lg bg-accent/60 text-muted-foreground"
                :class="
                  compact
                    ? 'gap-1.5 px-2 py-1 text-[11px]'
                    : 'gap-2 px-2.5 py-1.5 text-xs'
                "
              >
                <IconifyIcon
                  icon="lucide:sparkles"
                  class="text-primary"
                  :class="compact ? 'size-3' : 'size-3.5'"
                />
                <span>{{
                  $t('common.globalAiChat.optimizingTools', {
                    total: msg.optimizingTools?.total ?? 0,
                    selected: msg.optimizingTools?.selected ?? 0,
                  })
                }}</span>
              </div>

              <ChatMessageToolCalls
                v-if="hasToolExecutionFallbackContent(stage)"
                :compact="compact"
                :countdown-now="countdownNow"
                :index="0"
                :msg="msg"
                :pending-ops="pendingOps"
                @copy="(content) => emit('copy', content)"
              />

              <ChatMessageRagSources
                v-if="hasRetrievalFallbackContent(stage)"
                :compact="compact"
                :msg="msg"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div
    v-else-if="hasLegacyFallbackSections"
    data-testid="chat-message-kernel-fallback"
    class="space-y-2"
    :class="compact ? 'mb-1.5' : 'mb-2'"
  >
    <ChatMessageThinkingBlock
      v-if="msg.thinkingContent"
      :compact="compact"
      :index="0"
      :msg="msg"
    />

    <div
      v-if="msg.optimizingTools"
      class="flex items-center rounded-lg border border-border/20 bg-accent/10 text-muted-foreground"
      :class="
        compact
          ? 'gap-1.5 px-2 py-1 text-[11px]'
          : 'gap-2 px-2.5 py-1.5 text-xs'
      "
    >
      <IconifyIcon
        icon="lucide:sparkles"
        class="text-primary"
        :class="compact ? 'size-3' : 'size-3.5'"
      />
      <span>{{
        $t('common.globalAiChat.optimizingTools', {
          total: msg.optimizingTools.total ?? 0,
          selected: msg.optimizingTools.selected ?? 0,
        })
      }}</span>
    </div>

    <ChatMessageToolCalls
      v-if="msg.toolCalls?.length"
      :compact="compact"
      :countdown-now="countdownNow"
      :index="0"
      :msg="msg"
      :pending-ops="pendingOps"
      @copy="(content) => emit('copy', content)"
    />

    <ChatMessageRagSources
      v-if="msg.ragSources?.length"
      :compact="compact"
      :msg="msg"
    />
  </div>
</template>
