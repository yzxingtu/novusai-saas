<script lang="ts" setup>
import type { KernelPendingActionState } from './TurnFlowState';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    action?: KernelPendingActionState | null;
    compact?: boolean;
  }>(),
  {
    action: null,
    compact: false,
  },
);

const emit = defineEmits<{
  approve: [];
  reject: [];
}>();

const actionLabel = computed(() => {
  if (props.action?.operationLabel) {
    return props.action.operationLabel;
  }
  if (props.action?.toolName) {
    return props.action.toolName;
  }
  return props.action?.action || props.action?.table || '';
});

const actionDescription = computed(() => {
  if (props.action?.operationDescription) {
    return props.action.operationDescription;
  }
  if (props.action?.table && props.action?.action) {
    return `${props.action.table} · ${props.action.action}`;
  }
  return props.action?.table || '';
});

const titleKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.confirmationTitle'
    : 'common.globalAiChat.consentTitle',
);

const approveKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.confirmBtn'
    : 'common.globalAiChat.consentAllow',
);

const rejectKey = computed(() =>
  props.action?.kind === 'confirmation'
    ? 'common.globalAiChat.rejectBtn'
    : 'common.globalAiChat.consentDeny',
);

const resolvedLabel = computed(() => {
  if (!props.action?.resolved) {
    return '';
  }
  if (props.action.kind === 'confirmation') {
    return $t('common.globalAiChat.confirmationResolved');
  }
  if (props.action.rejected) {
    return $t('common.globalAiChat.consentRejected');
  }
  if (props.action.autoApproved) {
    return $t('common.globalAiChat.consentAutoApproved');
  }
  return $t('common.globalAiChat.consentApproved');
});
</script>

<template>
  <div
    v-if="action"
    data-testid="chat-message-kernel-consent"
    class="overflow-hidden rounded-lg border"
    :class="[
      compact ? 'mb-1.5' : 'mb-2',
      action.resolved
        ? 'border-border/20 bg-accent/10'
        : 'border-warning/30 bg-warning/5',
    ]"
  >
    <div
      class="flex items-center gap-1.5 border-b border-border/20 text-muted-foreground"
      :class="compact ? 'px-2.5 py-1.5 text-[11px]' : 'px-3 py-2 text-xs'"
    >
      <IconifyIcon
        :icon="
          action.kind === 'confirmation'
            ? 'lucide:shield-question'
            : action.resolved
              ? 'lucide:shield-check'
              : 'lucide:shield-alert'
        "
        :class="compact ? 'size-3' : 'size-3.5'"
      />
      <span class="font-medium">{{ $t(titleKey) }}</span>
      <span
        v-if="action.resolved"
        class="ml-auto inline-flex shrink-0 items-center rounded-full px-1.5 py-[1px] text-[10px] font-medium"
        :class="
          action.rejected
            ? 'bg-red-500/10 text-red-500'
            : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
        "
      >
        {{ resolvedLabel }}
      </span>
    </div>

    <div :class="compact ? 'space-y-2 px-2.5 py-2' : 'space-y-2.5 px-3 py-2.5'">
      <div class="space-y-1">
        <p
          v-if="actionLabel"
          class="font-medium text-foreground/90"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          {{ actionLabel }}
        </p>
        <p
          v-if="actionDescription"
          class="text-muted-foreground/80"
          :class="compact ? 'text-[11px]' : 'text-xs'"
        >
          {{ actionDescription }}
        </p>
        <p
          v-if="action.skillName"
          class="text-muted-foreground/75"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          {{ action.skillName }}
        </p>
      </div>

      <div
        v-if="action.preview && Object.keys(action.preview).length > 0"
        class="overflow-y-auto rounded-md bg-accent/50"
        :class="
          compact
            ? 'max-h-32 px-2 py-1.5 text-[10px]'
            : 'max-h-40 px-3 py-2 text-xs'
        "
      >
        <table class="w-full text-left">
          <tr
            v-for="(value, key) in action.preview"
            :key="String(key)"
            class="border-b border-border/30 last:border-0"
          >
            <td
              class="whitespace-nowrap py-0.5 pr-3 font-medium text-foreground/70"
            >
              {{ key }}
            </td>
            <td class="break-all py-0.5 text-muted-foreground">
              {{ typeof value === 'object' ? JSON.stringify(value) : value }}
            </td>
          </tr>
        </table>
      </div>

      <details
        v-if="action.arguments && Object.keys(action.arguments).length > 0"
        class="[&>summary::-webkit-details-marker]:hidden [&>summary]:list-none"
      >
        <summary
          class="flex cursor-pointer items-center gap-1 text-muted-foreground/70 hover:text-muted-foreground"
          :class="compact ? 'text-[10px]' : 'text-[11px]'"
        >
          <IconifyIcon icon="lucide:code" class="size-3" />
          {{ $t('common.globalAiChat.consentShowArgs') }}
        </summary>
        <pre
          class="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-[10px] text-muted-foreground"
          >{{ JSON.stringify(action.arguments, null, 2) }}</pre
        >
      </details>

      <div v-if="!action.resolved" class="flex items-center gap-2">
        <button
          class="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
          @click="emit('approve')"
        >
          <IconifyIcon icon="lucide:check" class="size-3" />
          {{ $t(approveKey) }}
        </button>
        <button
          class="inline-flex items-center gap-1 rounded-md border border-border/60 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
          @click="emit('reject')"
        >
          <IconifyIcon icon="lucide:x" class="size-3" />
          {{ $t(rejectKey) }}
        </button>
      </div>
    </div>
  </div>
</template>
