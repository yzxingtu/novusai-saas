<script lang="ts" setup>
import { Drawer } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatContextDiagnosticsDrawer' });

const props = withDefaults(
  defineProps<{
    conversationContextDiagnostics?: unknown | null;
    interactionModeDowngraded?: boolean;
    interactionModeDowngradeText?: string;
    interactionModeLabel?: string;
    interactionModeRequested?: string;
    lastRunSummary?: unknown | null;
    open?: boolean;
  }>(),
  {
    conversationContextDiagnostics: null,
    interactionModeDowngraded: false,
    interactionModeDowngradeText: '',
    interactionModeLabel: '',
    interactionModeRequested: '',
    lastRunSummary: null,
    open: false,
  },
);

const emit = defineEmits<{
  'update:open': [boolean];
}>();
</script>

<template>
  <Drawer
    :open="open"
    :title="$t('common.globalAiChat.contextDiagnostics')"
    width="520"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <div class="space-y-4">
      <div class="rounded-2xl border border-border/60 bg-muted/10 p-3">
        <div class="text-xs font-medium text-muted-foreground">
          {{ $t('common.globalAiChat.interactionModeLabel') }}
        </div>
        <div class="mt-1 text-sm font-semibold text-foreground">
          {{ interactionModeLabel }}
        </div>
        <div
          v-if="interactionModeDowngraded"
          class="mt-2 rounded-xl border border-amber-300/50 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          <div class="font-medium">
            {{ $t('common.globalAiChat.trustedAutoDowngraded') }}
          </div>
          <div class="mt-1">
            {{ interactionModeRequested }} -> {{ interactionModeLabel }}
          </div>
          <div v-if="interactionModeDowngradeText" class="mt-1 text-[11px]">
            {{ interactionModeDowngradeText }}
          </div>
        </div>
      </div>
      <div
        v-if="conversationContextDiagnostics"
        class="rounded-2xl border border-border/60 bg-muted/10 p-3"
      >
        <div class="mb-2 text-xs font-medium text-muted-foreground">
          {{ $t('common.detail') }}
        </div>
        <pre
          class="overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-foreground"
          >{{ JSON.stringify(conversationContextDiagnostics, null, 2) }}</pre
        >
      </div>
      <div
        v-if="lastRunSummary"
        class="rounded-2xl border border-border/60 bg-muted/10 p-3"
      >
        <div class="mb-2 text-xs font-medium text-muted-foreground">
          {{ $t('common.globalAiChat.lastRunSummary') }}
        </div>
        <pre
          class="overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-foreground"
          >{{ JSON.stringify(lastRunSummary, null, 2) }}</pre
        >
      </div>
    </div>
  </Drawer>
</template>
