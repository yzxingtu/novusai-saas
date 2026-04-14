<script lang="ts" setup>
import type { ChatMessage } from './types';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

const emit = defineEmits<{
  consentConfirm: [];
  consentReject: [];
}>();

const pendingConsent = computed(() => props.msg.pendingConsent);
</script>

<template>
  <div
    v-if="pendingConsent && !msg.streaming"
    class="overflow-hidden rounded-lg border"
    :class="[
      compact ? 'mt-1' : 'mt-1.5',
      pendingConsent.resolved
        ? 'border-border/20 bg-accent/10'
        : 'border-warning/30 bg-warning/5',
    ]"
  >
    <div
      v-if="pendingConsent.resolved"
      class="flex items-center gap-1.5 px-2.5 py-1 text-[11px]"
    >
      <IconifyIcon
        :icon="
          pendingConsent.rejected
            ? 'lucide:x-circle'
            : pendingConsent.autoApproved
              ? 'lucide:shield-check'
              : 'lucide:check-circle'
        "
        class="size-3 shrink-0"
        :class="pendingConsent.rejected ? 'text-red-500' : 'text-green-600'"
      />
      <span class="truncate text-muted-foreground">
        <span v-if="pendingConsent.skillName" class="font-medium text-foreground/60">
          {{ pendingConsent.skillName }} ›
        </span>
        <code class="text-[10px]">{{ pendingConsent.toolName }}</code>
      </span>
      <span
        class="ml-auto shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
        :class="
          pendingConsent.rejected
            ? 'bg-red-50 text-red-600 dark:bg-red-950/30'
            : pendingConsent.autoApproved
              ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/30'
              : 'bg-green-50 text-green-600 dark:bg-green-950/30'
        "
      >
        {{
          pendingConsent.rejected
            ? $t('common.globalAiChat.consentRejected')
            : pendingConsent.autoApproved
              ? $t('common.globalAiChat.consentAutoApproved')
              : $t('common.globalAiChat.consentApproved')
        }}
      </span>
    </div>

    <template v-else>
      <p class="border-b border-border/20 px-2.5 py-1 text-[10px] text-muted-foreground">
        {{ $t('common.globalAiChat.consentFirstTimeHint') }}
      </p>
      <div class="flex items-center gap-1.5 px-2.5 py-1.5">
        <IconifyIcon
          icon="lucide:shield-alert"
          class="size-3.5 shrink-0 text-warning"
        />
        <span class="flex-1 truncate text-[11px] text-muted-foreground">
          <span v-if="pendingConsent.skillName" class="font-medium text-foreground/70">
            {{ pendingConsent.skillName }} ›
          </span>
          <code class="text-[10px] font-semibold">{{ pendingConsent.toolName }}</code>
        </span>
        <div class="flex shrink-0 items-center gap-1">
          <button
            class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            @click="emit('consentConfirm')"
          >
            <IconifyIcon icon="lucide:check" class="size-3" />
            {{ $t('common.globalAiChat.consentAllow') }}
          </button>
          <button
            class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
            @click="emit('consentReject')"
          >
            <IconifyIcon icon="lucide:x" class="size-3" />
            {{ $t('common.globalAiChat.consentDeny') }}
          </button>
        </div>
      </div>
      <details
        v-if="
          pendingConsent.arguments &&
          Object.keys(pendingConsent.arguments).length > 0
        "
        class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
      >
        <summary
          class="flex cursor-pointer items-center gap-1 border-t border-border/20 px-2.5 py-0.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
        >
          <IconifyIcon icon="lucide:code" class="size-2.5" />
          {{ $t('common.globalAiChat.consentShowArgs') }}
          <IconifyIcon
            icon="lucide:chevron-down"
            class="size-2.5 transition-transform duration-200 [details[open]>&]:rotate-180"
          />
        </summary>
        <div class="border-t border-border/20 px-2.5 py-1">
          <pre
            class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
            >{{ JSON.stringify(pendingConsent.arguments, null, 2) }}</pre
          >
        </div>
      </details>
    </template>
  </div>
</template>
