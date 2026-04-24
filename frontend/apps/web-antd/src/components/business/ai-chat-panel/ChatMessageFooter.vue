<script lang="ts" setup>
import type { ChatMessage } from './types';

import { IconifyIcon } from '@vben/icons';

import { Tooltip } from 'ant-design-vue';

import { formatDurationSeconds } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';
import { formatTimeOnly } from '#/utils/common';

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

const emit = defineEmits<{
  copy: [content: string];
  regenerate: [index: number];
}>();
</script>

<template>
  <!-- Stats + Copy + Regenerate -->
  <div
    v-if="msg.content && !msg.streaming"
    data-testid="assistant-message-footer"
    class="assistant-message-footer text-muted-foreground/52 flex flex-wrap items-center justify-between gap-1.5"
    :class="[compact ? 'text-[7.5px]' : 'text-[8px]']"
  >
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 gap-y-1">
      <span
        v-if="msg.created_at"
        class="assistant-footer-chip rounded-full px-1.5 py-px text-[6.5px] tabular-nums"
      >
        {{ formatTimeOnly(msg.created_at) }}
      </span>
      <span
        v-if="!compact && (msg.tokenUsage || msg.durationMs)"
        class="assistant-footer-chip rounded-full px-1.5 py-px text-[6.5px] text-foreground/48 tabular-nums"
      >
        <template v-if="msg.tokenUsage">
          {{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}
        </template>
        <span
          v-if="msg.tokenUsage && msg.durationMs"
          class="px-0.5 text-foreground/38"
        >
          ·
        </span>
        <template v-if="msg.durationMs">
          {{ formatDurationSeconds(msg.durationMs) }}
        </template>
      </span>
      <Tooltip
        v-if="msg.memoryUpdated && !compact"
        :title="$t('common.globalAiChat.memoryUpdated')"
      >
        <span
          class="assistant-footer-memory inline-flex items-center gap-0.5 rounded-full px-1.5 py-px text-[6.5px] text-primary"
        >
          <IconifyIcon icon="lucide:brain" class="size-[7px]" />
          <span>{{ $t('common.globalAiChat.memoryUpdated') }}</span>
        </span>
      </Tooltip>
    </div>
    <div class="ml-auto flex shrink-0 items-center gap-0.5">
      <Tooltip :title="$t('common.globalAiChat.copy')">
        <button
          class="assistant-footer-action flex size-[13px] items-center justify-center rounded-full"
          @click="emit('copy', msg.content)"
        >
          <IconifyIcon icon="lucide:copy" class="size-2.5" />
        </button>
      </Tooltip>
      <Tooltip :title="$t('common.globalAiChat.regenerate')">
        <button
          class="assistant-footer-action flex size-[13px] items-center justify-center rounded-full"
          @click="emit('regenerate', props.index)"
        >
          <IconifyIcon icon="lucide:refresh-cw" class="size-2.5" />
        </button>
      </Tooltip>
    </div>
  </div>
</template>

<style scoped>
.assistant-footer-chip {
  border: 1px solid hsl(var(--border) / 0.26);
  background: hsl(var(--background) / 0.86);
}

.assistant-footer-memory {
  border: 1px solid hsl(var(--primary) / 0.2);
  background: hsl(var(--primary) / 0.08);
}

.assistant-footer-action {
  color: hsl(var(--muted-foreground) / 0.48);
  border: 1px solid transparent;
  background: transparent;
  transition:
    color 140ms ease,
    background-color 140ms ease,
    border-color 140ms ease;
}

.assistant-footer-action:hover {
  color: hsl(var(--foreground) / 0.82);
  border-color: hsl(var(--border) / 0.2);
  background: hsl(var(--muted) / 0.36);
}
</style>
