<script lang="ts" setup>
import type { PendingPageOpForDisplay } from './pending-page-op';
import type { ToolDisplayItem } from './tool-call-utils';
import type { ChatMessage } from './types';

import { IconifyIcon } from '@vben/icons';

import {
  formatDurationSeconds,
  formatToolStatusLabel,
} from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';

import ToolCallDetails from './ToolCallDetails.vue';
import ToolCallPendingOpCard from './ToolCallPendingOpCard.vue';
import { getPageOpErrorHintKey } from './pageOpErrorHints';
import { useChatMessageToolCalls } from './use-chat-message-tool-calls';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    embedded?: boolean;
    index: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    embedded: false,
    pendingOps: () => [],
  },
);

const emit = defineEmits<{
  copy: [content: string];
}>();

const aiPanelStore = useAIPanelStore();
const DEFAULT_VISIBLE_TARGET_BADGES = Number.POSITIVE_INFINITY;
const EMBEDDED_VISIBLE_TARGET_BADGES = 1;

const {
  getToolDisplayState,
  hasPendingOpArgs,
  isPendingOpExpanded,
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
} = useChatMessageToolCalls(props);

function isToolGroupOpen() {
  return props.embedded || isToolGroupExpanded(props.index);
}

function normalizeInlineText(value: null | string | undefined): string {
  return typeof value === 'string' ? value.trim() : '';
}

function getEmbeddedToolStatusLabel(toolItem: ToolDisplayItem): string {
  return formatToolStatusLabel(
    toolItem.tc.status,
    getToolDisplayState(toolItem.tc) === 'waiting_confirm',
  );
}

function getEmbeddedToolSummary(toolItem: ToolDisplayItem): string {
  const error = normalizeInlineText(toolItem.tc.error);
  if (error) {
    return error;
  }

  const headline = normalizeInlineText(toolItem.headlineSummary);
  if (headline) {
    return headline;
  }

  const explanation = normalizeInlineText(
    toolItem.structuredOutput.explanation,
  );
  if (explanation) {
    return explanation;
  }

  const searchFailure = normalizeInlineText(
    toolItem.searchSummary?.failureReason,
  );
  if (searchFailure) {
    return searchFailure;
  }

  if (typeof toolItem.searchSummary?.resultCount === 'number') {
    return `${$t('common.globalAiChat.toolSearchResults')}: ${toolItem.searchSummary.resultCount}`;
  }

  if (toolItem.searchSummary && toolItem.searchSummary.items.length > 0) {
    return `${$t('common.globalAiChat.toolSearchResults')}: ${toolItem.searchSummary.items.length}`;
  }

  return '';
}

function getToolCardSummary(toolItem: ToolDisplayItem): string {
  return getEmbeddedToolSummary(toolItem);
}

function getVisibleTargetBadges(toolItem: ToolDisplayItem) {
  const limit = props.embedded
    ? EMBEDDED_VISIBLE_TARGET_BADGES
    : DEFAULT_VISIBLE_TARGET_BADGES;
  return toolItem.targetBadges.slice(0, limit);
}

function getHiddenTargetBadgeCount(toolItem: ToolDisplayItem): number {
  return Math.max(
    toolItem.targetBadges.length - getVisibleTargetBadges(toolItem).length,
    0,
  );
}

function getEmbeddedToolHint(toolItem: ToolDisplayItem): string {
  if (toolItem.tc.status !== 'error') {
    return '';
  }
  return $t(getPageOpErrorHintKey(toolItem.tc.errorType));
}
</script>

<template>
  <!-- Generating indicator (tool calls running but no content yet) -->
  <div
    v-if="
      !embedded &&
      msg.streaming &&
      !msg.content &&
      toolCallsForDisplay.length > 0
    "
    class="text-muted-foreground/72 flex items-center gap-1.5 px-1.5 py-0.5"
    :class="compact ? 'text-[10px]' : 'text-[10.5px]'"
  >
    <span class="typing-dots"><span></span><span></span><span></span></span>
    <span>{{ $t('common.globalAiChat.generating') }}</span>
  </div>

  <!-- Tool calls - collapsible group card -->
  <div
    v-if="toolCallsForDisplay.length > 0"
    class="relative"
    :class="compact ? 'mt-1' : 'mt-1.5'"
  >
    <button
      v-if="!embedded"
      type="button"
      class="tool-group-toggle group flex w-full cursor-pointer select-none items-center rounded-[14px] border text-left transition-colors"
      :class="
        compact
          ? 'gap-1.5 px-2.5 py-[7px] text-[10px]'
          : 'gap-2 px-3 py-[9px] text-[10.5px]'
      "
      data-testid="tool-group-toggle"
      @click="toggleToolGroupExpand(index)"
    >
      <span
        class="tool-group-icon flex shrink-0 items-center justify-center rounded-2xl"
        :class="compact ? 'size-5' : 'size-5.5'"
      >
        <IconifyIcon
          icon="lucide:wrench"
          class="shrink-0 text-muted-foreground/60"
          :class="[
            compact ? 'size-2.5' : 'size-3',
            toolGroupSummary?.running ? 'tc-pill-pulse' : '',
          ]"
        />
      </span>
      <span class="text-muted-foreground/74 flex-1 font-medium">
        <template v-if="toolGroupSummary?.running">
          {{
            $t('common.globalAiChat.toolGroupRunning', {
              count: toolGroupSummary.total,
            })
          }}
        </template>
        <template v-else>
          {{
            $t('common.globalAiChat.toolGroupSummary', {
              count: toolGroupSummary?.total ?? 0,
            })
          }}
        </template>
      </span>
      <span
        v-if="toolGroupSummary && !toolGroupSummary.running"
        class="flex items-center gap-1 font-mono text-[9px] tracking-[0.06em]"
      >
        <span
          v-if="toolGroupSummary.success"
          class="tool-group-count flex items-center gap-0.5 rounded-full px-1.5 py-px text-green-600 dark:text-green-400"
        >
          <IconifyIcon icon="lucide:check" class="size-2.5" />
          {{ toolGroupSummary.success }}
        </span>
        <span
          v-if="toolGroupSummary.error"
          class="tool-group-count flex items-center gap-0.5 rounded-full px-1.5 py-px text-red-500"
        >
          <IconifyIcon icon="lucide:x" class="size-2.5" />
          {{ toolGroupSummary.error }}
        </span>
      </span>
      <IconifyIcon
        icon="lucide:chevron-down"
        class="shrink-0 text-muted-foreground/35 transition-transform duration-300 group-hover:text-muted-foreground/55"
        style="transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1)"
        :class="compact ? 'size-2.5' : 'size-3'"
        :style="{
          transform: isToolGroupOpen() ? 'rotate(180deg)' : 'rotate(0deg)',
        }"
      />
    </button>

    <div
      class="grid"
      :style="{
        gridTemplateRows: isToolGroupOpen() ? '1fr' : '0fr',
        opacity: isToolGroupOpen() ? 1 : 0,
        transition:
          'grid-template-rows 350ms cubic-bezier(0.4,0,0.2,1), opacity 200ms ease',
      }"
      data-testid="tool-group-body"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="border-border/28"
          :class="
            embedded
              ? 'mt-0 border-l-0 pl-0'
              : compact
                ? 'ml-1.5 mt-1 border-l pl-2.5'
                : 'ml-2 mt-1 border-l pl-3'
          "
        >
          <div
            class="tc-timeline relative"
            :class="
              embedded
                ? compact
                  ? 'py-0.5 pl-4'
                  : 'py-0.5 pl-5'
                : compact
                  ? 'py-0.5 pl-4'
                  : 'py-1 pl-5'
            "
            :data-testid="embedded ? 'tool-group-embedded' : undefined"
          >
            <!-- Timeline vertical line -->
            <div
              v-if="toolCallsForDisplay.length > 1"
              class="absolute w-px bg-border/25"
              :class="
                compact
                  ? 'bottom-1 left-[7px] top-1'
                  : 'bottom-1.5 left-[8px] top-1.5'
              "
            ></div>

            <div
              v-for="toolItem in toolDisplayItems"
              :key="toolItem.index"
              class="relative"
              :class="toolItem.index > 0 ? (compact ? 'mt-0.5' : 'mt-1') : ''"
            >
              <!-- Timeline dot -->
              <div
                class="absolute z-[1]"
                :class="compact ? '-left-3 top-[5px]' : '-left-4 top-[7px]'"
              >
                <span
                  v-if="toolItem.tc.status === 'running'"
                  class="tc-dot-pulse block rounded-full bg-primary"
                  :class="compact ? 'size-[7px]' : 'size-2'"
                ></span>
                <span
                  v-else-if="toolItem.tc.status === 'success'"
                  class="block rounded-full bg-green-500"
                  :class="compact ? 'size-[7px]' : 'size-2'"
                ></span>
                <span
                  v-else
                  class="block rounded-full bg-red-500"
                  :class="compact ? 'size-[7px]' : 'size-2'"
                ></span>
              </div>

              <!-- Tool call card -->
              <div
                :data-testid="
                  embedded ? `tool-call-embedded-${toolItem.index}` : undefined
                "
                :class="
                  embedded
                    ? 'tool-call-inline'
                    : 'tool-call-card group/tc overflow-hidden rounded-[14px] border transition-colors'
                "
              >
                <template v-if="embedded">
                  <button
                    type="button"
                    class="flex w-full items-start gap-2 rounded-[14px] bg-transparent text-left transition-colors hover:bg-muted/[0.05]"
                    :class="compact ? 'px-2.5 py-[7px]' : 'px-3 py-[9px]'"
                    :data-testid="`tool-call-toggle-${toolItem.index}`"
                    :title="
                      toolItem.hasDetails
                        ? $t(
                            toolItem.expanded
                              ? 'common.globalAiChat.toolDetailsCollapse'
                              : 'common.globalAiChat.toolDetailsExpand',
                          )
                        : undefined
                    "
                    @click="
                      toolItem.hasDetails
                        ? toggleToolExpand(toolItem.tc, toolItem.index)
                        : undefined
                    "
                  >
                    <span
                      class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px font-mono text-[9px] font-medium leading-tight tracking-[0.08em]"
                      :class="
                        toolItem.tc.status === 'running'
                          ? getToolDisplayState(toolItem.tc) ===
                            'waiting_confirm'
                            ? 'tc-pill-pulse bg-warning/10 text-warning'
                            : 'tc-pill-pulse bg-primary/10 text-primary'
                          : toolItem.tc.status === 'success'
                            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                            : 'bg-red-500/10 text-red-500'
                      "
                    >
                      <IconifyIcon
                        v-if="toolItem.tc.status !== 'running'"
                        :icon="
                          toolItem.tc.status === 'success'
                            ? 'lucide:check'
                            : 'lucide:x'
                        "
                        class="size-2.5"
                      />
                      <span
                        v-else
                        class="tc-dot-pulse mr-0.5 inline-block size-1.5 rounded-full bg-current"
                      ></span>
                      {{ getEmbeddedToolStatusLabel(toolItem) }}
                    </span>

                    <div class="min-w-0 flex-1">
                      <div class="flex min-w-0 flex-wrap items-start gap-1.5">
                        <span
                          class="min-w-0 flex-1 text-[10.5px] text-muted-foreground/68"
                        >
                          <span class="block truncate">
                            <template v-if="toolItem.tc.skillName">
                              <span class="text-foreground/52 font-mono">{{
                                toolItem.tc.skillName
                              }}</span>
                              <span class="mx-0.5 text-muted-foreground/30"
                                >›</span
                              >
                            </template>
                            <span class="text-foreground/82 font-medium">{{
                              toolItem.tc.displayName || toolItem.tc.name
                            }}</span>
                          </span>
                        </span>
                        <span
                          v-if="toolItem.tc.durationMs"
                          class="text-muted-foreground/42 font-mono text-[9px] tabular-nums"
                        >
                          {{ formatDurationSeconds(toolItem.tc.durationMs) }}
                        </span>
                      </div>
                      <p
                        v-if="getToolCardSummary(toolItem)"
                        class="mt-1 whitespace-pre-wrap break-words text-[9.5px] leading-[1.1rem] text-muted-foreground/68"
                      >
                        {{ getToolCardSummary(toolItem) }}
                      </p>
                      <span
                        v-if="toolItem.targetBadges.length > 0"
                        class="mt-1 flex flex-wrap items-center gap-1"
                        :class="compact ? 'text-[9px]' : 'text-[10px]'"
                      >
                        <span class="text-muted-foreground/45">
                          {{ $t('common.globalAiChat.toolTouched') }}
                        </span>
                        <span
                          v-for="badge in getVisibleTargetBadges(toolItem)"
                          :key="`${badge.labelKey}-${badge.value}`"
                          class="border-border/14 inline-flex max-w-full items-center gap-1 rounded-md border bg-background/55 px-1.5 py-px"
                        >
                          <span class="shrink-0 text-muted-foreground/55">{{
                            $t(badge.labelKey)
                          }}</span>
                          <span class="text-foreground/72 truncate">{{
                            badge.value
                          }}</span>
                        </span>
                        <span
                          v-if="getHiddenTargetBadgeCount(toolItem) > 0"
                          class="text-muted-foreground/48 inline-flex items-center rounded-md bg-background/40 px-1 py-px"
                        >
                          +{{ getHiddenTargetBadgeCount(toolItem) }}
                        </span>
                      </span>
                      <p
                        v-if="getEmbeddedToolHint(toolItem)"
                        class="text-muted-foreground/62 mt-1 text-[10px]"
                      >
                        {{ getEmbeddedToolHint(toolItem) }}
                      </p>
                      <a
                        v-if="
                          toolItem.tc.resultLink &&
                          toolItem.tc.status === 'success'
                        "
                        :href="toolItem.tc.resultLink"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="mt-1 inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
                      >
                        <IconifyIcon
                          icon="lucide:external-link"
                          class="size-2.5"
                        />
                        {{ $t('common.globalAiChat.viewResult') }}
                      </a>
                    </div>

                    <span
                      v-if="toolItem.hasDetails"
                      class="text-muted-foreground/48 ml-auto inline-flex shrink-0 items-center gap-1 pt-0.5 text-[9.5px]"
                    >
                      <span>{{
                        $t(
                          toolItem.expanded
                            ? 'common.globalAiChat.toolDetailsCollapse'
                            : 'common.globalAiChat.toolDetailsExpand',
                        )
                      }}</span>
                      <IconifyIcon
                        icon="lucide:chevron-down"
                        class="size-3 transition-transform duration-200"
                        :style="{
                          transform: toolItem.expanded
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                        }"
                      />
                    </span>
                  </button>

                  <div
                    v-if="toolItem.hasDetails"
                    class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                    :style="{
                      gridTemplateRows: toolItem.expanded ? '1fr' : '0fr',
                      opacity: toolItem.expanded ? 1 : 0,
                    }"
                    :data-testid="`tool-call-details-${toolItem.index}`"
                  >
                    <div class="min-h-0 overflow-hidden pl-2 pt-1">
                      <div class="border-border/18 border-l">
                        <ToolCallDetails
                          :compact="compact"
                          :raw-expanded="isToolRawExpanded(toolItem.index)"
                          :tool-item="toolItem"
                          @copy="emit('copy', $event)"
                          @toggle-raw="toggleToolRawExpand(toolItem.index)"
                        />
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <button
                    type="button"
                    class="flex w-full select-none items-center text-left"
                    :class="[
                      compact
                        ? 'gap-1.5 px-2.5 py-[7px] text-[10px]'
                        : 'gap-2 px-3 py-[9px] text-[10.5px]',
                      toolItem.hasDetails ? 'cursor-pointer' : 'cursor-default',
                    ]"
                    :data-testid="`tool-call-toggle-${toolItem.index}`"
                    :title="
                      toolItem.hasDetails
                        ? $t(
                            toolItem.expanded
                              ? 'common.globalAiChat.toolDetailsCollapse'
                              : 'common.globalAiChat.toolDetailsExpand',
                          )
                        : undefined
                    "
                    @click="toggleToolExpand(toolItem.tc, toolItem.index)"
                  >
                    <span
                      class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px font-mono text-[9px] font-medium leading-tight tracking-[0.08em]"
                      :class="
                        toolItem.tc.status === 'running'
                          ? getToolDisplayState(toolItem.tc) ===
                            'waiting_confirm'
                            ? 'tc-pill-pulse bg-warning/10 text-warning'
                            : 'tc-pill-pulse bg-primary/10 text-primary'
                          : toolItem.tc.status === 'success'
                            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                            : 'bg-red-500/10 text-red-500'
                      "
                    >
                      <IconifyIcon
                        v-if="toolItem.tc.status !== 'running'"
                        :icon="
                          toolItem.tc.status === 'success'
                            ? 'lucide:check'
                            : 'lucide:x'
                        "
                        class="size-2.5"
                      />
                      <span
                        v-else
                        class="tc-dot-pulse mr-0.5 inline-block size-1.5 rounded-full bg-current"
                      ></span>
                      {{
                        toolItem.tc.status === 'running'
                          ? getToolDisplayState(toolItem.tc) ===
                            'waiting_confirm'
                            ? $t('common.globalAiChat.toolWaitingConfirm')
                            : $t('common.globalAiChat.toolExecuting')
                          : toolItem.tc.status === 'success'
                            ? $t('common.globalAiChat.toolStatusOk')
                            : $t('common.globalAiChat.toolStatusErr')
                      }}
                    </span>

                    <div
                      class="min-w-0 flex-1 text-[10.5px] text-muted-foreground/68"
                    >
                      <span class="block truncate">
                        <template v-if="toolItem.tc.skillName">
                          <span class="text-foreground/52 font-mono">{{
                            toolItem.tc.skillName
                          }}</span>
                          <span class="mx-0.5 text-muted-foreground/30">›</span>
                        </template>
                        <span class="text-foreground/78 font-medium">{{
                          toolItem.tc.displayName || toolItem.tc.name
                        }}</span>
                      </span>
                      <p
                        v-if="getToolCardSummary(toolItem)"
                        class="mt-0.5 line-clamp-2 break-words text-[9.5px] leading-[1.05rem] text-muted-foreground/62"
                      >
                        {{ getToolCardSummary(toolItem) }}
                      </p>
                      <span
                        v-if="toolItem.targetBadges.length > 0"
                        class="mt-1 flex flex-wrap items-center gap-1"
                        :class="compact ? 'text-[9px]' : 'text-[10px]'"
                      >
                        <span class="text-muted-foreground/45">
                          {{ $t('common.globalAiChat.toolTouched') }}
                        </span>
                        <span
                          v-for="badge in getVisibleTargetBadges(toolItem)"
                          :key="`${badge.labelKey}-${badge.value}`"
                          class="border-border/16 inline-flex max-w-full items-center gap-1 rounded-md border bg-background/60 px-1.5 py-px"
                        >
                          <span class="shrink-0 text-muted-foreground/55">{{
                            $t(badge.labelKey)
                          }}</span>
                          <span class="truncate text-foreground/75">{{
                            badge.value
                          }}</span>
                        </span>
                        <span
                          v-if="getHiddenTargetBadgeCount(toolItem) > 0"
                          class="text-muted-foreground/48 inline-flex items-center rounded-md bg-background/40 px-1 py-px"
                        >
                          +{{ getHiddenTargetBadgeCount(toolItem) }}
                        </span>
                      </span>
                    </div>

                    <span
                      v-if="toolItem.tc.durationMs"
                      class="font-mono text-[9px] tabular-nums text-muted-foreground/45"
                    >
                      {{ formatDurationSeconds(toolItem.tc.durationMs) }}
                    </span>

                    <IconifyIcon
                      v-if="toolItem.hasDetails"
                      icon="lucide:chevron-down"
                      class="shrink-0 text-muted-foreground/30 transition-transform duration-200"
                      :class="compact ? 'size-2.5' : 'size-3'"
                      :style="{
                        transform: toolItem.expanded
                          ? 'rotate(180deg)'
                          : 'rotate(0deg)',
                      }"
                    />
                  </button>

                  <div
                    v-if="toolItem.hasDetails"
                    class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                    :style="{
                      gridTemplateRows: toolItem.expanded ? '1fr' : '0fr',
                      opacity: toolItem.expanded ? 1 : 0,
                    }"
                    :data-testid="`tool-call-details-${toolItem.index}`"
                  >
                    <div class="min-h-0 overflow-hidden px-1 pb-1 pt-1">
                      <div class="rounded-[12px] bg-background/78">
                        <ToolCallDetails
                          :compact="compact"
                          :raw-expanded="isToolRawExpanded(toolItem.index)"
                          :tool-item="toolItem"
                          @copy="emit('copy', $event)"
                          @toggle-raw="toggleToolRawExpand(toolItem.index)"
                        />
                      </div>
                    </div>
                  </div>
                </template>
              </div>

              <!-- Inline confirmation card (for this tool call) / 内联确认卡片（对应本工具调用） -->
              <ToolCallPendingOpCard
                v-for="op in (pendingOps || []).filter(
                  (o) => o.toolCallId === toolItem.tc.id,
                )"
                :key="op.invokeId"
                :compact="compact"
                :countdown-now="countdownNow"
                :expanded="isPendingOpExpanded(op.invokeId)"
                :has-args="hasPendingOpArgs(op.params)"
                :now="now"
                :op="op"
                @resolve="
                  (allowed) => aiPanelStore.resolvePageOp(op.invokeId, allowed)
                "
                @toggle-args="togglePendingOpExpand(op.invokeId)"
              />

              <!-- Still running hint (8s+) - outside details so always visible / 执行超 8s 的提示 -->
              <p
                v-if="
                  toolItem.tc.status === 'running' &&
                  toolItem.tc.startedAt &&
                  now - toolItem.tc.startedAt >= 8000
                "
                class="mt-0.5 text-[10px] text-muted-foreground/70"
                :class="embedded ? '' : 'pl-2'"
              >
                {{ $t('common.globalAiChat.toolStillRunningHint') }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-group-toggle {
  border-color: hsl(var(--border) / 0.1);
  background:
    radial-gradient(
      circle at 100% 0%,
      hsl(var(--primary) / 0.04),
      transparent 38%
    ),
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.82) 0%,
      hsl(var(--background) / 0.72) 100%
    );
  backdrop-filter: blur(10px);
  box-shadow:
    0 10px 22px -30px hsl(var(--foreground) / 0.14),
    0 1px 0 hsl(var(--background) / 0.72) inset;
}

.tool-group-toggle:hover {
  border-color: hsl(var(--primary) / 0.16);
}

.tool-group-icon {
  border: 1px solid hsl(var(--primary) / 0.1);
  background: hsl(var(--primary) / 0.07);
}

.tool-group-count {
  border: 1px solid hsl(var(--border) / 0.1);
  background: hsl(var(--background) / 0.76);
}

.tool-call-card {
  background:
    radial-gradient(
      circle at top left,
      hsl(var(--primary) / 0.025),
      transparent 32%
    ),
    hsl(var(--background) / 0.66);
  border-color: hsl(var(--border) / 0.1);
  box-shadow: 0 10px 22px -32px hsl(var(--foreground) / 0.12);
}

.tool-call-inline {
  border-bottom: 1px solid hsl(var(--border) / 0.08);
}

.tool-call-inline:last-child {
  border-bottom: none;
}
</style>
