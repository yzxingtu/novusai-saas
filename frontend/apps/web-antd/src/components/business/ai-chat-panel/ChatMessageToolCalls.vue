<script lang="ts" setup>
import type { PendingPageOpForDisplay } from './pending-page-op';
import type { ChatMessage } from './types';

import { IconifyIcon } from '@vben/icons';

import { formatDurationSeconds } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { useAIPanelStore } from '#/store';

import ToolCallDetails from './ToolCallDetails.vue';
import ToolCallPendingOpCard from './ToolCallPendingOpCard.vue';
import { useChatMessageToolCalls } from './use-chat-message-tool-calls';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    countdownNow?: number;
    index: number;
    msg: ChatMessage;
    pendingOps?: PendingPageOpForDisplay[];
  }>(),
  {
    compact: false,
    countdownNow: undefined,
    pendingOps: () => [],
  },
);

const emit = defineEmits<{
  copy: [content: string];
}>();

const aiPanelStore = useAIPanelStore();

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
  toolDisplayItems,
  toolGroupSummary,
} = useChatMessageToolCalls(props);
</script>

<template>
  <!-- Generating indicator (tool calls running but no content yet) -->
  <div
    v-if="msg.streaming && !msg.content && msg.toolCalls?.length"
    class="flex items-center gap-1.5 px-2 py-0.5 text-muted-foreground"
    :class="compact ? 'text-[11px]' : 'text-xs'"
  >
    <span class="typing-dots"><span></span><span></span><span></span></span>
    <span>{{ $t('common.globalAiChat.generating') }}</span>
  </div>

  <!-- Tool calls - collapsible group card -->
  <div
    v-if="msg.toolCalls?.length"
    class="overflow-hidden rounded-lg border border-border/25 bg-accent/10"
    :class="compact ? 'mt-1' : 'mt-1.5'"
  >
    <button
      type="button"
      class="flex w-full cursor-pointer select-none items-center text-left transition-colors hover:bg-accent/20"
      :class="
        compact
          ? 'gap-1 px-2 py-1 text-[11px]'
          : 'gap-1.5 px-2.5 py-1.5 text-xs'
      "
      data-testid="tool-group-toggle"
      @click="toggleToolGroupExpand(index)"
    >
      <IconifyIcon
        icon="lucide:wrench"
        class="shrink-0 text-muted-foreground/60"
        :class="[
          compact ? 'size-3' : 'size-3.5',
          toolGroupSummary?.running ? 'tc-pill-pulse' : '',
        ]"
      />
      <span class="flex-1 font-medium text-muted-foreground">
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
        class="flex items-center gap-1.5 text-[10px]"
      >
        <span
          v-if="toolGroupSummary.success"
          class="flex items-center gap-0.5 text-green-600 dark:text-green-400"
        >
          <IconifyIcon icon="lucide:check" class="size-2.5" />
          {{ toolGroupSummary.success }}
        </span>
        <span
          v-if="toolGroupSummary.error"
          class="flex items-center gap-0.5 text-red-500"
        >
          <IconifyIcon icon="lucide:x" class="size-2.5" />
          {{ toolGroupSummary.error }}
        </span>
      </span>
      <IconifyIcon
        icon="lucide:chevron-down"
        class="shrink-0 text-muted-foreground/30 transition-transform duration-300"
        style="transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1)"
        :class="compact ? 'size-2.5' : 'size-3'"
        :style="{
          transform: isToolGroupExpanded(index)
            ? 'rotate(180deg)'
            : 'rotate(0deg)',
        }"
      />
    </button>

    <div
      class="grid"
      :style="{
        gridTemplateRows: isToolGroupExpanded(index) ? '1fr' : '0fr',
        opacity: isToolGroupExpanded(index) ? 1 : 0,
        transition:
          'grid-template-rows 350ms cubic-bezier(0.4,0,0.2,1), opacity 200ms ease',
      }"
      data-testid="tool-group-body"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="border-t border-border/20 transition-opacity duration-200"
          :style="{ opacity: isToolGroupExpanded(index) ? 1 : 0 }"
        ></div>
        <div
          class="tc-timeline relative"
          :class="compact ? 'px-2 py-1 pl-5' : 'px-2.5 py-1.5 pl-6'"
        >
          <!-- Timeline vertical line -->
          <div
            v-if="msg.toolCalls.length > 1"
            class="absolute w-px bg-border/40"
            :class="
              compact
                ? 'bottom-1 left-[8px] top-1'
                : 'bottom-1.5 left-[9px] top-1.5'
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
              class="group/tc overflow-hidden rounded-lg border border-border/20 bg-accent/15 backdrop-blur-sm transition-colors hover:bg-accent/25"
            >
              <button
                type="button"
                class="flex w-full select-none items-center text-left"
                :class="[
                  compact
                    ? 'gap-1 px-2 py-[3px] text-[11px]'
                    : 'gap-1.5 px-2.5 py-1 text-xs',
                  toolItem.hasDetails ? 'cursor-pointer' : 'cursor-default',
                ]"
                :data-testid="`tool-call-toggle-${toolItem.index}`"
                @click="toggleToolExpand(toolItem.tc, toolItem.index)"
              >
                <!-- Status pill -->
                <span
                  class="inline-flex shrink-0 items-center gap-0.5 rounded-full px-1.5 py-px text-[10px] font-medium leading-tight"
                  :class="
                    toolItem.tc.status === 'running'
                      ? getToolDisplayState(toolItem.tc) === 'waiting_confirm'
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
                      ? getToolDisplayState(toolItem.tc) === 'waiting_confirm'
                        ? $t('common.globalAiChat.toolWaitingConfirm')
                        : $t('common.globalAiChat.toolExecuting')
                      : toolItem.tc.status === 'success'
                        ? $t('common.globalAiChat.toolStatusOk')
                        : $t('common.globalAiChat.toolStatusErr')
                  }}
                </span>

                <!-- Tool name -->
                <span class="min-w-0 flex-1 text-muted-foreground">
                  <span class="block truncate">
                    <template v-if="toolItem.tc.skillName">
                      <span class="font-medium text-foreground/60">{{
                        toolItem.tc.skillName
                      }}</span>
                      <span class="mx-0.5 text-muted-foreground/30">›</span>
                    </template>
                    <span class="text-foreground/70">{{
                      toolItem.tc.displayName || toolItem.tc.name
                    }}</span>
                    <span
                      v-if="
                        toolItem.headlineSummary &&
                        toolItem.tc.status === 'success'
                      "
                      class="ml-1 text-muted-foreground/50"
                      >— {{ toolItem.headlineSummary }}</span
                    >
                  </span>
                  <span
                    v-if="toolItem.targetBadges.length > 0"
                    class="mt-1 flex flex-wrap items-center gap-1"
                    :class="compact ? 'text-[9px]' : 'text-[10px]'"
                  >
                    <span class="text-muted-foreground/45">
                      {{ $t('common.globalAiChat.toolTouched') }}
                    </span>
                    <span
                      v-for="badge in toolItem.targetBadges"
                      :key="`${badge.labelKey}-${badge.value}`"
                      class="inline-flex max-w-full items-center gap-1 rounded-full border border-border/30 bg-background/70 px-1.5 py-px"
                    >
                      <span class="shrink-0 text-muted-foreground/55">{{
                        $t(badge.labelKey)
                      }}</span>
                      <span class="truncate text-foreground/75">{{
                        badge.value
                      }}</span>
                    </span>
                  </span>
                </span>

                <!-- Duration -->
                <span
                  v-if="toolItem.tc.durationMs"
                  class="text-[10px] tabular-nums text-muted-foreground/40"
                >
                  {{ formatDurationSeconds(toolItem.tc.durationMs) }}
                </span>

                <!-- Expand chevron -->
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

              <!-- Expanded details -->
              <div
                v-if="toolItem.hasDetails"
                class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
                :style="{
                  gridTemplateRows: toolItem.expanded ? '1fr' : '0fr',
                  opacity: toolItem.expanded ? 1 : 0,
                }"
                :data-testid="`tool-call-details-${toolItem.index}`"
              >
                <div class="min-h-0 overflow-hidden border-t border-border/20">
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
              class="mt-0.5 pl-1 text-[10px] text-muted-foreground"
            >
              {{ $t('common.globalAiChat.toolStillRunningHint') }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
