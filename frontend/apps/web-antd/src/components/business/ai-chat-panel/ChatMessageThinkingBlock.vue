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
    embedded?: boolean;
    index: number;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
    embedded: false,
  },
);

/** Thinking block: expanded during streaming, collapsed by default when done. User can toggle. */
const THINKING_AUTO_COLLAPSE_DELAY_MS = 180;
const THINKING_PREVIEW_MAX_LENGTH = 120;
const thinkingExpandedMap = ref<Record<number, boolean>>({});
const thinkingAutoCollapseMap = ref<Record<number, boolean>>({});
const thinkingAutoCollapseTimers = new Map<
  number,
  ReturnType<typeof setTimeout>
>();

function getThinkingPreview(content: string | undefined) {
  if (!content) {
    return undefined;
  }

  const firstMeaningfulLine = content
    .split(/\n+/)
    .map((line) => line.trim())
    .find((line) => line.length > 0);

  if (!firstMeaningfulLine) {
    return undefined;
  }

  const normalized = firstMeaningfulLine
    .replace(/\[(.*?)\]\((.*?)\)/g, '$1')
    .replace(/`{1,3}([^`]+)`{1,3}/g, '$1')
    .replace(/[*_>#~-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!normalized) {
    return undefined;
  }

  if (normalized.length <= THINKING_PREVIEW_MAX_LENGTH) {
    return normalized;
  }

  return `${normalized.slice(0, THINKING_PREVIEW_MAX_LENGTH - 1).trimEnd()}…`;
}

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
const thinkingPreview = computed(() =>
  getThinkingPreview(thinkingContent.value),
);
const toolCallsForDisplay = computed(() => getToolCallsForDisplay(props.msg));

function isThinkingExpanded(idx: number) {
  if (props.embedded) {
    return Boolean(thinkingContent.value);
  }
  return Boolean(
    (props.msg.streaming && thinkingContent.value) ||
    thinkingAutoCollapseMap.value[idx] ||
    thinkingExpandedMap.value[idx],
  );
}

function toggleThinkingExpand(idx: number) {
  if (props.embedded) {
    return;
  }
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
    class="thinking-skeleton rounded-[14px] border border-border/14 bg-background/62"
    :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'"
  >
    <div class="flex items-center gap-2">
      <div
        class="thinking-glow relative flex size-5 items-center justify-center rounded-full bg-primary/10"
      >
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
      <span class="text-[10px] font-medium text-muted-foreground">{{
        $t('common.globalAiChat.processing')
      }}</span>
    </div>
    <div class="mt-2 space-y-2">
      <div class="skeleton-line h-2 w-[82%] rounded-full bg-muted/50"></div>
      <div
        class="skeleton-line h-2 w-[64%] rounded-full bg-muted/50"
        style="animation-delay: 0.15s"
      ></div>
    </div>
  </div>

  <!-- Thinking content (streamed separately from final answer). Less prominent; auto-collapse when done; expandable. -->
  <div
    v-if="thinkingContent"
    class="relative"
    :class="compact ? 'mb-1.5' : 'mb-2'"
  >
    <div
      v-if="embedded"
      data-testid="thinking-embedded-body"
      class="thinking-inline-body rounded-[13px] border border-border/12 bg-background/74"
      :class="compact ? 'px-2.5 py-2' : 'px-3 py-2.5'"
    >
      <div class="thinking-markdown text-[10px] leading-[1.45rem] text-foreground/68">
        <MarkdownRender
          :content="thinkingContent"
          :streaming="!!msg.streaming && !msg.content"
        />
      </div>
    </div>
    <button
      v-else
      :aria-expanded="isThinkingExpanded(index)"
      data-testid="thinking-toggle"
      type="button"
      class="thinking-chip group flex max-w-full cursor-pointer items-start gap-2.5 rounded-[16px] border text-left transition-all duration-200"
      :class="
        compact
          ? 'px-2.5 py-1.5 hover:bg-background/78'
          : 'px-3 py-2 hover:bg-background/78'
      "
      :title="!isThinkingExpanded(index) ? thinkingPreview : undefined"
      @click="toggleThinkingExpand(index)"
    >
      <span
        class="thinking-chip-icon relative flex shrink-0 items-center justify-center rounded-full bg-muted/55 ring-1 ring-border/10"
        :class="compact ? 'size-[1.3rem]' : 'size-[1.45rem]'"
      >
        <IconifyIcon
          icon="lucide:brain"
          class="size-3 text-muted-foreground/68"
          :class="msg.streaming ? 'thinking-glow text-primary/70' : ''"
        />
      </span>

      <span
        class="flex min-w-0 flex-1 flex-col"
        :class="compact ? 'gap-0.5' : 'gap-1'"
      >
        <span class="flex min-w-0 items-center gap-1.5">
          <span class="truncate text-[9.5px] font-semibold text-foreground/78">
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

        <span
          v-if="thinkingPreview && !isThinkingExpanded(index)"
          data-testid="thinking-preview"
          class="pr-1 text-[9.5px] leading-[1.05rem] text-muted-foreground/64"
          :class="compact ? 'line-clamp-2' : 'line-clamp-3'"
        >
          {{ thinkingPreview }}
        </span>
      </span>

      <span
        class="ml-auto flex shrink-0 items-center pt-0.5 text-muted-foreground/50"
      >
        <IconifyIcon
          icon="lucide:chevron-down"
          class="size-3.5 transition-transform duration-200"
          :class="isThinkingExpanded(index) ? 'rotate-180 text-primary/80' : ''"
        />
      </span>
    </button>
    <div
      v-if="!embedded"
      data-testid="thinking-body"
      class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
      :style="{
        gridTemplateRows: isThinkingExpanded(index) ? '1fr' : '0fr',
        opacity: isThinkingExpanded(index) ? 1 : 0,
      }"
    >
      <div class="min-h-0 overflow-hidden">
        <div
          class="thinking-sheet-card mt-1.5 rounded-[13px] border border-border/12 transition-transform duration-200"
          :class="
            compact ? 'ml-1.5 px-3 py-2' : 'ml-2 px-3.5 py-2.5'
          "
          :style="{
            transform: isThinkingExpanded(index)
              ? 'translateY(0)'
              : 'translateY(-4px)',
          }"
        >
          <div class="thinking-markdown text-[10px] leading-[1.45rem] text-foreground/68">
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

<style scoped>
.thinking-chip {
  border-color: hsl(var(--border) / 0.12);
  background:
    linear-gradient(
      180deg,
      hsl(var(--background) / 0.82) 0%,
      hsl(var(--muted) / 0.12) 100%
    );
  box-shadow:
    0 14px 26px -34px hsl(var(--foreground) / 0.14),
    0 1px 0 hsl(var(--background) / 0.7) inset;
}

.thinking-sheet-card {
  background: linear-gradient(
    180deg,
    hsl(var(--background) / 0.92),
    hsl(var(--muted) / 0.08)
  );
  box-shadow: 0 14px 28px -36px hsl(var(--foreground) / 0.12);
}

.thinking-inline-body {
  min-width: 0;
  position: relative;
  box-shadow: 0 12px 22px -34px hsl(var(--foreground) / 0.1);
}

.thinking-inline-body::before {
  position: absolute;
  top: 0.65rem;
  bottom: 0.65rem;
  left: 0.65rem;
  width: 2px;
  content: '';
  background: linear-gradient(
    180deg,
    hsl(var(--primary) / 20%),
    hsl(var(--border) / 0%)
  );
  border-radius: 999px;
}

.thinking-markdown :deep(p:first-child) {
  margin-top: 0;
}

.thinking-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.thinking-markdown :deep(ul),
.thinking-markdown :deep(ol) {
  margin: 0.65rem 0 0;
  padding-inline-start: 1.1rem;
}

.thinking-markdown :deep(li + li) {
  margin-top: 0.25rem;
}
</style>
