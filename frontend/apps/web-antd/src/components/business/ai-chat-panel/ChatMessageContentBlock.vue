<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

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

/** Long message fold: keep very long replies readable without feeling truncated / 长消息折叠阈值 */
const COLLAPSE_THRESHOLD = 1600;
const canCollapse = computed(
  () =>
    !!props.msg.content &&
    !props.msg.streaming &&
    props.msg.content.length > COLLAPSE_THRESHOLD,
);

function normalizeDiagnosticText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

const diagnosticTerminationReason = computed(() => {
  return (
    normalizeDiagnosticText(props.msg.terminationReason) ||
    normalizeDiagnosticText(props.msg.completionReason)
  );
});

const isTruncatedByLength = computed(() => {
  return (
    !props.msg.streaming && diagnosticTerminationReason.value.toLowerCase() === 'length'
  );
});

const expandedMap = ref<Record<number, boolean>>({});
function toggleExpand(idx: number) {
  expandedMap.value = { ...expandedMap.value, [idx]: !expandedMap.value[idx] };
}
</script>

<template>
  <div
    v-if="msg.content"
    class="overflow-hidden rounded-2xl border border-border/30 bg-gradient-to-br from-muted/40 to-muted/20 shadow-sm"
    :class="compact ? 'px-2.5 py-1.5 text-sm' : 'px-4 py-3'"
  >
    <div
      class="transition-[max-height] duration-200"
      :class="[
        canCollapse && !expandedMap[index]
          ? 'relative max-h-[300px] overflow-hidden'
          : '',
      ]"
    >
      <MarkdownRender :content="msg.content" :streaming="!!msg.streaming" />
      <span v-if="msg.streaming" class="streaming-cursor"></span>
      <span v-if="msg.stoppedByUser && !msg.streaming" class="ml-1 text-muted-foreground/70">
        {{ $t('common.globalAiChat.generationStopped') }}
      </span>
      <span v-else-if="msg.interrupted && !msg.streaming" class="ml-1 text-muted-foreground/70">
        {{ $t('common.globalAiChat.generationInterrupted') }}
      </span>
      <span v-else-if="msg.partial && !msg.streaming" class="ml-1 text-muted-foreground/70">
        {{ $t('common.globalAiChat.generationIncomplete') }}
      </span>
      <div
        v-if="canCollapse && !expandedMap[index]"
        class="pointer-events-none absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-muted/90 to-transparent"
      ></div>
    </div>
    <button
      v-if="canCollapse && !msg.streaming"
      type="button"
      class="mt-1 flex w-full items-center justify-center gap-1 rounded py-1 text-xs text-primary transition-colors hover:underline"
      @click="toggleExpand(index)"
    >
      {{
        expandedMap[index]
          ? $t('common.globalAiChat.collapseMessage')
          : $t('common.globalAiChat.expandMore')
      }}
    </button>
    <p
      v-if="canCollapse && !expandedMap[index] && !msg.streaming"
      data-testid="collapsed-message-hint"
      class="mt-1 text-center text-[11px] text-muted-foreground/75"
    >
      {{ $t('common.globalAiChat.collapsedMessageHint') }}
    </p>
    <div
      v-if="isTruncatedByLength"
      data-testid="truncation-warning"
      class="mt-2 flex items-center gap-1.5 rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-700 dark:text-amber-300"
    >
      <IconifyIcon icon="lucide:triangle-alert" class="size-3.5 shrink-0" />
      <span>{{ $t('common.globalAiChat.responseTruncated') }}</span>
    </div>
  </div>
</template>
