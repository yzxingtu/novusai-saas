<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';
import { isDevErrorMode } from '#/utils/request';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

const showDebugError = computed(
  () => isDevErrorMode() && !!props.msg.error?.debugMessage,
);
</script>

<template>
  <!-- Structured error panel -->
  <div
    v-if="msg.error"
    class="rounded-xl border border-destructive/40 bg-destructive/5"
    :class="compact ? 'mb-1 px-2.5 py-2 text-xs' : 'mb-2 px-3 py-2.5 text-sm'"
  >
    <div class="flex items-start gap-2">
      <IconifyIcon
        icon="lucide:alert-triangle"
        class="mt-0.5 size-4 shrink-0 text-destructive"
      />
      <div class="min-w-0 flex-1">
        <p class="break-words text-foreground">{{ msg.error.message }}</p>
        <p
          v-if="msg.error.traceId"
          class="mt-1 font-mono text-[11px] text-muted-foreground"
        >
          {{
            $t('common.globalAiChat.traceIdValue', {
              traceId: msg.error.traceId,
            })
          }}
        </p>
        <pre
          v-if="showDebugError"
          class="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded bg-black/5 p-2 text-[11px] text-red-500"
          >{{ msg.error?.debugMessage }}</pre
        >
      </div>
    </div>
  </div>
</template>
