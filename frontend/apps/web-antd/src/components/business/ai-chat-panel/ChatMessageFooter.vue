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
    class="flex items-center text-muted-foreground/70 transition-opacity duration-200 group-hover:opacity-100"
    :class="[
      compact ? 'mt-0.5 gap-0.5 text-[11px]' : 'mt-1 gap-1 text-xs',
      compact ? 'opacity-100' : 'opacity-60 hover:opacity-100',
    ]"
  >
    <span
      v-if="msg.created_at"
      class="mr-0.5 text-[10px] tabular-nums text-muted-foreground/40"
    >
      {{ formatTimeOnly(msg.created_at) }}
    </span>
    <span v-if="msg.tokenUsage" class="mr-0.5 tabular-nums"
      >{{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}</span
    >
    <span v-if="msg.durationMs" class="mr-0.5 tabular-nums"
      >· {{ formatDurationSeconds(msg.durationMs) }}</span
    >
    <Tooltip
      v-if="msg.memoryUpdated"
      :title="$t('common.globalAiChat.memoryUpdated')"
    >
      <span
        class="mr-0.5 inline-flex items-center gap-0.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
      >
        <IconifyIcon icon="lucide:brain" class="size-2.5" />
      </span>
    </Tooltip>
    <span class="mx-0.5 text-border">·</span>
    <Tooltip :title="$t('common.globalAiChat.copy')">
      <button
        class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
        :class="compact ? 'size-5' : 'size-5'"
        @click="emit('copy', msg.content)"
      >
        <IconifyIcon
          icon="lucide:copy"
          :class="compact ? 'size-2.5' : 'size-3'"
        />
      </button>
    </Tooltip>
    <Tooltip :title="$t('common.globalAiChat.regenerate')">
      <button
        class="flex items-center justify-center rounded-md transition-colors hover:bg-muted hover:text-foreground"
        :class="compact ? 'size-5' : 'size-5'"
        @click="emit('regenerate', props.index)"
      >
        <IconifyIcon
          icon="lucide:refresh-cw"
          :class="compact ? 'size-2.5' : 'size-3'"
        />
      </button>
    </Tooltip>
  </div>
</template>
