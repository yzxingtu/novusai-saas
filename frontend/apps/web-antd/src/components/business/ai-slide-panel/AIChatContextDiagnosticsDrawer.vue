<script lang="ts" setup>
import { Drawer } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AIChatContextDiagnosticsDrawer' });

withDefaults(
  defineProps<{
    conversationContextDiagnostics?: null | Record<string, unknown>;
    lastRunSummary?: null | Record<string, unknown>;
    open?: boolean;
  }>(),
  {
    conversationContextDiagnostics: null,
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
