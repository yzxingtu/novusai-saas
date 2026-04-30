<script setup lang="ts">
import type { PendingToolActionForDisplay } from './pending-tool-action';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { $t } from '#/locales';

const props = defineProps<{
  compact: boolean;
  countdownNow?: number;
  expanded: boolean;
  hasArgs: boolean;
  now: number;
  op: PendingToolActionForDisplay;
}>();

const emit = defineEmits<{
  resolve: [allowed: boolean];
  toggleArgs: [];
}>();

const remainingSeconds = computed(() =>
  Math.max(
    0,
    60 -
      Math.floor(
        ((props.countdownNow ?? props.now) - (props.op.startedAt || 0)) / 1000,
      ),
  ),
);
</script>

<template>
  <div
    class="mt-1 overflow-hidden rounded-lg border"
    :class="
      op.resolved
        ? 'border-border/20 bg-accent/10'
        : 'border-warning/30 bg-warning/5'
    "
  >
    <div
      v-if="op.resolved"
      class="flex items-center gap-1.5 px-2.5 py-1.5"
      :class="compact ? 'text-[10px]' : 'text-[11px]'"
    >
      <IconifyIcon
        :icon="op.allowed ? 'lucide:check-circle' : 'lucide:x-circle'"
        class="size-3 shrink-0"
        :class="op.allowed ? 'text-green-600' : 'text-red-500'"
      />
      <span class="truncate text-muted-foreground">
        <span class="font-medium text-foreground/60">{{
          op.operationLabel
        }}</span>
        <span
          v-if="op.operationDescription"
          class="ml-1 text-muted-foreground/60"
          >{{ op.operationDescription }}</span
        >
      </span>
      <span
        class="ml-auto shrink-0 rounded-full px-1.5 py-px font-medium"
        :class="[
          compact ? 'text-[9px]' : 'text-[10px]',
          op.allowed
            ? 'bg-green-50 text-green-600 dark:bg-green-950/30'
            : 'bg-red-50 text-red-600 dark:bg-red-950/30',
        ]"
      >
        {{
          op.allowed
            ? $t('shared.toolAction.confirmOk')
            : $t('shared.toolAction.confirmCancel')
        }}
      </span>
    </div>
    <template v-else>
      <div
        class="flex items-center gap-1.5 px-2.5 py-1.5"
        :class="compact ? 'text-[10px]' : 'text-[11px]'"
      >
        <IconifyIcon
          icon="lucide:shield-alert"
          class="size-3.5 shrink-0 text-warning"
        />
        <div class="min-w-0 flex-1">
          <div class="truncate font-medium text-foreground/80">
            {{ op.operationLabel }}
          </div>
          <div
            v-if="op.operationDescription"
            class="truncate text-muted-foreground/60"
          >
            {{ op.operationDescription }}
          </div>
          <div
            class="mt-0.5 text-muted-foreground/50"
            :class="compact ? 'text-[9px]' : 'text-[10px]'"
          >
            {{
              $t('shared.toolAction.confirmCountdown', {
                seconds: remainingSeconds,
              })
            }}
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-1">
          <button
            class="inline-flex items-center gap-0.5 rounded-md bg-primary px-2 py-0.5 font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
            :class="compact ? 'text-[10px]' : 'text-[11px]'"
            @click="emit('resolve', true)"
          >
            <IconifyIcon icon="lucide:check" class="size-3" />
            {{ $t('shared.toolAction.confirmOk') }}
          </button>
          <button
            class="inline-flex items-center gap-0.5 rounded-md border border-border/60 px-2 py-0.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
            :class="compact ? 'text-[10px]' : 'text-[11px]'"
            @click="emit('resolve', false)"
          >
            <IconifyIcon icon="lucide:x" class="size-3" />
            {{ $t('shared.toolAction.confirmCancel') }}
          </button>
        </div>
      </div>
      <div v-if="hasArgs" class="border-t border-border/20">
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-1 px-2.5 py-0.5 text-left text-muted-foreground/60 transition-colors hover:text-muted-foreground"
          :class="compact ? 'text-[9px]' : 'text-[10px]'"
          @click="emit('toggleArgs')"
        >
          <IconifyIcon icon="lucide:code" class="size-2.5" />
          {{ $t('common.globalAiChat.args') }}
          <IconifyIcon
            icon="lucide:chevron-down"
            class="size-2.5 transition-transform duration-200"
            :style="{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }"
          />
        </button>
        <div
          class="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
          :style="{
            gridTemplateRows: expanded ? '1fr' : '0fr',
            opacity: expanded ? 1 : 0,
          }"
        >
          <div class="min-h-0 overflow-hidden border-t border-border/20">
            <div class="px-2.5 py-1">
              <pre
                class="max-h-24 overflow-y-auto whitespace-pre-wrap rounded bg-accent/40 px-1.5 py-1 font-mono text-muted-foreground"
                :class="compact ? 'text-[9px]' : 'text-[10px]'"
                >{{ JSON.stringify(op.params, null, 2) }}</pre
              >
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
