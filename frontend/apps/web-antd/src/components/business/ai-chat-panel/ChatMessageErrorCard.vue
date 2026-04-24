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
  <div
    v-if="msg.error"
    data-testid="assistant-error-card"
    class="chat-error-card rounded-[18px] border"
    :class="compact ? 'mb-1 px-3 py-2.5 text-xs' : 'mb-2 px-3.5 py-3 text-sm'"
  >
    <div class="flex items-start gap-2">
      <IconifyIcon
        icon="lucide:alert-triangle"
        class="mt-0.5 size-4 shrink-0 text-destructive"
      />
      <div class="min-w-0 flex-1">
        <p class="text-foreground/88 break-words font-medium">
          {{ msg.error.message }}
        </p>
        <div
          v-if="msg.error.traceId"
          data-testid="assistant-error-trace-id"
          class="chat-error-trace mt-2 inline-flex max-w-full items-center gap-1 rounded-full px-2.5 py-1 font-mono text-[11px] text-muted-foreground"
        >
          <IconifyIcon icon="lucide:fingerprint" class="size-3 shrink-0" />
          <span class="truncate">
            {{
              $t('common.globalAiChat.traceIdValue', {
                traceId: msg.error.traceId,
              })
            }}
          </span>
        </div>
        <pre
          v-if="showDebugError"
          class="mt-2 max-h-36 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-black/5 p-2 text-[11px] text-red-500"
          >{{ msg.error?.debugMessage }}</pre
        >
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-error-card {
  border-color: hsl(var(--destructive) / 0.32);
  background:
    linear-gradient(
      180deg,
      hsl(var(--destructive) / 0.08) 0%,
      hsl(var(--destructive) / 0.035) 100%
    ),
    hsl(var(--background));
  box-shadow: 0 14px 24px -24px hsl(var(--destructive) / 0.28);
}

.chat-error-trace {
  border: 1px solid hsl(var(--destructive) / 0.22);
  background: hsl(var(--background) / 0.92);
}
</style>
