<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed, onUnmounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

import {
  getThinkingContentForDisplay,
  getToolCallsForDisplay,
} from './chat-message-turn-flow';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    index: number;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

/** Thinking block: expanded during streaming, collapsed by default when done. User can toggle. */
const THINKING_AUTO_COLLAPSE_DELAY_MS = 180;
const thinkingExpandedMap = ref<Record<number, boolean>>({});
const thinkingAutoCollapseMap = ref<Record<number, boolean>>({});
const thinkingAutoCollapseTimers = new Map<
  number,
  ReturnType<typeof setTimeout>
>();

function setThinkingAutoCollapse(idx: number, active: boolean) {
  const next = { ...thinkingAutoCollapseMap.value };
  if (active) {
    next[idx] = true;
  } else {
    delete next[idx];
  }
  thinkingAutoCollapseMap.value = next;
}

function clearThinkingAutoCollapse(idx: number) {
  const timer = thinkingAutoCollapseTimers.get(idx);
  if (timer) {
    clearTimeout(timer);
    thinkingAutoCollapseTimers.delete(idx);
  }
  setThinkingAutoCollapse(idx, false);
}

function scheduleThinkingAutoCollapse(idx: number) {
  clearThinkingAutoCollapse(idx);
  setThinkingAutoCollapse(idx, true);
  thinkingAutoCollapseTimers.set(
    idx,
    setTimeout(() => {
      thinkingAutoCollapseTimers.delete(idx);
      setThinkingAutoCollapse(idx, false);
      thinkingExpandedMap.value = {
        ...thinkingExpandedMap.value,
        [idx]: false,
      };
    }, THINKING_AUTO_COLLAPSE_DELAY_MS),
  );
}

function clearAllThinkingAutoCollapseTimers() {
  for (const timer of thinkingAutoCollapseTimers.values()) {
    clearTimeout(timer);
  }
  thinkingAutoCollapseTimers.clear();
  thinkingAutoCollapseMap.value = {};
}

const thinkingContent = computed(() => getThinkingContentForDisplay(props.msg));
const toolCallsForDisplay = computed(() => getToolCallsForDisplay(props.msg));

function isThinkingExpanded(idx: number) {
  return Boolean(
    (props.msg.streaming && thinkingContent.value) ||
    thinkingAutoCollapseMap.value[idx] ||
    thinkingExpandedMap.value[idx],
  );
}

function toggleThinkingExpand(idx: number) {
  const nextExpanded = !isThinkingExpanded(idx);
  clearThinkingAutoCollapse(idx);
  thinkingExpandedMap.value = {
    ...thinkingExpandedMap.value,
    [idx]: nextExpanded,
  };
}

/** Auto-collapse thinking block when streaming ends. */
watch(
  () => [props.msg.streaming, props.index] as const,
  ([streaming, idx], oldVal) => {
    const prevStreaming = oldVal?.[0];
    if (
      prevStreaming === true &&
      streaming === false &&
      typeof idx === 'number'
    ) {
      scheduleThinkingAutoCollapse(idx);
      return;
    }
    if (streaming === true && typeof idx === 'number') {
      clearThinkingAutoCollapse(idx);
    }
  },
);

onUnmounted(clearAllThinkingAutoCollapseTimers);
</script>

<template>
  <!-- Thinking (no tool calls yet) - skeleton pulse -->
  <div
    v-if="
      msg.streaming &&
      !msg.content &&
      !toolCallsForDisplay?.length &&
      !thinkingContent
    "
    class="thinking-skeleton space-y-2 rounded-xl border border-border/20 bg-accent/30 px-3 py-3"
  >
    <div class="flex items-center gap-2">
      <div
        class="thinking-glow relative flex size-5 items-center justify-center rounded-full bg-primary/10"
      >
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
      <span class="text-xs font-medium text-muted-foreground">{{
        $t('common.globalAiChat.processing')
      }}</span>
    </div>
    <div class="space-y-2">
      <div class="skeleton-line h-2 w-[90%] rounded-full bg-muted/50"></div>
      <div
        class="skeleton-line h-2 w-[72%] rounded-full bg-muted/50"
        style="animation-delay: 0.15s"
      ></div>
      <div
        class="skeleton-line h-2 w-[55%] rounded-full bg-muted/50"
        style="animation-delay: 0.3s"
      ></div>
    </div>
  </div>

  <!-- Thinking content (streamed separately from final answer). Less prominent; auto-collapse when done; expandable. -->
  <div
    v-if="thinkingContent"
    class="relative"
    :class="compact ? 'mb-1.5' : 'mb-2'"
  >
    <button
      :aria-expanded="isThinkingExpanded(index)"
      data-testid="thinking-toggle"
      type="button"
      class="thinking-chip hover:border-primary/18 flex max-w-full cursor-pointer items-center gap-2 border-0 bg-transparent text-left transition-all duration-200 hover:text-foreground"
      :class="compact ? 'px-2.5 py-1.5' : 'px-3 py-1.5'"
      @click="toggleThinkingExpand(index)"
    >
      <span
        class="thinking-chip-icon relative flex shrink-0 items-center justify-center rounded-full"
        :class="compact ? 'size-6' : 'size-7'"
      >
        <IconifyIcon
          icon="lucide:brain"
          class="size-3.5 text-muted-foreground/80"
          :class="msg.streaming ? 'thinking-glow text-primary/70' : ''"
        />
      </span>

      <span class="flex min-w-0 flex-1 items-center gap-1.5">
        <span class="text-foreground/84 truncate text-xs font-medium">
          {{
            msg.streaming
              ? $t('common.globalAiChat.thinking')
              : $t('common.globalAiChat.thinkingCollapsed')
          }}
        </span>

        <span
          v-if="msg.streaming"
          class="typing-dots thinking-status-dots shrink-0"
          ><span></span><span></span><span></span
        ></span>
        <span
          v-else
          aria-hidden="true"
          class="size-1.5 shrink-0 rounded-full bg-primary/35"
        >
        </span>
      </span>

      <span class="ml-auto flex shrink-0 items-center text-muted-foreground/60">
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-3.5 transition-transform duration-200"
          :class="isThinkingExpanded(index) ? 'rotate-180 text-primary/80' : ''"
        />
      </span>
    </button>
    <div
      data-testid="thinking-body"
      class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
      :style="{
        gridTemplateRows: isThinkingExpanded(index) ? '1fr' : '0fr',
        opacity: isThinkingExpanded(index) ? 1 : 0,
      }"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="thinking-sheet-card mt-2 transition-transform duration-200"
          :class="compact ? 'ml-1.5 px-3 py-2.5' : 'ml-2 px-3.5 py-3'"
          :style="{
            transform: isThinkingExpanded(index)
              ? 'translateY(0)'
              : 'translateY(-6px)',
          }"
        >
          <div
            class="thinking-markdown leading-5.5 text-muted-foreground/82 text-xs"
          >
            <MarkdownRender
              :content="thinkingContent"
              :streaming="!!msg.streaming && !msg.content"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
