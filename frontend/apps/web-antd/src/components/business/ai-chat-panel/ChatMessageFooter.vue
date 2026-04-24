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
    class="assistant-message-footer text-muted-foreground/56 flex flex-wrap items-center gap-2"
    :class="[compact ? 'text-[9px]' : 'text-[9.5px]']"
  >
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 gap-y-1">
      <span
        v-if="msg.created_at"
        class="assistant-footer-chip rounded-full px-1.5 py-0.5 text-[9px] tabular-nums"
      >
        {{ formatTimeOnly(msg.created_at) }}
      </span>
      <span
        v-if="!compact && (msg.tokenUsage || msg.durationMs)"
        class="assistant-footer-chip text-foreground/44 rounded-full px-1.5 py-0.5 text-[9px] tabular-nums"
      >
        <template v-if="msg.tokenUsage">
          {{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}
        </template>
        <span
          v-if="msg.tokenUsage && msg.durationMs"
          class="text-foreground/38 px-0.5"
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
          class="assistant-footer-memory inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] text-primary"
        >
          <IconifyIcon icon="lucide:brain" class="size-3" />
          <span>{{ $t('common.globalAiChat.memoryUpdated') }}</span>
        </span>
      </Tooltip>
    </div>
    <div
      class="assistant-footer-actions ml-auto flex shrink-0 items-center gap-1"
    >
      <Tooltip :title="$t('common.globalAiChat.copy')">
        <button
          type="button"
          class="assistant-footer-action flex size-5 items-center justify-center rounded-full"
          @click="emit('copy', msg.content)"
        >
          <IconifyIcon icon="lucide:copy" class="size-2.5" />
        </button>
      </Tooltip>
      <Tooltip :title="$t('common.globalAiChat.regenerate')">
        <button
          type="button"
          class="assistant-footer-action flex size-5 items-center justify-center rounded-full"
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
  color: hsl(var(--muted-foreground) / 0.62);
}

.assistant-footer-memory {
  color: hsl(var(--primary) / 0.78);
}

.assistant-footer-actions {
  opacity: 0.84;
}

.assistant-footer-action {
  color: hsl(var(--muted-foreground) / 0.5);
  transition:
    color 140ms ease,
    background-color 140ms ease,
    border-color 140ms ease;
}

.assistant-footer-action:hover {
  color: hsl(var(--foreground) / 0.82);
  background: hsl(var(--muted) / 0.4);
}
</style>
