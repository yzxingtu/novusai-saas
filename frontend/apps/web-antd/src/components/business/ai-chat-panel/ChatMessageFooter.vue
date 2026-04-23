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
    class="assistant-message-footer text-muted-foreground/70 flex flex-wrap items-center justify-between gap-2"
    :class="[compact ? 'text-[10px]' : 'text-[11px]']"
  >
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1">
      <span
        v-if="msg.created_at"
        class="text-muted-foreground/44 rounded-full border border-border/18 bg-background/74 px-1.5 py-px text-[9px] tabular-nums"
      >
        {{ formatTimeOnly(msg.created_at) }}
      </span>
      <span
        v-if="!compact && msg.tokenUsage"
        class="text-foreground/64 rounded-full border border-border/18 bg-background/74 px-1.5 py-px text-[9px] tabular-nums"
      >
        {{ msg.tokenUsage }} {{ $t('common.globalAiChat.tokens') }}
      </span>
      <span
        v-if="!compact && msg.durationMs"
        class="text-foreground/60 rounded-full border border-border/18 bg-background/74 px-1.5 py-px text-[9px] tabular-nums"
      >
        {{ formatDurationSeconds(msg.durationMs) }}
      </span>
      <Tooltip
        v-if="msg.memoryUpdated && !compact"
        :title="$t('common.globalAiChat.memoryUpdated')"
      >
        <span
          class="border-primary/14 inline-flex items-center gap-0.5 rounded-full border bg-primary/[0.07] px-1.5 py-px text-[9px] text-primary"
        >
          <IconifyIcon icon="lucide:brain" class="size-2.5" />
        </span>
      </Tooltip>
    </div>
    <div class="ml-auto flex shrink-0 items-center gap-1">
      <Tooltip :title="$t('common.globalAiChat.copy')">
        <button
          class="hover:bg-background/88 flex size-[18px] items-center justify-center rounded-md border border-transparent text-muted-foreground/56 transition-colors hover:border-border/28 hover:text-foreground"
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
          class="hover:bg-background/88 flex size-[18px] items-center justify-center rounded-md border border-transparent text-muted-foreground/56 transition-colors hover:border-border/28 hover:text-foreground"
          @click="emit('regenerate', props.index)"
        >
          <IconifyIcon
            icon="lucide:refresh-cw"
            :class="compact ? 'size-2.5' : 'size-3'"
          />
        </button>
      </Tooltip>
    </div>
  </div>
</template>
